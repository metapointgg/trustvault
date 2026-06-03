from __future__ import annotations

from typing import Any

from sqlalchemy import select

from trustvault.core.industry_query_filters import (
    active_query_context,
    document_types_for_missing_check,
    entity_matches_context,
    evidence_has_document_type,
)
from trustvault.core.query_vocabulary import QueryVocabularyService
from trustvault.db.models import Entity, FitsIndexEntry


_PATCHED = False


def apply(query_module: Any) -> None:
    """Apply validated industry vocabulary matches to legacy query output/execution.

    This is a bridge while TrustVault moves from the current legacy structured
    query shape to a fully generic filters/requirement query object. It avoids
    adding more hardcoded jurisdictions, departments, clinician names or document
    types to the deterministic interpreter.
    """

    global _PATCHED
    if _PATCHED:
        return

    original_interpret = query_module._interpret
    original_structured_index_search = query_module._structured_index_search

    def patched_interpret(request: Any, db: Any) -> tuple[Any, dict[str, Any]]:
        structured, meta = original_interpret(request, db)
        service = QueryVocabularyService(db)
        resolved = service.legacy_structured_overrides(request.query)
        overrides = resolved.get("overrides") or {}
        meta["resolved_vocabulary"] = resolved.get("resolved_vocabulary")
        meta["vocabulary_overrides"] = overrides
        context = active_query_context(db, request.query)
        meta["active_industry_context"] = {
            "industry_key": context.get("industry_key"),
            "metadata_filters": context.get("metadata_filters"),
            "document_requirements": context.get("document_requirements"),
            "requirement_groups": context.get("requirement_groups"),
        }
        if not overrides:
            return structured, meta

        data = structured.to_dict()
        data.update({key: value for key, value in overrides.items() if value is not None})
        if data.get("entity_external_id"):
            data["scope"] = "entity"
        else:
            data["scope"] = "archive"
        if data.get("capability") == "completeness_check":
            data["execute_with"] = "fits_index"
        structured = query_module.StructuredQuery(**data)
        meta["structured_query_after_vocabulary"] = structured.to_dict()
        return structured, meta

    def patched_completeness_check_result(service: Any, structured: Any, limit: int) -> dict[str, Any]:
        db = service.db
        context = active_query_context(db, structured.raw_query)
        entities = service.customers(risk_rating=structured.risk_rating, jurisdiction=structured.jurisdiction)
        entities = [entity for entity in entities if entity_matches_context(entity, context)]
        if structured.entity_external_id:
            entities = [entity for entity in entities if entity["external_id"] == structured.entity_external_id]
        expected_document_types = document_types_for_missing_check(context)
        rows: list[dict[str, Any]] = []
        diagnostics = {
            "execution_mode": "industry_completeness_check",
            "active_industry": context.get("industry_key"),
            "metadata_filters": context.get("metadata_filters"),
            "requested_entity_external_id": structured.entity_external_id,
            "requested_risk_rating": structured.risk_rating,
            "requested_jurisdiction": structured.jurisdiction,
            "missing_evidence_type": structured.missing_evidence_type,
            "expected_document_types": expected_document_types,
            "matching_entity_count": len(entities),
            "matching_entity_external_ids": [entity["external_id"] for entity in entities],
        }
        for entity in entities:
            missing = _missing_documents_for_entity(db, entity, expected_document_types)
            if expected_document_types:
                for document_type in missing:
                    rows.append(_industry_missing_row(entity, document_type))
                continue
            # Fall back to the existing completeness rules for financial-services/default checks.
            run = service.evaluate_completeness(entity["external_id"])
            missing_rows = [row for row in run.get("results", []) if query_module._missing_rule_matches(row, structured.missing_evidence_type)]
            rows.extend(query_module._completeness_result_row(entity, run, missing_rule) for missing_rule in missing_rows)
        limited = rows[:limit]
        diagnostics["matched_missing_entity_count"] = len({row.get("entity_external_id") for row in rows if row.get("entity_external_id")})
        diagnostics["matched_before_limit"] = len(rows)
        return {
            "query": structured.raw_query,
            "entity_id": None,
            "entity_external_id": structured.entity_external_id,
            "container_version_id": None,
            "result_count": len(limited),
            "results": limited,
            "filtered_entity_count": diagnostics["matched_missing_entity_count"],
            "diagnostics": diagnostics,
        }

    def patched_structured_index_search(db: Any, service: Any, structured: Any, query: str, limit: int) -> dict[str, Any]:
        context = active_query_context(db, structured.raw_query)
        result = original_structured_index_search(db, service, structured, query, 5000)
        rows = [row for row in result.get("results", []) if _row_matches_context(row, context)]
        limited = rows[:limit]
        diagnostics = dict(result.get("diagnostics") or {})
        diagnostics.update(
            {
                "active_industry": context.get("industry_key"),
                "metadata_filters": context.get("metadata_filters"),
                "active_industry_filtered_before_limit": len(rows),
                "active_industry_filtered_entity_external_ids": sorted({str(row.get("entity_external_id")) for row in rows if row.get("entity_external_id")})[:100],
            }
        )
        return {**result, "result_count": len(limited), "results": limited, "filtered_entity_count": len({row.get("entity_external_id") for row in rows if row.get("entity_external_id")}), "diagnostics": diagnostics}

    query_module._interpret = patched_interpret
    query_module._completeness_check_result = patched_completeness_check_result
    query_module._structured_index_search = patched_structured_index_search
    _PATCHED = True


def _missing_documents_for_entity(db: Any, entity_row: dict[str, Any], expected_document_types: list[str]) -> list[str]:
    if not expected_document_types:
        return []
    entity = db.get(Entity, entity_row["id"])
    if entity is None:
        return expected_document_types
    entries = db.scalars(select(FitsIndexEntry).where(FitsIndexEntry.entity_id == entity.id)).all()
    present = set()
    for entry in entries:
        metadata = entry.metadata_json or {}
        nested = metadata.get("metadata") if isinstance(metadata.get("metadata"), dict) else {}
        row = {
            "filename": entry.filename,
            "object_type": entry.object_type,
            "category": metadata.get("category") or nested.get("category"),
            "document_type": metadata.get("document_type") or nested.get("document_type"),
        }
        for document_type in expected_document_types:
            if evidence_has_document_type(row, document_type):
                present.add(document_type)
    return [document_type for document_type in expected_document_types if document_type not in present]


def _industry_missing_row(entity: dict[str, Any], document_type: str) -> dict[str, Any]:
    metadata = entity.get("metadata_json") if isinstance(entity.get("metadata_json"), dict) else {}
    return {
        "entity_id": entity.get("id"),
        "entity_external_id": entity.get("external_id"),
        "entity_display_name": entity.get("display_name"),
        "entity_type": entity.get("entity_type"),
        "risk_rating": entity.get("risk_rating"),
        "jurisdiction": entity.get("jurisdiction"),
        "department": metadata.get("department"),
        "responsible_person": metadata.get("responsible_person"),
        "supplier_category": metadata.get("supplier_category"),
        "criticality": metadata.get("criticality"),
        "status": "missing",
        "summary_type": "missing_evidence",
        "rule_key": _to_key(document_type),
        "category": None,
        "document_type": document_type,
        "missing_evidence_type": document_type,
        "completeness_score": None,
        "required_count": None,
        "present_count": None,
        "missing_count": None,
        "matched_evidence_object_id": None,
        "matched_filename": None,
        "snippet": f"Missing required evidence: {document_type}",
    }


def _row_matches_context(row: dict[str, Any], context: dict[str, Any]) -> bool:
    entity_row = {
        "external_id": row.get("entity_external_id") or row.get("external_id"),
        "entity_type": row.get("entity_type"),
        "metadata_json": row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
    }
    # FITS rows can contain nested evidence metadata rather than entity metadata, so
    # industry filtering for indexed rows is primarily by entity id prefix/metadata.
    external_id = str(entity_row.get("external_id") or "")
    industry = context.get("industry_key")
    if industry == "healthcare" and not external_id.startswith("PAT-"):
        return False
    if industry == "supplier_due_diligence" and not external_id.startswith("SUP-"):
        return False
    if industry == "financial_services" and external_id.startswith(("PAT-", "SUP-")):
        return False
    for item in context.get("metadata_filters") or []:
        field = item.get("field_binding")
        expected = _normalise(item.get("canonical_value"))
        actual_values = [row.get(field), row.get("metadata", {}).get(field) if isinstance(row.get("metadata"), dict) else None, row.get("text_content"), row.get("filename")]
        if not any(expected and expected in _normalise(value) for value in actual_values):
            return False
    return True


def _to_key(value: str) -> str:
    return _normalise(value).replace(" ", "_")


def _normalise(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
