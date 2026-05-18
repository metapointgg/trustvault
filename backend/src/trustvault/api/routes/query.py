from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from trustvault.ai.lm_studio import LmStudioAiProvider
from trustvault.audit.events import AI_SUMMARY_GENERATED, SEARCH_EXECUTED
from trustvault.audit.logger import AuditLogger
from trustvault.api.dependencies import get_audit_logger, get_database
from trustvault.core.feature_services import TrustVaultFeatureService
from trustvault.core.fits_reader import FitsContainerReader
from trustvault.core.query_interpreter import StructuredQuery, TrustVaultQueryInterpreter
from trustvault.settings import get_settings

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


def _ai_enabled_for_mode(mode: str) -> bool:
    settings = get_settings()
    if mode == "deterministic":
        return False
    return settings.ai_provider.lower() in {"lm_studio", "lmstudio"}


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


def _interpret(request: InterpretRequest | ExecuteRequest) -> tuple[StructuredQuery, dict[str, Any]]:
    deterministic = TrustVaultQueryInterpreter().interpret(request.query, entity_external_id=request.entity_external_id)
    meta: dict[str, Any] = {
        "mode": request.mode,
        "deterministic_query": deterministic.to_dict(),
        "ai_used": False,
        "ai_provider": None,
        "ai_model": None,
        "ai_warnings": [],
    }
    if not _ai_enabled_for_mode(request.mode):
        if request.mode == "ai":
            meta["ai_warnings"].append("AI mode requested but TRUSTVAULT_AI_PROVIDER is not lm_studio; deterministic interpretation used")
        return deterministic, meta

    settings = get_settings()
    ai = LmStudioAiProvider(settings.lm_studio_base_url, model=settings.lm_studio_query_model)
    ai_result = ai.interpret_query(request.query, deterministic.to_dict(), context={"entity_external_id": request.entity_external_id})
    meta.update({
        "ai_used": not ai_result.warnings,
        "ai_provider": ai_result.provider,
        "ai_model": ai_result.model,
        "ai_warnings": ai_result.warnings,
        "ai_raw": ai_result.data,
    })
    if ai_result.warnings or not ai_result.data:
        return deterministic, meta
    return _normalise_ai_payload(ai_result.data, deterministic), meta


def _summarise_if_requested(request: ExecuteRequest, rows: list[dict[str, Any]], meta: dict[str, Any], execution_source: str, audit_logger: AuditLogger) -> dict[str, Any] | None:
    if not request.include_ai_summary:
        return None
    settings = get_settings()
    if settings.ai_provider.lower() not in {"lm_studio", "lmstudio"}:
        return {
            "available": False,
            "warning": "AI summary requested but TRUSTVAULT_AI_PROVIDER is not lm_studio.",
        }
    if not rows:
        return {"available": False, "warning": "No evidence rows were returned to summarise."}
    ai = LmStudioAiProvider(settings.lm_studio_base_url, model=settings.lm_studio_model)
    evidence_payload = [
        {
            "entity_external_id": row.get("entity_external_id"),
            "entity_display_name": row.get("entity_display_name"),
            "filename": row.get("filename"),
            "object_type": row.get("object_type"),
            "source_system": row.get("source_system"),
            "sha256": row.get("sha256"),
            "snippet": row.get("snippet"),
            "hdu_name": row.get("hdu_name"),
        }
        for row in rows[:25]
    ]
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
        "evidence_row_count": min(len(rows), 25),
        "source_of_truth_notice": "The preserved FITS evidence and payload hashes remain the source of truth.",
    }


@router.get("/archive/status")
def archive_status(db: Session = Depends(get_database)) -> dict[str, Any]:
    return TrustVaultFeatureService(db).archive_status()


@router.get("/scenarios")
def query_scenarios() -> dict[str, Any]:
    return {"scenario_group_count": len(SCENARIOS), "scenarios": SCENARIOS}


@router.post("/interpret")
def interpret_query(request: InterpretRequest, audit_logger: AuditLogger = Depends(get_audit_logger)) -> dict[str, Any]:
    structured, meta = _interpret(request)
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
    structured, meta = _interpret(request)
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
            result = {"result_count": len(runs), "results": runs}
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
        summary = _summarise_if_requested(request, result.get("results", []) if isinstance(result.get("results"), list) else [result], meta, execution_source, audit_logger)
        return {"structured_query": sq, "interpretation": meta, "execution_source": execution_source, "result": result, "ai_summary": summary}

    if structured.entity_external_id:
        try:
            result = reader.direct_search(structured.entity_external_id, search_query, request.limit)
            execution_source = "direct_fits_container"
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    else:
        if structured.risk_rating or structured.jurisdiction:
            customers = service.customers(risk_rating=structured.risk_rating, jurisdiction=structured.jurisdiction)
            entity_ids = {customer["external_id"] for customer in customers}
            broad = reader.index_search(search_query, None, request.limit * 5)
            filtered = [row for row in broad["results"] if row.get("entity_external_id") in entity_ids][: request.limit]
            result = {**broad, "result_count": len(filtered), "results": filtered, "filtered_entity_count": len(entity_ids)}
        else:
            result = reader.index_search(search_query, None, request.limit)
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
        metadata={"query_mode": structured.execute_with, "interpretation": meta},
    )
    summary = _summarise_if_requested(request, rows, meta, execution_source, audit_logger)
    return {"structured_query": sq, "interpretation": meta, "execution_source": execution_source, "result": result, "ai_summary": summary}