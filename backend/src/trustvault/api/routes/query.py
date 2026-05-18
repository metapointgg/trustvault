import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.ai.lm_studio import LmStudioAiProvider
from trustvault.audit.events import AI_SUMMARY_GENERATED, SEARCH_EXECUTED
from trustvault.audit.logger import AuditLogger
from trustvault.api.dependencies import get_audit_logger, get_database
from trustvault.core.app_settings import AppSettingsService
from trustvault.core.feature_services import TrustVaultFeatureService
from trustvault.core.fits_reader import FitsContainerReader
from trustvault.core.query_interpreter import StructuredQuery, TrustVaultQueryInterpreter
from trustvault.db.models import Entity, FitsIndexEntry

router = APIRouter(prefix="/api/v1/query", tags=["query"])


class InterpretRequest(BaseModel):
    query: str = Field(min_length=1)
    entity_external_id: str | None = None
    mode: str = Field(default="auto", pattern="^(deterministic|ai|auto)$")


class ExecuteRequest(BaseModel):
    query: str = Field(min_length=1)
    entity_external_id: str | None = None
    limit: int = Field(default=50, ge=1, le=500)
    mode: str = Field(default="auto", pattern="^(deterministic|ai|auto)$")
    include_ai_summary: bool = False


SCENARIOS: list[dict[str, Any]] = [
    {"group": "Archive/status checks", "examples": ["Use TrustVault to show me the archive status.", "Use TrustVault to tell me how many entities, containers and indexed evidence objects are available.", "Use TrustVault to show the configured source folder, containers folder, index path and exports folder."]},
    {"group": "Entity discovery", "examples": ["Use TrustVault to list the first 10 entities.", "Use TrustVault to list high risk entities.", "Use TrustVault to list high risk entities in Guernsey.", "Use TrustVault to list medium risk entities in Jersey.", "Use TrustVault to list low risk entities in the United Kingdom."]},
    {"group": "Entity summary", "examples": ["Use TrustVault to summarise entity CUST-000001.", "Use TrustVault to show the FITS containers available for CUST-000001.", "Use TrustVault to show the evidence counts by category and document type for CUST-000001.", "Use TrustVault to show the retention and legal hold summary for CUST-000001."]},
    {"group": "Direct FITS search for selected customer", "examples": ["Use TrustVault to search the FITS container for CUST-000001 for source of wealth evidence.", "Use TrustVault to search CUST-000001 directly for onboarding documentation.", "Use TrustVault to search CUST-000001 for proof of address evidence.", "Use TrustVault to search CUST-000001 for passport or identity evidence.", "Use TrustVault to search CUST-000001 for screening evidence.", "Use TrustVault to search CUST-000001 for correspondence about due diligence."]},
    {"group": "Cross-archive search", "examples": ["Use TrustVault to search the archive for source of funds evidence.", "Use TrustVault to search the archive for onboarding documentation for high risk clients in Guernsey.", "Use TrustVault to find CDD review evidence for high risk customers.", "Use TrustVault to find all screening evidence for Guernsey customers.", "Use TrustVault to search for customer correspondence mentioning missing documents.", "Use TrustVault to find evidence that would help respond to a regulator asking about source of wealth."]},
    {"group": "Query interpretation tests", "examples": ["Use TrustVault to interpret this query but do not execute it: Show me all onboarding documentation for high risk clients in Guernsey.", "Use TrustVault to interpret this query: Which high risk clients in Guernsey are missing proof of address?", "Use TrustVault to interpret this query: Show me source of wealth and screening evidence for high risk customers.", "Use TrustVault to interpret this query: Is the onboarding file complete for CUST-000001?"]},
    {"group": "Execute natural-language queries", "examples": ["Use TrustVault to execute this query: Show me all onboarding documentation for high risk clients in Guernsey.", "Use TrustVault to execute this query: Which customers are missing proof of address?", "Use TrustVault to execute this query for CUST-000001: Show me source of wealth evidence.", "Use TrustVault to execute this query for CUST-000001: What evidence explains where the customer money came from?", "Use TrustVault to execute this query: Find high risk customers with source of funds evidence."]},
    {"group": "Completeness checks", "examples": ["Use TrustVault to check evidence completeness for CUST-000001.", "Use TrustVault to check completeness for high risk customers in Guernsey.", "Use TrustVault to show only incomplete high risk customer files.", "Use TrustVault to identify customers missing mandatory evidence.", "Use TrustVault to check whether the onboarding evidence is complete for CUST-000001."]},
    {"group": "Payload metadata checks", "examples": ["Use TrustVault to show metadata for object OBJ-000001 for entity CUST-000001.", "Use TrustVault to show the filename, document type, category, source system, SHA-256 and safe preview for object OBJ-000001 for CUST-000001.", "Use TrustVault to show the retention metadata and legal hold status for object OBJ-000001 for CUST-000001."]},
]

STOP_WORDS = {"show", "me", "all", "the", "for", "of", "and", "or", "in", "to", "a", "an", "use", "trustvault", "evidence", "documentation", "documents", "client", "clients", "customer", "customers"}
ONBOARDING_CATEGORIES = {"customer_documents", "identity", "proof_of_address", "source_of_wealth", "cdd_review", "communications"}


def _settings_values(db: Session) -> dict[str, Any]:
    return AppSettingsService(db).effective_values()


def _lm_studio_model(values: dict[str, Any], *, purpose: str) -> str:
    query_model = str(values.get("lm_studio_query_model") or "").strip()
    summary_model = str(values.get("lm_studio_model") or "").strip()
    if purpose == "summary":
        return summary_model if ":" in summary_model else query_model or summary_model
    return query_model or summary_model


def _ai_enabled_for_mode(mode: str, values: dict[str, Any]) -> bool:
    if mode == "deterministic":
        return False
    return str(values.get("ai_provider", "none")).lower() in {"lm_studio", "lmstudio"}


def _norm(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _text_norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalise_ai_payload(ai_payload: dict[str, Any], deterministic: StructuredQuery) -> StructuredQuery:
    """Validate AI interpretation against deterministic guardrails and controlled values."""
    det = deterministic.to_dict()
    raw_query = deterministic.raw_query
    lower = raw_query.lower()
    scope = ai_payload.get("scope") if ai_payload.get("scope") in {"archive", "entity"} else det["scope"]
    entity_external_id = ai_payload.get("entity_external_id") or det.get("entity_external_id")
    risk_rating = ai_payload.get("risk_rating") if ai_payload.get("risk_rating") in {"High", "Medium", "Low", None} else det.get("risk_rating")
    jurisdiction = ai_payload.get("jurisdiction") if ai_payload.get("jurisdiction") in {"Guernsey", "Jersey", "United Kingdom", "Isle of Man", "Other", None} else det.get("jurisdiction")
    snapshot_id = ai_payload.get("snapshot_id") or det.get("snapshot_id")
    document_types = ai_payload.get("document_types") if isinstance(ai_payload.get("document_types"), list) else det.get("document_types")
    categories = ai_payload.get("categories") if isinstance(ai_payload.get("categories"), list) else det.get("categories")
    search_terms = ai_payload.get("search_terms") if isinstance(ai_payload.get("search_terms"), list) else det.get("search_terms")
    capability = ai_payload.get("capability") if ai_payload.get("capability") in {"evidence_search", "completeness_check", "entity_discovery", "archive_status", "payload_metadata"} else det.get("capability")

    if "onboarding" in lower or snapshot_id == "ONBOARDING":
        snapshot_id = "ONBOARDING"
        document_types = [item for item in (document_types or []) if str(item).upper() != "ONBOARDING"]
        categories = categories or ["customer_documents"]
        if not search_terms:
            search_terms = ["onboarding documentation"]

    execute_with = ai_payload.get("execute_with") if ai_payload.get("execute_with") in {"direct_fits", "fits_index"} else det.get("execute_with")
    if entity_external_id and capability != "completeness_check":
        execute_with = "direct_fits"
    elif not entity_external_id:
        execute_with = "fits_index"

    return StructuredQuery(
        raw_query=raw_query,
        scope=scope,
        capability=capability,
        entity_external_id=entity_external_id,
        risk_rating=risk_rating,
        jurisdiction=jurisdiction,
        snapshot_id=snapshot_id,
        document_types=document_types or [],
        categories=categories or [],
        search_terms=search_terms or det.get("search_terms") or [raw_query],
        completeness_only=bool(ai_payload.get("completeness_only", det.get("completeness_only"))),
        missing_evidence_type=ai_payload.get("missing_evidence_type") or det.get("missing_evidence_type"),
        execute_with=execute_with,
    )


def _interpret(request: InterpretRequest | ExecuteRequest, db: Session) -> tuple[StructuredQuery, dict[str, Any]]:
    deterministic = TrustVaultQueryInterpreter().interpret(request.query, entity_external_id=request.entity_external_id)
    values = _settings_values(db)
    meta: dict[str, Any] = {
        "mode": request.mode,
        "deterministic_query": deterministic.to_dict(),
        "ai_used": False,
        "ai_provider": values.get("ai_provider"),
        "ai_model": None,
        "ai_base_url": values.get("lm_studio_base_url"),
        "ai_warnings": [],
    }
    if not _ai_enabled_for_mode(request.mode, values):
        if request.mode == "ai":
            meta["ai_warnings"].append("AI mode requested but effective ai_provider is not lm_studio; deterministic interpretation used")
        return deterministic, meta

    ai = LmStudioAiProvider(str(values.get("lm_studio_base_url") or "http://localhost:1234"), model=_lm_studio_model(values, purpose="query"))
    ai_result = ai.interpret_query(request.query, deterministic.to_dict(), context={"entity_external_id": request.entity_external_id})
    meta.update({"ai_used": not ai_result.warnings, "ai_provider": ai_result.provider, "ai_model": ai_result.model, "ai_warnings": ai_result.warnings, "ai_raw": ai_result.data})
    if ai_result.warnings or not ai_result.data:
        return deterministic, meta
    return _normalise_ai_payload(ai_result.data, deterministic), meta


def _summarise_if_requested(request: ExecuteRequest, rows: list[dict[str, Any]], db: Session, execution_source: str, audit_logger: AuditLogger) -> dict[str, Any] | None:
    if not request.include_ai_summary:
        return None
    values = _settings_values(db)
    if str(values.get("ai_provider", "none")).lower() not in {"lm_studio", "lmstudio"}:
        return {"available": False, "warning": "AI summary requested but effective ai_provider is not lm_studio.", "effective_ai_provider": values.get("ai_provider")}
    if not rows:
        return {"available": False, "warning": "No evidence rows were returned to summarise."}
    summary_model = _lm_studio_model(values, purpose="summary")
    ai = LmStudioAiProvider(str(values.get("lm_studio_base_url") or "http://localhost:1234"), model=summary_model)
    evidence_payload = [_safe_summary_row(row) for row in rows[:12]]
    ai_result = ai.summarise_evidence(evidence_payload, question=request.query)
    audit_logger.log(
        AI_SUMMARY_GENERATED,
        raw_query=request.query,
        result_count=len(rows),
        search_source=execution_source,
        ai_used=not ai_result.warnings,
        ai_provider=ai_result.provider,
        ai_model=ai_result.model,
        metadata={"operation": "search_result_summary", "warnings": ai_result.warnings},
    )
    return {
        "available": not ai_result.warnings,
        "summary": ai_result.text,
        "provider": ai_result.provider,
        "model": ai_result.model,
        "warnings": ai_result.warnings,
        "evidence_row_count": min(len(rows), 12),
        "source_of_truth_notice": "The preserved FITS evidence and payload hashes remain the source of truth.",
    }


def _safe_summary_row(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    nested = metadata.get("metadata") if isinstance(metadata.get("metadata"), dict) else {}
    return {
        "entity_external_id": row.get("entity_external_id"),
        "entity_display_name": row.get("entity_display_name"),
        "filename": row.get("filename"),
        "object_type": row.get("object_type"),
        "category": metadata.get("category") or nested.get("category"),
        "document_type": metadata.get("document_type") or nested.get("document_type"),
        "jurisdiction": metadata.get("jurisdiction") or nested.get("jurisdiction"),
        "risk_rating": metadata.get("risk_rating") or nested.get("risk_rating"),
        "source_system": row.get("source_system"),
        "sha256": row.get("sha256"),
        "snippet": str(row.get("snippet") or "")[:600],
        "hdu_name": row.get("hdu_name"),
    }


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not key.startswith("_")}


def _structured_index_search(db: Session, service: TrustVaultFeatureService, structured: StructuredQuery, query: str, limit: int) -> dict[str, Any]:
    customers = service.customers(risk_rating=structured.risk_rating, jurisdiction=structured.jurisdiction)
    entity_filter_applied = bool(structured.risk_rating or structured.jurisdiction)
    allowed_external_ids = {customer["external_id"] for customer in customers}
    diagnostics = {
        "entity_filter_applied": entity_filter_applied,
        "requested_risk_rating": structured.risk_rating,
        "requested_jurisdiction": structured.jurisdiction,
        "matching_entity_count": len(customers),
        "matching_entity_external_ids": sorted(allowed_external_ids)[:100],
        "metadata_filter_applied": bool(structured.categories or structured.document_types or structured.snapshot_id),
        "categories": structured.categories,
        "document_types": structured.document_types,
        "snapshot_id": structured.snapshot_id,
        "search_terms": structured.search_terms,
    }
    if entity_filter_applied and not customers:
        return {"query": query, "entity_id": None, "entity_external_id": None, "container_version_id": None, "result_count": 0, "results": [], "filtered_entity_count": 0, "diagnostics": diagnostics}

    statement = select(FitsIndexEntry).order_by(FitsIndexEntry.created_at.desc()).limit(5000)
    entries = db.scalars(statement).all()
    rows: list[dict[str, Any]] = []
    for entry in entries:
        entity = db.get(Entity, entry.entity_id)
        if entity is None:
            continue
        if entity_filter_applied and entity.external_id not in allowed_external_ids:
            continue
        row = _row_from_index_entry(entry, entity)
        match = _structured_row_match(row, structured)
        if not match["matched"]:
            continue
        row["match_reason"] = match["reason"]
        row["match_score"] = match["score"]
        rows.append(row)

    rows.sort(key=lambda item: (item.get("match_score", 0), item.get("entity_external_id", ""), item.get("filename", "")), reverse=True)
    limited = [_public_row(row) for row in rows[:limit]]
    diagnostics["candidate_index_entry_count"] = len(entries)
    diagnostics["matched_before_limit"] = len(rows)
    return {"query": query, "entity_id": None, "entity_external_id": None, "container_version_id": None, "result_count": len(limited), "results": limited, "filtered_entity_count": len(customers) if entity_filter_applied else None, "diagnostics": diagnostics}


def _row_from_index_entry(entry: FitsIndexEntry, entity: Entity) -> dict[str, Any]:
    metadata = entry.metadata_json or {}
    searchable = "\n".join([entry.filename or "", entry.object_type or "", entry.source_system or "", entry.text_content or "", json.dumps(metadata, default=str)])
    return {
        "entity_id": str(entry.entity_id),
        "entity_external_id": entity.external_id,
        "entity_display_name": entity.display_name,
        "container_version_id": str(entry.container_version_id),
        "evidence_object_id": entry.evidence_object_id,
        "hdu_name": entry.hdu_name,
        "filename": entry.filename,
        "object_type": entry.object_type,
        "source_system": entry.source_system,
        "sha256": entry.sha256,
        "snippet": _snippet(searchable, ""),
        "metadata": metadata,
        "_searchable": searchable,
    }


def _structured_row_match(row: dict[str, Any], structured: StructuredQuery) -> dict[str, Any]:
    metadata = row.get("metadata") or {}
    nested_metadata = metadata.get("metadata") if isinstance(metadata.get("metadata"), dict) else {}
    category = _norm(metadata.get("category") or nested_metadata.get("category") or row.get("object_type"))
    document_type = _norm(metadata.get("document_type") or nested_metadata.get("document_type") or row.get("object_type"))
    object_type = _norm(row.get("object_type"))
    filename = _norm(row.get("filename"))
    searchable = _text_norm(row.get("_searchable"))

    categories = {_norm(item) for item in structured.categories if item}
    document_types = {_norm(item) for item in structured.document_types if item}
    terms = [_text_norm(item) for item in structured.search_terms if item]
    onboarding = structured.snapshot_id == "ONBOARDING" or "onboarding" in _text_norm(structured.raw_query)
    score = 0
    reasons: list[str] = []

    if onboarding:
        allowed_categories = categories or ONBOARDING_CATEGORIES
        if category in allowed_categories or category in ONBOARDING_CATEGORIES:
            score += 70
            reasons.append("onboarding_category")
        elif any(value in filename for value in ["application", "onboarding", "screening", "passport", "address", "wealth", "cdd"]):
            score += 45
            reasons.append("onboarding_filename")
    elif categories:
        if category not in categories:
            return {"matched": False, "score": 0, "reason": "category_filter_not_matched"}
        score += 50
        reasons.append("category")

    if document_types:
        if document_type in document_types or object_type in document_types:
            score += 50
            reasons.append("document_type")
        elif not onboarding:
            return {"matched": False, "score": 0, "reason": "document_type_filter_not_matched"}

    term_match = _term_matches(terms, searchable)
    if term_match:
        score += 30
        reasons.append("text")

    if not categories and not document_types and not onboarding and not term_match:
        return {"matched": False, "score": 0, "reason": "text_not_matched"}

    if score <= 0:
        return {"matched": False, "score": 0, "reason": "no_structured_match"}
    row["snippet"] = _best_snippet(searchable, terms)
    return {"matched": True, "score": score, "reason": ",".join(reasons)}


def _term_matches(terms: list[str], searchable: str) -> bool:
    if not terms:
        return False
    for term in terms:
        if not term:
            continue
        if term in searchable:
            return True
        tokens = [token for token in term.replace("_", " ").split() if token not in STOP_WORDS and len(token) > 2]
        if tokens and all(token in searchable for token in tokens):
            return True
    return False


def _best_snippet(searchable: str, terms: list[str], window: int = 180) -> str:
    for term in terms:
        term = _text_norm(term)
        if term and term in searchable:
            return _snippet(searchable, term, window)
    return searchable[: window * 2]


def _snippet(text: str, normalised_query: str, window: int = 120) -> str:
    if not normalised_query:
        return text[: window * 2]
    index = text.find(normalised_query)
    if index < 0:
        return text[: window * 2]
    start = max(index - window, 0)
    end = min(index + len(normalised_query) + window, len(text))
    return f"{'...' if start > 0 else ''}{text[start:end]}{'...' if end < len(text) else ''}"


@router.get("/archive/status")
def archive_status(db: Session = Depends(get_database)) -> dict[str, Any]:
    return TrustVaultFeatureService(db).archive_status()


@router.get("/scenarios")
def query_scenarios() -> dict[str, Any]:
    return {"scenario_group_count": len(SCENARIOS), "scenarios": SCENARIOS}


@router.post("/interpret")
def interpret_query(request: InterpretRequest, db: Session = Depends(get_database), audit_logger: AuditLogger = Depends(get_audit_logger)) -> dict[str, Any]:
    structured, meta = _interpret(request, db)
    audit_logger.log(
        AI_SUMMARY_GENERATED if meta["ai_used"] else SEARCH_EXECUTED,
        raw_query=request.query,
        structured_query=structured.to_dict(),
        ai_used=meta["ai_used"],
        ai_provider=meta.get("ai_provider"),
        ai_model=meta.get("ai_model"),
        metadata={"operation": "query_interpret", **meta},
    )
    return {"structured_query": structured.to_dict(), "interpretation": meta}


@router.post("/execute")
def execute_query(
    request: ExecuteRequest,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> dict[str, Any]:
    service = TrustVaultFeatureService(db)
    reader = FitsContainerReader(db)
    structured, meta = _interpret(request, db)
    sq = structured.to_dict()
    terms = structured.search_terms or [request.query]
    search_query = " ".join(terms)

    if structured.capability == "completeness_check":
        if structured.entity_external_id:
            result = service.evaluate_completeness(structured.entity_external_id)
        else:
            customers = service.customers(risk_rating=structured.risk_rating, jurisdiction=structured.jurisdiction)
            runs = []
            for customer in customers:
                run = service.evaluate_completeness(customer["external_id"])
                if structured.missing_evidence_type or "incomplete" in request.query.lower():
                    if run["missing_count"] <= 0:
                        continue
                runs.append(run)
            result = {"result_count": len(runs), "results": runs, "diagnostics": {"matching_entity_count": len(customers)}}
        execution_source = "completeness_rules"
        audit_logger.log(
            SEARCH_EXECUTED,
            raw_query=request.query,
            structured_query=sq,
            result_count=result.get("result_count", 1),
            search_source=execution_source,
            ai_used=meta["ai_used"],
            ai_provider=meta.get("ai_provider"),
            ai_model=meta.get("ai_model"),
            metadata={"query_mode": structured.execute_with, "interpretation": meta},
        )
        rows = result.get("results", []) if isinstance(result.get("results"), list) else [result]
        summary = _summarise_if_requested(request, rows, db, execution_source, audit_logger)
        return {"structured_query": sq, "interpretation": meta, "execution_source": execution_source, "result": result, "ai_summary": summary}

    if structured.entity_external_id:
        try:
            result = reader.direct_search(structured.entity_external_id, search_query, request.limit)
            if result.get("result_count", 0) == 0 and (structured.categories or structured.document_types or structured.snapshot_id == "ONBOARDING"):
                result = _structured_index_search(db, service, structured, search_query, request.limit)
                result["entity_external_id"] = structured.entity_external_id
            execution_source = "direct_fits_container"
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    else:
        result = _structured_index_search(db, service, structured, search_query, request.limit)
        execution_source = "fits_index"

    rows = result.get("results", [])
    audit_logger.log(
        SEARCH_EXECUTED,
        raw_query=request.query,
        structured_query=sq,
        result_count=result.get("result_count", 0),
        search_source=execution_source,
        entity_ids=[result["entity_id"]] if result.get("entity_id") else [],
        object_ids=[item.get("evidence_object_id") for item in rows],
        ai_used=meta["ai_used"],
        ai_provider=meta.get("ai_provider"),
        ai_model=meta.get("ai_model"),
        metadata={"query_mode": structured.execute_with, "interpretation": meta, "diagnostics": result.get("diagnostics")},
    )
    summary = _summarise_if_requested(request, rows, db, execution_source, audit_logger)
    return {"structured_query": sq, "interpretation": meta, "execution_source": execution_source, "result": result, "ai_summary": summary}