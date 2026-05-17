from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from trustvault.audit.events import SEARCH_EXECUTED
from trustvault.audit.logger import AuditLogger
from trustvault.api.dependencies import get_audit_logger, get_database
from trustvault.core.feature_services import TrustVaultFeatureService
from trustvault.core.fits_reader import FitsContainerReader
from trustvault.core.query_interpreter import TrustVaultQueryInterpreter

router = APIRouter(prefix="/api/v1/query", tags=["query"])


class InterpretRequest(BaseModel):
    query: str = Field(min_length=1)
    entity_external_id: str | None = None


class ExecuteRequest(BaseModel):
    query: str = Field(min_length=1)
    entity_external_id: str | None = None
    limit: int = Field(default=50, ge=1, le=500)


SCENARIOS: list[dict[str, Any]] = [
    {
        "group": "Archive/status checks",
        "examples": [
            "Use TrustVault to show me the archive status.",
            "Use TrustVault to tell me how many entities, containers and indexed evidence objects are available.",
            "Use TrustVault to show the configured source folder, containers folder, index path and exports folder.",
        ],
    },
    {
        "group": "Entity discovery",
        "examples": [
            "Use TrustVault to list the first 10 entities.",
            "Use TrustVault to list high risk entities.",
            "Use TrustVault to list high risk entities in Guernsey.",
            "Use TrustVault to list medium risk entities in Jersey.",
            "Use TrustVault to list low risk entities in the United Kingdom.",
        ],
    },
    {
        "group": "Entity summary",
        "examples": [
            "Use TrustVault to summarise entity CUST-000001.",
            "Use TrustVault to show the FITS containers available for CUST-000001.",
            "Use TrustVault to show the evidence counts by category and document type for CUST-000001.",
            "Use TrustVault to show the retention and legal hold summary for CUST-000001.",
        ],
    },
    {
        "group": "Direct FITS search for selected customer",
        "examples": [
            "Use TrustVault to search the FITS container for CUST-000001 for source of wealth evidence.",
            "Use TrustVault to search CUST-000001 directly for onboarding documentation.",
            "Use TrustVault to search CUST-000001 for proof of address evidence.",
            "Use TrustVault to search CUST-000001 for passport or identity evidence.",
            "Use TrustVault to search CUST-000001 for screening evidence.",
            "Use TrustVault to search CUST-000001 for correspondence about due diligence.",
        ],
    },
    {
        "group": "Cross-archive search",
        "examples": [
            "Use TrustVault to search the archive for source of funds evidence.",
            "Use TrustVault to search the archive for onboarding documentation for high risk clients in Guernsey.",
            "Use TrustVault to find CDD review evidence for high risk customers.",
            "Use TrustVault to find all screening evidence for Guernsey customers.",
            "Use TrustVault to search for customer correspondence mentioning missing documents.",
            "Use TrustVault to find evidence that would help respond to a regulator asking about source of wealth.",
        ],
    },
    {
        "group": "Query interpretation tests",
        "examples": [
            "Use TrustVault to interpret this query but do not execute it: Show me all onboarding documentation for high risk clients in Guernsey.",
            "Use TrustVault to interpret this query: Which high risk clients in Guernsey are missing proof of address?",
            "Use TrustVault to interpret this query: Show me source of wealth and screening evidence for high risk customers.",
            "Use TrustVault to interpret this query: Is the onboarding file complete for CUST-000001?",
        ],
    },
    {
        "group": "Execute natural-language queries",
        "examples": [
            "Use TrustVault to execute this query: Show me all onboarding documentation for high risk clients in Guernsey.",
            "Use TrustVault to execute this query: Which customers are missing proof of address?",
            "Use TrustVault to execute this query for CUST-000001: Show me source of wealth evidence.",
            "Use TrustVault to execute this query for CUST-000001: What evidence explains where the customer money came from?",
            "Use TrustVault to execute this query: Find high risk customers with source of funds evidence.",
        ],
    },
    {
        "group": "Completeness checks",
        "examples": [
            "Use TrustVault to check evidence completeness for CUST-000001.",
            "Use TrustVault to check completeness for high risk customers in Guernsey.",
            "Use TrustVault to show only incomplete high risk customer files.",
            "Use TrustVault to identify customers missing mandatory evidence.",
            "Use TrustVault to check whether the onboarding evidence is complete for CUST-000001.",
        ],
    },
    {
        "group": "Payload metadata checks",
        "examples": [
            "Use TrustVault to show metadata for object OBJ-000001 for entity CUST-000001.",
            "Use TrustVault to show the filename, document type, category, source system, SHA-256 and safe preview for object OBJ-000001 for CUST-000001.",
            "Use TrustVault to show the retention metadata and legal hold status for object OBJ-000001 for CUST-000001.",
        ],
    },
]


@router.get("/archive/status")
def archive_status(db: Session = Depends(get_database)) -> dict[str, Any]:
    return TrustVaultFeatureService(db).archive_status()


@router.get("/scenarios")
def query_scenarios() -> dict[str, Any]:
    return {"scenario_group_count": len(SCENARIOS), "scenarios": SCENARIOS}


@router.post("/interpret")
def interpret_query(request: InterpretRequest) -> dict[str, Any]:
    structured = TrustVaultQueryInterpreter().interpret(
        request.query,
        entity_external_id=request.entity_external_id,
    )
    return {"structured_query": structured.to_dict()}


@router.post("/execute")
def execute_query(
    request: ExecuteRequest,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> dict[str, Any]:
    service = TrustVaultFeatureService(db)
    reader = FitsContainerReader(db)
    structured = TrustVaultQueryInterpreter().interpret(
        request.query,
        entity_external_id=request.entity_external_id,
        execute=True,
    )
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
        return {"structured_query": sq, "execution_source": "completeness_rules", "result": result}

    if structured.entity_external_id:
        try:
            result = reader.direct_search(structured.entity_external_id, search_query, request.limit)
            execution_source = "direct_fits_container"
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    else:
        entity_filter = None
        if structured.risk_rating or structured.jurisdiction:
            customers = service.customers(risk_rating=structured.risk_rating, jurisdiction=structured.jurisdiction)
            entity_ids = {customer["external_id"] for customer in customers}
            broad = reader.index_search(search_query, None, request.limit * 5)
            filtered = [row for row in broad["results"] if row.get("entity_external_id") in entity_ids][: request.limit]
            result = {**broad, "result_count": len(filtered), "results": filtered, "filtered_entity_count": len(entity_ids)}
        else:
            result = reader.index_search(search_query, entity_filter, request.limit)
        execution_source = "fits_index"

    audit_logger.log(
        SEARCH_EXECUTED,
        raw_query=request.query,
        structured_query=sq,
        result_count=result.get("result_count", 0),
        search_source=execution_source,
        entity_ids=[result["entity_id"]] if result.get("entity_id") else [],
        object_ids=[item.get("evidence_object_id") for item in result.get("results", [])],
        metadata={"query_mode": structured.execute_with},
    )
    return {"structured_query": sq, "execution_source": execution_source, "result": result}
