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
        context = active_query_context(db, request.query)
        service = QueryVocabularyService(db, industry_key=context.get("industry_key"))
        resolved = service.legacy_structured_overrides(request.query)
        overrides = resolved.get("overrides") or {}
        context_document_types = document_types_for_missing_check(context)
        if _has_missing_intent(request.query) and context_document_types:
            overrides = {
                **overrides,
                "capability": "completeness_check",
                "completeness_only": True,
                "document_types": overrides.get("document_types") or context_document_types,
                "missing_evidence_type": overrides.get("missing_evidence_type") or _to_key(context_document_types[0]),
                "execute_with": "fits_index",
            }
        if _has_missing_intent(request.query) and context.get("requirement_groups") and not context_document_types:
            overrides = {
                **overrides,
                "capability": "completeness_check",
                "completeness_only": True,
                "missing_evidence_type": overrides.get("missing_evidence_type") or "mandatory_evidence",
                "execute_with": "fits_index",
            }
        if _has_entity_list_intent(request.query) and not _has_missing_intent(request.query) and not context_document_types and not context.get("requirement_groups"):
            overrides = {
                **overrides,
                "capability": "entity_discovery",
                "completeness_only": False,
                "document_types": [],
                "categories": [],
                "missing_evidence_type": None,
                "execute_with": "entity_metadata",
            }
        meta["resolved_vocabulary"] = resolved.get("resolved_vocabulary") or context.get("resolved_vocabulary")
        meta["vocabulary_overrides"] = overrides
        meta["active_industry_context"] = {
            "industry_key": context.get("industry_key"),
            "metadata_filters": context.get("metadata_filters"),
            "document_requirements": context.get("document_requirements"),
            "requirement_groups": context.get("requirement_groups"),
        }
        if overrides:
            _normalise_ai_raw(meta, overrides, context)
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
            "industry_filter_source": "entity_and_fits_metadata",
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

    def patched_entity_discovery_result(service: Any, structured: Any, limit: int) -> dict[str, Any]:
        db = service.db
        context = active_query_context(db, structured.raw_query)
        entities = service.customers(risk_rating=structured.risk_rating, jurisdiction=structured.jurisdiction)
        entities = [entity for entity in entities if entity_matches_context(entity, context)]
        if structured.entity_external_id:
            entities = [entity for entity in entities if entity["external_id"] == structured.entity_external_id]
        limited = entities[:limit]
        diagnostics = {
            "execution_mode": "industry_entity_discovery",
            "active_industry": context.get("industry_key"),
            "industry_filter_source": "entity_metadata",
            "metadata_filters": context.get("metadata_filters"),
            "requested_entity_external_id": structured.entity_external_id,
            "requested_risk_rating": structured.risk_rating,
            "requested_jurisdiction": structured.jurisdiction,
            "matching_entity_count": len(entities),
            "matching_entity_external_ids": [entity["external_id"] for entity in entities],
            "matched_before_limit": len(entities),
        }
        return {
            "query": structured.raw_query,
            "result_count": len(limited),
            "results": limited,
            "filtered_entity_count": len(limited),
            "diagnostics": diagnostics,
        }

    def patched_structured_index_search(db: Any, service: Any, structured: Any, query: str, limit: int) -> dict[str, Any]:
        context = active_query_context(db, structured.raw_query)
        result = original_structured_index_search(db, service, structured, query, 5000)
        rows = [row for row in result.get("results", []) if _row_matches_context(db, row, context)]
        limited = rows[:limit]
        diagnostics = dict(result.get("diagnostics") or {})
        diagnostics.update(
            {
                "active_industry": context.get("industry_key"),
                "industry_filter_source": "entity_and_fits_metadata",
                "metadata_filters": context.get("metadata_filters"),
                "active_industry_filtered_before_limit": len(rows),
                "active_industry_filtered_entity_external_ids": sorted({str(row.get("entity_external_id")) for row in rows if row.get("entity_external_id")})[:100],
            }
        )
        return {**result, "result_count": len(limited), "results": limited, "filtered_entity_count": len({row.get("entity_external_id") for row in rows if row.get("entity_external_id")}), "diagnostics": diagnostics}

    query_module._interpret = patched_interpret
    query_module._completeness_check_result = patched_completeness_check_result
    query_module._entity_discovery_result = patched_entity_discovery_result
    query_module._structured_index_search = patched_structured_index_search
    _PATCHED = True


def _normalise_ai_raw(meta: dict[str, Any], overrides: dict[str, Any], context: dict[str, Any]) -> None:
    ai_raw = meta.get("ai_raw")
    if not isinstance(ai_raw, dict):
        return
    if overrides.get("capability") != "completeness_check":
        return
    ai_raw["capability"] = "completeness_check"
    ai_raw["completeness_only"] = True
    ai_raw["missing_evidence_type"] = overrides.get("missing_evidence_type")
    ai_raw["document_types"] = overrides.get("document_types") or context.get("document_requirements") or []
    ai_raw["execute_with"] = "fits_index"
    ai_raw["confidence"] = max(float(ai_raw.get("confidence") or 0), 0.92)
    ai_raw["reason"] = "Resolved by configured industry vocabulary: missing required evidence/document terms route to completeness_check, with filters and requirements validated against the active industry pack."


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
        "industry_pack": metadata.get("industry_pack") or metadata.get("industry") or metadata.get("demo_archive_key"),
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


def _row_matches_context(db: Any, row: dict[str, Any], context: dict[str, Any]) -> bool:
    entity = None
    entity_id = row.get("entity_id")
    if entity_id:
        try:
            entity = db.get(Entity, entity_id)
        except Exception:
            entity = None
    if entity is None and row.get("entity_external_id"):
        entity = db.scalars(select(Entity).where(Entity.external_id == row.get("entity_external_id"))).first()
    if entity is None:
        return False

    entity_row = {
        "external_id": entity.external_id,
        "entity_type": entity.entity_type,
        "metadata_json": entity.metadata_json or {},
    }
    if not entity_matches_context(entity_row, context):
        return False

    for item in context.get("metadata_filters") or []:
        field = item.get("field_binding")
        expected = _normalise(item.get("canonical_value"))
        metadata = entity.metadata_json or {}
        evidence_metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        actual_values = [
            metadata.get(field),
            row.get(field),
            evidence_metadata.get(field),
            row.get("text_content"),
            row.get("filename"),
        ]
        if not any(expected and expected in _normalise(value) for value in actual_values):
            return False
    return True


def _has_missing_intent(query: str) -> bool:
    normalised = _normalise(query)
    return any(phrase in normalised for phrase in ("missing", "not_supplied", "not_provided", "without", "outstanding", "have_not_supplied", "has_not_supplied"))


def _has_entity_list_intent(query: str) -> bool:
    normalised = _normalise(query)
    tokens = {token for token in normalised.split("_") if token}
    has_listing_verb = bool(tokens & {"list", "show", "find", "identify"})
    has_entity_subject = bool(tokens & {"patient", "patients", "supplier", "suppliers", "vendor", "vendors", "customer", "customers", "entity", "entities"})
    if not has_listing_verb or not has_entity_subject:
        return False
    # Queries that explicitly ask for evidence/documents/search should remain evidence searches unless they are missing/completeness queries.
    evidence_terms = {"evidence", "document", "documents", "documentation", "reports", "report", "certificate", "certificates", "agreement", "agreements"}
    return not bool(tokens & evidence_terms)


def _to_key(value: str) -> str:
    return _normalise(value).replace(" ", "_")


def _normalise(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
