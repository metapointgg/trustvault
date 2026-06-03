from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.audit.events import SEARCH_EXECUTED
from trustvault.audit.logger import AuditLogger
from trustvault.api.dependencies import get_audit_logger, get_current_user, get_database
from trustvault.core.feature_services import TrustVaultFeatureService
from trustvault.core.query_ai_summary import summarise_query_results
from trustvault.core.query_examples import ENRICHED_QUERY_SCENARIOS, QUERY_REGRESSION_TEST_CASES
from trustvault.core.query_interpreter import StructuredQuery, TrustVaultQueryInterpreter
from trustvault.db.models import Entity, FitsIndexEntry, User

router = APIRouter(prefix="/api/v1/query", tags=["query"])


class InterpretRequest(BaseModel):
    query: str = Field(min_length=1)
    entity_external_id: str | None = None
    industry_key: str | None = None
    mode: str = Field(default="auto", pattern="^(deterministic|ai|auto)$")


class ExecuteRequest(BaseModel):
    query: str = Field(min_length=1)
    entity_external_id: str | None = None
    industry_key: str | None = None
    limit: int = Field(default=50, ge=1, le=500)
    mode: str = Field(default="auto", pattern="^(deterministic|ai|auto)$")
    include_ai_summary: bool = False


SCENARIOS: list[dict[str, Any]] = ENRICHED_QUERY_SCENARIOS


def _interpret(request: InterpretRequest | ExecuteRequest, db: Session) -> tuple[StructuredQuery, dict[str, Any]]:
    structured = TrustVaultQueryInterpreter().interpret(
        request.query,
        entity_external_id=request.entity_external_id,
        industry_key=request.industry_key,
    )
    meta: dict[str, Any] = {
        "mode": request.mode,
        "deterministic_query": structured.to_dict(),
        "requested_industry_key": request.industry_key,
        "ai_used": False,
        "ai_provider": "trustvault",
        "ai_model": "deterministic_query_interpreter",
        "ai_base_url": None,
        "ai_warnings": [],
        "ai_skipped": True,
        "ai_skip_reason": "query route uses deterministic interpretation plus configured vocabulary patches",
    }
    return structured, meta


def _safe_summary_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in {
        "entity_external_id": row.get("entity_external_id") or row.get("external_id"),
        "entity_display_name": row.get("entity_display_name") or row.get("display_name"),
        "filename": row.get("filename"),
        "document_type": row.get("document_type") or row.get("object_type"),
        "category": row.get("category"),
        "status": row.get("status"),
        "snippet": row.get("snippet"),
    }.items() if value not in (None, "", [], {})}


def _norm(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _snippet(text: str, query: str = "", window: int = 180) -> str:
    text = str(text or "")
    query = str(query or "").lower()
    if not query or query not in text.lower():
        return text[: window * 2]
    index = text.lower().find(query)
    start = max(index - window, 0)
    end = min(index + len(query) + window, len(text))
    return f"{'...' if start > 0 else ''}{text[start:end]}{'...' if end < len(text) else ''}"


def _metadata_value(row: dict[str, Any], key: str) -> Any:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    nested = metadata.get("metadata") if isinstance(metadata.get("metadata"), dict) else {}
    entity_metadata = metadata.get("entity_metadata") if isinstance(metadata.get("entity_metadata"), dict) else {}
    return row.get(key) or metadata.get(key) or nested.get(key) or entity_metadata.get(key)


def _row_from_index_entry(entry: FitsIndexEntry, entity: Entity | None) -> dict[str, Any]:
    metadata = entry.metadata_json or {}
    nested = metadata.get("metadata") if isinstance(metadata.get("metadata"), dict) else {}
    search_text = nested.get("search_text") or metadata.get("search_text") or entry.text_content or ""
    searchable = "\n".join([entry.filename or "", entry.object_type or "", entry.source_system or "", search_text, json.dumps(metadata, default=str)])
    return {
        "entity_id": str(entry.entity_id),
        "entity_external_id": entity.external_id if entity else None,
        "entity_display_name": entity.display_name if entity else None,
        "container_version_id": str(entry.container_version_id),
        "evidence_object_id": entry.evidence_object_id,
        "hdu_name": entry.hdu_name,
        "filename": entry.filename,
        "object_type": entry.object_type,
        "source_system": entry.source_system,
        "sha256": entry.sha256,
        "snippet": _snippet(search_text or searchable),
        "metadata": metadata,
        "text_content": search_text,
        "risk_rating": _metadata_value({"metadata": metadata}, "risk_rating"),
        "jurisdiction": _metadata_value({"metadata": metadata}, "jurisdiction"),
        "category": _metadata_value({"metadata": metadata}, "category"),
        "document_type": _metadata_value({"metadata": metadata}, "document_type"),
        "_searchable": searchable,
    }


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not key.startswith("_")}


def _term_matches(terms: list[str], searchable: str) -> bool:
    if not terms:
        return True
    lower = searchable.lower()
    for term in terms:
        tokens = [token for token in str(term).lower().replace("_", " ").split() if len(token) > 2 and token not in {"show", "trustvault", "which", "have", "not", "the", "are", "for"}]
        if tokens and all(token in lower for token in tokens):
            return True
        if str(term).lower() in lower:
            return True
    return False


def _structured_index_search(db: Session, service: TrustVaultFeatureService, structured: StructuredQuery, query: str, limit: int) -> dict[str, Any]:
    entries = db.scalars(select(FitsIndexEntry).order_by(FitsIndexEntry.created_at.desc()).limit(5000)).all()
    rows: list[dict[str, Any]] = []
    terms = structured.search_terms or [query]
    for entry in entries:
        entity = db.get(Entity, entry.entity_id)
        if entity is None:
            continue
        if structured.entity_external_id and entity.external_id != structured.entity_external_id:
            continue
        row = _row_from_index_entry(entry, entity)
        if structured.risk_rating and _norm(_metadata_value(row, "risk_rating")) != _norm(structured.risk_rating):
            continue
        if structured.jurisdiction and _norm(_metadata_value(row, "jurisdiction")) != _norm(structured.jurisdiction):
            continue
        if structured.document_types:
            doc = _norm(row.get("document_type") or row.get("object_type") or row.get("filename"))
            if not any(_norm(item) in doc or doc in _norm(item) for item in structured.document_types):
                continue
        if structured.categories:
            category = _norm(_metadata_value(row, "category") or row.get("object_type"))
            if not any(_norm(item) == category for item in structured.categories):
                continue
        if not _term_matches(terms, row.get("_searchable") or "") and not (structured.document_types or structured.categories):
            continue
        row["match_reason"] = "metadata_or_text"
        row["match_score"] = 50
        rows.append(row)
    limited = [_public_row(row) for row in rows[:limit]]
    return {
        "query": query,
        "entity_id": None,
        "entity_external_id": structured.entity_external_id,
        "container_version_id": None,
        "result_count": len(limited),
        "results": limited,
        "filtered_entity_count": len({row.get("entity_external_id") for row in rows if row.get("entity_external_id")}),
        "diagnostics": {
            "candidate_index_entry_count": len(entries),
            "matched_before_limit": len(rows),
            "requested_entity_external_id": structured.entity_external_id,
            "requested_industry_key": structured.industry_key,
            "requested_risk_rating": structured.risk_rating,
            "requested_jurisdiction": structured.jurisdiction,
            "categories": structured.categories,
            "document_types": structured.document_types,
            "search_terms": structured.search_terms,
        },
    }


def _missing_rule_matches(row: dict[str, Any], missing_evidence_type: str | None) -> bool:
    if row.get("status") != "missing":
        return False
    if not missing_evidence_type or missing_evidence_type == "mandatory_evidence":
        return True
    target = _norm(missing_evidence_type)
    values = [_norm(row.get("rule_key")), _norm(row.get("category")), _norm(row.get("document_type"))]
    return any(target == value or target in value or value in target for value in values if value)


def _completeness_result_row(entity: dict[str, Any], run: dict[str, Any], missing_rule: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "entity_id": entity.get("id"),
        "entity_external_id": entity.get("external_id"),
        "entity_display_name": entity.get("display_name"),
        "entity_type": entity.get("entity_type"),
        "risk_rating": entity.get("risk_rating"),
        "jurisdiction": entity.get("jurisdiction"),
        "status": missing_rule.get("status") if missing_rule else ("missing" if (run.get("missing_count") or 0) else "complete"),
        "summary_type": "missing_evidence" if missing_rule else "completeness_summary",
        "rule_key": missing_rule.get("rule_key") if missing_rule else None,
        "category": missing_rule.get("category") if missing_rule else None,
        "document_type": missing_rule.get("document_type") if missing_rule else None,
        "missing_evidence_type": missing_rule.get("document_type") if missing_rule else None,
        "completeness_score": run.get("score"),
        "required_count": run.get("required_count"),
        "present_count": run.get("present_count"),
        "missing_count": run.get("missing_count"),
        "matched_evidence_object_id": missing_rule.get("matched_evidence_object_id") if missing_rule else None,
        "matched_filename": missing_rule.get("matched_filename") if missing_rule else None,
        "snippet": f"Missing required evidence: {missing_rule.get('document_type') or missing_rule.get('category') or missing_rule.get('rule_key')}" if missing_rule else f"Completeness score {run.get('score')}%, missing {run.get('missing_count')} item(s).",
    }


def _completeness_check_result(service: TrustVaultFeatureService, structured: StructuredQuery, limit: int) -> dict[str, Any]:
    entities = service.customers(risk_rating=structured.risk_rating, jurisdiction=structured.jurisdiction)
    if structured.entity_external_id:
        entities = [entity for entity in entities if entity["external_id"] == structured.entity_external_id]
    rows: list[dict[str, Any]] = []
    for entity in entities:
        run = service.evaluate_completeness(entity["external_id"])
        missing_rows = [row for row in run.get("results", []) if _missing_rule_matches(row, structured.missing_evidence_type)]
        if structured.missing_evidence_type or structured.completeness_only or "missing" in structured.raw_query.lower() or "incomplete" in structured.raw_query.lower():
            rows.extend(_completeness_result_row(entity, run, row) for row in missing_rows)
        else:
            rows.append(_completeness_result_row(entity, run))
    limited = rows[:limit]
    return {
        "query": structured.raw_query,
        "entity_id": None,
        "entity_external_id": structured.entity_external_id,
        "container_version_id": None,
        "result_count": len(limited),
        "results": limited,
        "filtered_entity_count": len({row.get("entity_external_id") for row in rows if row.get("entity_external_id")}),
        "diagnostics": {
            "execution_mode": "completeness_check",
            "requested_entity_external_id": structured.entity_external_id,
            "requested_industry_key": structured.industry_key,
            "requested_risk_rating": structured.risk_rating,
            "requested_jurisdiction": structured.jurisdiction,
            "missing_evidence_type": structured.missing_evidence_type,
            "matching_entity_count": len(entities),
            "matching_entity_external_ids": [entity["external_id"] for entity in entities],
            "matched_before_limit": len(rows),
        },
    }


def _archive_status_result(service: TrustVaultFeatureService, structured: StructuredQuery) -> dict[str, Any]:
    status = service.archive_status()
    configuration = status.get("configuration") if isinstance(status.get("configuration"), dict) else {}
    checks = status.get("archive_checks") if isinstance(status.get("archive_checks"), dict) else {}
    display_row = {
        **status,
        "entity_external_id": "ARCHIVE",
        "entity_display_name": "TrustVault archive",
        "filename": "Archive status",
        "category": "archive_status",
        "document_type": "Archive Status",
        "source_system": "TrustVault",
        "status": "ok" if not status.get("failed_jobs") and not status.get("integrity_issue_count") else "attention_required",
        "summary_type": "archive_status",
        "snippet": (
            f"{status.get('entity_count', 0)} entities; "
            f"{status.get('current_fits_container_count', 0)} current FITS containers; "
            f"{status.get('fits_index_entry_count', 0)} indexed evidence objects; "
            f"{status.get('queued_jobs', 0)} queued jobs; "
            f"{status.get('failed_jobs', 0)} failed jobs."
        ),
        "storage_provider": configuration.get("storage_provider"),
        "queue_provider": configuration.get("queue_provider"),
        "source_folder": configuration.get("source_folder"),
        "containers_folder": configuration.get("containers_folder"),
        "index_path": configuration.get("index_path"),
        "exports_folder": configuration.get("exports_folder"),
        "fits_source_of_truth": checks.get("fits_source_of_truth"),
        "index_rebuildable": checks.get("index_rebuildable"),
        "direct_fits_search_available": checks.get("direct_fits_search_available"),
        "cross_archive_index_available": checks.get("cross_archive_index_available"),
    }
    return {"query": structured.raw_query, "result_count": 1, "results": [display_row], "diagnostics": {"execution_mode": "archive_status", "requested_industry_key": structured.industry_key}}


def _entity_discovery_result(service: TrustVaultFeatureService, structured: StructuredQuery, limit: int) -> dict[str, Any]:
    rows = service.customers(risk_rating=structured.risk_rating, jurisdiction=structured.jurisdiction, limit=limit)
    return {"query": structured.raw_query, "result_count": len(rows), "results": rows, "diagnostics": {"execution_mode": "entity_discovery", "requested_industry_key": structured.industry_key}}


def _summarise_if_requested(request: ExecuteRequest, structured: StructuredQuery, meta: dict[str, Any], result: dict[str, Any], db: Session, execution_source: str) -> dict[str, Any] | None:
    if not request.include_ai_summary:
        return None
    return summarise_query_results(
        db=db,
        raw_query=request.query,
        structured_query=structured.to_dict(),
        interpretation=meta,
        execution_source=execution_source,
        result=result,
    )


def _audit_and_return(*, request: ExecuteRequest, structured: StructuredQuery, meta: dict[str, Any], result: dict[str, Any], execution_source: str, audit_logger: AuditLogger, db: Session, current_user: User) -> dict[str, Any]:
    audit_logger.log(
        SEARCH_EXECUTED,
        raw_query=request.query,
        structured_query=structured.to_dict(),
        result_count=result.get("result_count", 0),
        search_source=execution_source,
        user_id=str(current_user.id),
        metadata={"interpretation": meta, "diagnostics": result.get("diagnostics"), "user_email": current_user.email},
    )
    return {"structured_query": structured.to_dict(), "interpretation": meta, "execution_source": execution_source, "result": result, "ai_summary": _summarise_if_requested(request, structured, meta, result, db, execution_source)}


@router.get("/archive/status")
def archive_status(db: Session = Depends(get_database)) -> dict[str, Any]:
    return TrustVaultFeatureService(db).archive_status()


@router.get("/scenarios")
def query_scenarios() -> dict[str, Any]:
    return {"scenario_group_count": len(SCENARIOS), "scenarios": SCENARIOS}


@router.get("/test-cases")
def query_test_cases() -> dict[str, Any]:
    return {"test_case_count": len(QUERY_REGRESSION_TEST_CASES), "test_cases": QUERY_REGRESSION_TEST_CASES}


@router.post("/interpret")
def interpret_query(request: InterpretRequest, db: Session = Depends(get_database), audit_logger: AuditLogger = Depends(get_audit_logger), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    structured, meta = _interpret(request, db)
    audit_logger.log(SEARCH_EXECUTED, raw_query=request.query, structured_query=structured.to_dict(), user_id=str(current_user.id), metadata={"operation": "query_interpret", **meta})
    return {"structured_query": structured.to_dict(), "interpretation": meta}


@router.post("/execute")
def execute_query(request: ExecuteRequest, db: Session = Depends(get_database), audit_logger: AuditLogger = Depends(get_audit_logger), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    service = TrustVaultFeatureService(db)
    structured, meta = _interpret(request, db)
    if structured.capability == "archive_status":
        return _audit_and_return(request=request, structured=structured, meta=meta, result=_archive_status_result(service, structured), execution_source="archive_status", audit_logger=audit_logger, db=db, current_user=current_user)
    if structured.capability == "entity_discovery":
        return _audit_and_return(request=request, structured=structured, meta=meta, result=_entity_discovery_result(service, structured, request.limit), execution_source="entity_metadata", audit_logger=audit_logger, db=db, current_user=current_user)
    if structured.capability == "completeness_check":
        return _audit_and_return(request=request, structured=structured, meta=meta, result=_completeness_check_result(service, structured, request.limit), execution_source="completeness_rules", audit_logger=audit_logger, db=db, current_user=current_user)
    terms = structured.search_terms or [request.query]
    result = _structured_index_search(db, service, structured, " ".join(terms), request.limit)
    return _audit_and_return(request=request, structured=structured, meta=meta, result=result, execution_source="fits_index", audit_logger=audit_logger, db=db, current_user=current_user)
