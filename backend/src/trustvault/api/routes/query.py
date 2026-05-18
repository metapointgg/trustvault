import json
import re
from collections import Counter
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
from trustvault.db.models import Entity, EntityContainerVersion, FitsIndexEntry

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

STOP_WORDS = {
    "show", "me", "all", "the", "for", "of", "and", "or", "in", "to", "a", "an", "use", "trustvault",
    "evidence", "documentation", "documents", "document", "client", "clients", "customer", "customers", "who", "are", "is", "with",
}
ONBOARDING_CATEGORIES = {"customer_documents", "identity", "proof_of_address", "source_of_wealth", "cdd_review", "communications"}
NON_AI_SUMMARY_SOURCES = {"entity_metadata", "archive_status", "entity_summary", "payload_metadata", "completeness_rules"}
DETERMINISTIC_AUTO_CAPABILITIES = {"archive_status", "entity_discovery", "entity_summary", "payload_metadata", "completeness_check"}


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


def _auto_should_skip_ai_interpretation(structured: StructuredQuery) -> bool:
    return structured.capability in DETERMINISTIC_AUTO_CAPABILITIES


def _norm(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _text_norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _unique(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        if value and value not in output:
            output.append(value)
    return output


def _expand_query_filters(categories: list[str], document_types: list[str], search_terms: list[str]) -> tuple[list[str], list[str], list[str]]:
    cats = list(categories or [])
    docs = list(document_types or [])
    terms = list(search_terms or [])
    joined = " ".join(cats + docs + terms).lower()

    if "source_of_funds" in joined or "source of funds" in joined:
        cats.extend(["source_of_funds", "source_of_wealth"])
        docs.extend(["source_of_funds", "source_of_wealth"])
        terms.extend(["source of funds", "source of wealth", "funds", "proceeds"])
    if "source_of_wealth" in joined or "source of wealth" in joined:
        cats.extend(["source_of_wealth"])
        docs.extend(["source_of_wealth"])
        terms.extend(["source of wealth", "wealth", "proceeds"])
    if "screening" in joined or "pep" in joined or "sanctions" in joined:
        cats.extend(["customer_documents", "cdd_review"])
        docs.extend(["screening", "cdd_risk_review"])
        terms.extend(["screening", "pep", "sanctions", "adverse media"])
    if "correspondence" in joined or "email" in joined or "missing documents" in joined:
        cats.extend(["communications"])
        docs.extend(["email"])
        if "missing documents" in joined:
            terms.extend(["missing documents", "missing", "correspondence"])
    return _unique(cats), _unique(docs), _unique(terms)


def _structured_with_filters(
    structured: StructuredQuery,
    categories: list[str],
    document_types: list[str],
    search_terms: list[str],
    capability: str | None = None,
    completeness_only: bool | None = None,
    missing_evidence_type: str | None = None,
) -> StructuredQuery:
    return StructuredQuery(
        raw_query=structured.raw_query,
        scope=structured.scope,
        capability=capability or structured.capability,
        entity_external_id=structured.entity_external_id,
        risk_rating=structured.risk_rating,
        jurisdiction=structured.jurisdiction,
        snapshot_id=structured.snapshot_id,
        document_types=document_types,
        categories=categories,
        search_terms=search_terms,
        completeness_only=structured.completeness_only if completeness_only is None else completeness_only,
        missing_evidence_type=structured.missing_evidence_type if missing_evidence_type is None else missing_evidence_type,
        execute_with=structured.execute_with,
    )


def _normalise_ai_payload(ai_payload: dict[str, Any], deterministic: StructuredQuery) -> StructuredQuery:
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
    ai_capability = ai_payload.get("capability")
    capability = ai_capability if ai_capability in {"evidence_search", "completeness_check", "entity_discovery", "archive_status", "entity_summary", "payload_metadata"} else det.get("capability")

    if det.get("capability") in {"archive_status", "entity_summary", "payload_metadata", "completeness_check"}:
        capability = det.get("capability")
    if det.get("capability") == "entity_discovery" and not snapshot_id and not document_types and not categories:
        capability = "entity_discovery"
        search_terms = []
    if det.get("capability") == "evidence_search" and ("correspondence" in lower or "email" in lower):
        capability = "evidence_search"

    if "onboarding" in lower or snapshot_id == "ONBOARDING":
        snapshot_id = "ONBOARDING"
        document_types = [item for item in (document_types or []) if str(item).upper() != "ONBOARDING"]
        categories = categories or ["customer_documents"]
        if not search_terms:
            search_terms = ["onboarding documentation"]

    categories, document_types, search_terms = _expand_query_filters(categories or [], document_types or [], search_terms or [])

    execute_with = ai_payload.get("execute_with") if ai_payload.get("execute_with") in {"direct_fits", "fits_index"} else det.get("execute_with")
    if capability in {"entity_discovery", "archive_status", "entity_summary", "payload_metadata"}:
        execute_with = "fits_index"
    elif entity_external_id and capability != "completeness_check":
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
        document_types=document_types,
        categories=categories,
        search_terms=search_terms or ([] if capability == "entity_discovery" else det.get("search_terms") or [raw_query]),
        completeness_only=bool(ai_payload.get("completeness_only", det.get("completeness_only"))) if capability == "completeness_check" else False,
        missing_evidence_type=(ai_payload.get("missing_evidence_type") or det.get("missing_evidence_type")) if capability == "completeness_check" else None,
        execute_with=execute_with,
    )


def _interpret(request: InterpretRequest | ExecuteRequest, db: Session) -> tuple[StructuredQuery, dict[str, Any]]:
    deterministic = TrustVaultQueryInterpreter().interpret(request.query, entity_external_id=request.entity_external_id)
    categories, document_types, search_terms = _expand_query_filters(deterministic.categories or [], deterministic.document_types or [], deterministic.search_terms or [])
    deterministic = _structured_with_filters(deterministic, categories, document_types, search_terms)
    values = _settings_values(db)
    meta: dict[str, Any] = {
        "mode": request.mode,
        "deterministic_query": deterministic.to_dict(),
        "ai_used": False,
        "ai_provider": values.get("ai_provider"),
        "ai_model": None,
        "ai_base_url": values.get("lm_studio_base_url"),
        "ai_warnings": [],
        "ai_skipped": False,
        "ai_skip_reason": None,
    }
    if not _ai_enabled_for_mode(request.mode, values):
        if request.mode == "ai":
            meta["ai_warnings"].append("AI mode requested but effective ai_provider is not lm_studio; deterministic interpretation used")
        return deterministic, meta

    if request.mode == "auto" and _auto_should_skip_ai_interpretation(deterministic):
        meta["ai_skipped"] = True
        meta["ai_skip_reason"] = f"auto mode used deterministic {deterministic.capability} interpretation"
        return deterministic, meta

    ai = LmStudioAiProvider(str(values.get("lm_studio_base_url") or "http://localhost:1234"), model=_lm_studio_model(values, purpose="query"))
    ai_result = ai.interpret_query(request.query, deterministic.to_dict(), context={"entity_external_id": request.entity_external_id})
    meta.update({"ai_used": not ai_result.warnings, "ai_provider": ai_result.provider, "ai_model": ai_result.model, "ai_warnings": ai_result.warnings, "ai_raw": ai_result.data})
    if ai_result.warnings or not ai_result.data:
        return deterministic, meta
    return _normalise_ai_payload(ai_result.data, deterministic), meta


def _deterministic_rows_summary(rows: list[dict[str, Any]], *, title: str = "Returned rows") -> str:
    lines = [f"{title}: {len(rows)}.", ""]
    for row in rows:
        label = row.get("filename") or row.get("entity_external_id") or row.get("key") or row.get("summary") or "row"
        details = []
        for key in ("entity_external_id", "category", "document_type", "source_system", "sha256", "retention_until", "legal_hold_status"):
            if row.get(key) not in (None, ""):
                details.append(f"{key}={row.get(key)}")
        lines.append(f"- {label}" + (f"; {'; '.join(details)}" if details else ""))
    lines.extend(["", "The preserved FITS evidence and payload hashes remain the source of truth."])
    return "\n".join(lines)


def _summary_should_use_ai(request: ExecuteRequest, execution_source: str) -> bool:
    if request.mode != "ai":
        return False
    return execution_source not in NON_AI_SUMMARY_SOURCES


def _summarise_if_requested(request: ExecuteRequest, rows: list[dict[str, Any]], db: Session, execution_source: str, audit_logger: AuditLogger) -> dict[str, Any] | None:
    if not request.include_ai_summary:
        return None
    if not rows:
        return {"available": False, "warning": "No rows were returned to summarise."}
    if not _summary_should_use_ai(request, execution_source):
        summary = _deterministic_entity_summary(rows) if execution_source == "entity_metadata" else _deterministic_rows_summary(rows, title=execution_source)
        audit_logger.log(
            AI_SUMMARY_GENERATED,
            raw_query=request.query,
            result_count=len(rows),
            search_source=execution_source,
            ai_used=False,
            ai_provider="trustvault",
            ai_model=f"deterministic_{execution_source}_summary",
            metadata={"operation": f"deterministic_{execution_source}_summary", "row_count": len(rows), "request_mode": request.mode},
        )
        return {
            "available": True,
            "summary": summary,
            "provider": "trustvault",
            "model": f"deterministic_{execution_source}_summary",
            "warnings": [],
            "evidence_row_count": len(rows),
            "source_of_truth_notice": "The preserved FITS evidence and payload hashes remain the source of truth.",
            "ai_used_for_summary": False,
        }

    values = _settings_values(db)
    if str(values.get("ai_provider", "none")).lower() not in {"lm_studio", "lmstudio"}:
        return {"available": False, "warning": "AI summary requested but effective ai_provider is not lm_studio.", "effective_ai_provider": values.get("ai_provider")}
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
        "ai_used_for_summary": not ai_result.warnings,
    }


def _deterministic_entity_summary(rows: list[dict[str, Any]]) -> str:
    risk_counts = Counter(str(row.get("risk_rating") or "Unknown") for row in rows)
    jurisdiction_counts = Counter(str(row.get("jurisdiction") or "Unknown") for row in rows)
    total_evidence_objects = sum(int(row.get("evidence_object_count") or 0) for row in rows)
    lines = [
        f"Returned {len(rows)} customer entit{'y' if len(rows) == 1 else 'ies'}.",
        "Risk ratings: " + ", ".join(f"{key}: {value}" for key, value in sorted(risk_counts.items())),
        "Jurisdictions: " + ", ".join(f"{key}: {value}" for key, value in sorted(jurisdiction_counts.items())),
        f"Total indexed evidence objects across returned customers: {total_evidence_objects}.",
        "",
        "Customers:",
    ]
    for row in rows:
        lines.append(
            "- "
            f"{row.get('entity_external_id') or row.get('external_id')}: "
            f"{row.get('entity_display_name') or row.get('display_name') or '-'}; "
            f"risk={row.get('risk_rating') or '-'}; "
            f"jurisdiction={row.get('jurisdiction') or '-'}; "
            f"evidence_objects={row.get('evidence_object_count') or 0}; "
            f"fits_current={bool(row.get('has_current_fits_container'))}"
        )
    lines.extend(["", "The preserved FITS evidence and payload hashes remain the source of truth."])
    return "\n".join(lines)


def _safe_summary_row(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    nested = metadata.get("metadata") if isinstance(metadata.get("metadata"), dict) else {}
    text_preview = nested.get("search_text") or metadata.get("search_text") or row.get("text_content") or row.get("snippet") or ""
    return {
        "entity_external_id": row.get("entity_external_id") or row.get("external_id"),
        "entity_display_name": row.get("entity_display_name") or row.get("display_name"),
        "filename": row.get("filename"),
        "object_type": row.get("object_type") or row.get("entity_type"),
        "category": metadata.get("category") or nested.get("category") or row.get("category"),
        "document_type": metadata.get("document_type") or nested.get("document_type") or row.get("document_type"),
        "jurisdiction": row.get("jurisdiction") or metadata.get("jurisdiction") or nested.get("jurisdiction"),
        "risk_rating": row.get("risk_rating") or metadata.get("risk_rating") or nested.get("risk_rating"),
        "retention_class": metadata.get("retention_class") or nested.get("retention_class"),
        "legal_hold_status": metadata.get("legal_hold_status") or nested.get("legal_hold_status"),
        "source_system": row.get("source_system"),
        "sha256": row.get("sha256"),
        "text_preview": str(text_preview)[:1000],
        "hdu_name": row.get("hdu_name"),
    }


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not key.startswith("_")}


def _metadata_value(row: dict[str, Any], key: str) -> Any:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    nested = metadata.get("metadata") if isinstance(metadata.get("metadata"), dict) else {}
    if row.get(key) not in (None, ""):
        return row.get(key)
    if metadata.get(key) not in (None, ""):
        return metadata.get(key)
    return nested.get(key)


def _customer_row(customer: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_id": customer.get("id"),
        "entity_external_id": customer.get("external_id"),
        "entity_display_name": customer.get("display_name"),
        "external_id": customer.get("external_id"),
        "display_name": customer.get("display_name"),
        "entity_type": customer.get("entity_type"),
        "status": customer.get("status"),
        "risk_rating": customer.get("risk_rating"),
        "jurisdiction": customer.get("jurisdiction"),
        "evidence_object_count": customer.get("evidence_object_count"),
        "has_current_fits_container": customer.get("has_current_fits_container"),
        "current_container_version_id": customer.get("current_container_version_id"),
        "current_container_version_number": customer.get("current_container_version_number"),
        "current_container_storage_uri": customer.get("current_container_storage_uri"),
        "metadata_json": customer.get("metadata_json"),
    }


def _requested_limit(raw_query: str, fallback: int) -> int:
    lower = raw_query.lower()
    match = re.search(r"\b(?:first|top|list)\s+(\d{1,3})\b", lower)
    if match:
        return max(1, min(int(match.group(1)), fallback))
    return fallback


def _entity_discovery_result(service: TrustVaultFeatureService, structured: StructuredQuery, limit: int) -> dict[str, Any]:
    effective_limit = _requested_limit(structured.raw_query, limit)
    customers = service.customers(risk_rating=structured.risk_rating, jurisdiction=structured.jurisdiction, limit=effective_limit)
    rows = [_customer_row(customer) for customer in customers]
    return {
        "query": structured.raw_query,
        "entity_id": None,
        "entity_external_id": None,
        "container_version_id": None,
        "result_count": len(rows),
        "results": rows,
        "filtered_entity_count": len(rows),
        "diagnostics": {
            "entity_filter_applied": bool(structured.risk_rating or structured.jurisdiction),
            "requested_risk_rating": structured.risk_rating,
            "requested_jurisdiction": structured.jurisdiction,
            "requested_limit": effective_limit,
            "matching_entity_count": len(rows),
            "matching_entity_external_ids": [row["entity_external_id"] for row in rows],
            "execution_mode": "entity_discovery",
            "evidence_text_filter_applied": False,
        },
    }


def _archive_status_result(service: TrustVaultFeatureService, structured: StructuredQuery) -> dict[str, Any]:
    status = service.archive_status()
    rows = [
        {"key": "entity_count", "value": status.get("entity_count")},
        {"key": "current_fits_container_count", "value": status.get("current_fits_container_count")},
        {"key": "evidence_object_count", "value": status.get("evidence_object_count")},
        {"key": "fits_index_entry_count", "value": status.get("fits_index_entry_count")},
        {"key": "source_folder", "value": status.get("configuration", {}).get("source_folder")},
        {"key": "containers_folder", "value": status.get("configuration", {}).get("containers_folder")},
        {"key": "index_path", "value": status.get("configuration", {}).get("index_path")},
        {"key": "exports_folder", "value": status.get("configuration", {}).get("exports_folder")},
    ]
    return {
        "query": structured.raw_query,
        "result_count": len(rows),
        "results": rows,
        "archive_status": status,
        "diagnostics": {"execution_mode": "archive_status", "evidence_text_filter_applied": False},
    }


def _entity_summary_result(db: Session, service: TrustVaultFeatureService, structured: StructuredQuery) -> dict[str, Any]:
    if not structured.entity_external_id:
        return {"query": structured.raw_query, "result_count": 0, "results": [], "diagnostics": {"error": "entity_external_id_required"}}
    lower = structured.raw_query.lower()
    summary = service.entity_evidence_summary(structured.entity_external_id)
    entity = summary.get("entity", {})
    rows: list[dict[str, Any]] = []
    if "fits container" in lower:
        current_id = entity.get("current_container_version_id")
        if current_id:
            version = db.get(EntityContainerVersion, current_id)
            rows.append({
                "entity_external_id": structured.entity_external_id,
                "container_version_id": current_id,
                "version_number": entity.get("current_container_version_number"),
                "status": version.status if version else "current",
                "storage_uri": entity.get("current_container_storage_uri"),
                "sha256": version.sha256 if version else None,
                "size_bytes": version.size_bytes if version else None,
                "hdu_count": len(version.manifest_json.get("hdu_names", [])) if version else None,
            })
    elif "retention" in lower or "legal hold" in lower:
        report = service.retention_report(structured.entity_external_id)
        rows = report.get("entities", [{}])[0].get("evidence", [])
    elif "counts" in lower or "category" in lower or "document type" in lower:
        for category, count in sorted(summary.get("counts_by_category", {}).items()):
            rows.append({"entity_external_id": structured.entity_external_id, "summary_type": "category_count", "category": category, "count": count})
        for document_type, count in sorted(summary.get("counts_by_document_type", {}).items()):
            rows.append({"entity_external_id": structured.entity_external_id, "summary_type": "document_type_count", "document_type": document_type, "count": count})
    else:
        rows = [{**entity, "evidence_count": summary.get("evidence_count"), "counts_by_category": summary.get("counts_by_category"), "counts_by_document_type": summary.get("counts_by_document_type")}]
    return {
        "query": structured.raw_query,
        "entity_external_id": structured.entity_external_id,
        "result_count": len(rows),
        "results": rows,
        "entity_summary": summary,
        "diagnostics": {"execution_mode": "entity_summary", "evidence_text_filter_applied": False},
    }


def _payload_metadata_result(db: Session, structured: StructuredQuery) -> dict[str, Any]:
    match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", structured.raw_query.lower())
    object_id = match.group(0) if match else None
    rows: list[dict[str, Any]] = []
    if object_id:
        entries = db.scalars(select(FitsIndexEntry).where(FitsIndexEntry.evidence_object_id == object_id)).all()
        for entry in entries:
            entity = db.get(Entity, entry.entity_id)
            if structured.entity_external_id and entity and entity.external_id != structured.entity_external_id:
                continue
            rows.append(_public_row(_row_from_index_entry(entry, entity)))
    return {
        "query": structured.raw_query,
        "entity_external_id": structured.entity_external_id,
        "object_id": object_id,
        "result_count": len(rows),
        "results": rows,
        "diagnostics": {"execution_mode": "payload_metadata", "evidence_text_filter_applied": False},
    }


def _row_matches_cohort(entity: Entity, row: dict[str, Any], structured: StructuredQuery, allowed_external_ids: set[str]) -> tuple[bool, str]:
    if structured.entity_external_id and entity.external_id != structured.entity_external_id:
        return False, "entity_external_id_not_matched"
    if not structured.risk_rating and not structured.jurisdiction:
        return True, "no_cohort_filter"
    if entity.external_id in allowed_external_ids:
        return True, "entity_metadata"
    risk_ok = not structured.risk_rating or _norm(_metadata_value(row, "risk_rating")) == _norm(structured.risk_rating)
    jurisdiction_ok = not structured.jurisdiction or _norm(_metadata_value(row, "jurisdiction")) == _norm(structured.jurisdiction)
    if risk_ok and jurisdiction_ok:
        return True, "evidence_metadata"
    return False, "cohort_filter_not_matched"


def _structured_index_search(db: Session, service: TrustVaultFeatureService, structured: StructuredQuery, query: str, limit: int) -> dict[str, Any]:
    customers = service.customers(risk_rating=structured.risk_rating, jurisdiction=structured.jurisdiction)
    entity_filter_applied = bool(structured.entity_external_id or structured.risk_rating or structured.jurisdiction)
    allowed_external_ids = {customer["external_id"] for customer in customers}
    diagnostics = {
        "entity_filter_applied": entity_filter_applied,
        "requested_entity_external_id": structured.entity_external_id,
        "requested_risk_rating": structured.risk_rating,
        "requested_jurisdiction": structured.jurisdiction,
        "matching_entity_count": len(customers),
        "matching_entity_external_ids": sorted(allowed_external_ids)[:100],
        "matching_evidence_metadata_entity_count": 0,
        "matching_evidence_metadata_external_ids": [],
        "cohort_rejected_index_entry_count": 0,
        "metadata_filter_applied": bool(structured.categories or structured.document_types or structured.snapshot_id),
        "categories": structured.categories,
        "document_types": structured.document_types,
        "snapshot_id": structured.snapshot_id,
        "search_terms": structured.search_terms,
    }

    entries = db.scalars(select(FitsIndexEntry).order_by(FitsIndexEntry.created_at.desc()).limit(5000)).all()
    rows: list[dict[str, Any]] = []
    matched_by_evidence_metadata: set[str] = set()
    matched_by_entity_metadata: set[str] = set()

    for entry in entries:
        entity = db.get(Entity, entry.entity_id)
        if entity is None:
            continue
        row = _row_from_index_entry(entry, entity)
        cohort_ok, cohort_source = _row_matches_cohort(entity, row, structured, allowed_external_ids)
        if not cohort_ok:
            diagnostics["cohort_rejected_index_entry_count"] += 1
            continue
        if cohort_source == "entity_metadata":
            matched_by_entity_metadata.add(entity.external_id)
        elif cohort_source == "evidence_metadata":
            matched_by_evidence_metadata.add(entity.external_id)
        match = _structured_row_match(row, structured)
        if not match["matched"]:
            continue
        row["match_reason"] = match["reason"]
        row["match_score"] = match["score"]
        row["cohort_match_source"] = cohort_source
        rows.append(row)

    rows.sort(key=lambda item: (item.get("match_score", 0), item.get("entity_external_id", ""), item.get("filename", "")), reverse=True)
    limited = [_public_row(row) for row in rows[:limit]]
    effective_entity_ids = {row["entity_external_id"] for row in rows if row.get("entity_external_id")}
    diagnostics["candidate_index_entry_count"] = len(entries)
    diagnostics["matched_before_limit"] = len(rows)
    diagnostics["matching_evidence_metadata_entity_count"] = len(matched_by_evidence_metadata)
    diagnostics["matching_evidence_metadata_external_ids"] = sorted(matched_by_evidence_metadata)[:100]
    diagnostics["matching_entity_metadata_after_index_scan_count"] = len(matched_by_entity_metadata)
    diagnostics["effective_matching_entity_count"] = len(effective_entity_ids)
    diagnostics["effective_matching_entity_external_ids"] = sorted(effective_entity_ids)[:100]
    return {
        "query": query,
        "entity_id": None,
        "entity_external_id": structured.entity_external_id,
        "container_version_id": None,
        "result_count": len(limited),
        "results": limited,
        "filtered_entity_count": len(effective_entity_ids) if entity_filter_applied else None,
        "diagnostics": diagnostics,
    }


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
        "snippet": _snippet(search_text or searchable, ""),
        "metadata": metadata,
        "text_content": search_text,
        "risk_rating": metadata.get("risk_rating") or nested.get("risk_rating"),
        "jurisdiction": metadata.get("jurisdiction") or nested.get("jurisdiction"),
        "category": metadata.get("category") or nested.get("category"),
        "document_type": metadata.get("document_type") or nested.get("document_type"),
        "retention_class": metadata.get("retention_class") or nested.get("retention_class"),
        "retention_until": metadata.get("retention_until") or nested.get("retention_until"),
        "legal_hold_status": metadata.get("legal_hold_status") or nested.get("legal_hold_status"),
        "_searchable": searchable,
    }


def _structured_row_match(row: dict[str, Any], structured: StructuredQuery) -> dict[str, Any]:
    metadata = row.get("metadata") or {}
    nested_metadata = metadata.get("metadata") if isinstance(metadata.get("metadata"), dict) else {}
    category = _norm(metadata.get("category") or nested_metadata.get("category") or row.get("category") or row.get("object_type"))
    document_type = _norm(metadata.get("document_type") or nested_metadata.get("document_type") or row.get("document_type") or row.get("object_type"))
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
        if category in categories:
            score += 50
            reasons.append("category")
        elif not document_types and not terms:
            return {"matched": False, "score": 0, "reason": "category_filter_not_matched"}

    if document_types:
        if document_type in document_types or object_type in document_types:
            score += 50
            reasons.append("document_type")
        elif not categories and not terms and not onboarding:
            return {"matched": False, "score": 0, "reason": "document_type_filter_not_matched"}

    term_match = _term_matches(terms, searchable)
    if term_match:
        score += 30
        reasons.append("text")

    if categories or document_types:
        if score <= 0:
            return {"matched": False, "score": 0, "reason": "metadata_or_text_filter_not_matched"}
    elif not onboarding and not term_match:
        return {"matched": False, "score": 0, "reason": "text_not_matched"}

    row["snippet"] = _best_snippet(row.get("text_content") or searchable, terms)
    return {"matched": True, "score": score, "reason": ",".join(reasons) or "text"}


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
        if term and term in _text_norm(searchable):
            index = _text_norm(searchable).find(term)
            start = max(index - window, 0)
            end = min(index + len(term) + window, len(searchable))
            return f"{'...' if start > 0 else ''}{searchable[start:end]}{'...' if end < len(searchable) else ''}"
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


def _audit_and_return(
    *,
    request: ExecuteRequest,
    structured: StructuredQuery,
    meta: dict[str, Any],
    result: dict[str, Any],
    execution_source: str,
    audit_logger: AuditLogger,
    db: Session,
) -> dict[str, Any]:
    rows = result.get("results", [])
    audit_logger.log(
        SEARCH_EXECUTED,
        raw_query=request.query,
        structured_query=structured.to_dict(),
        result_count=result.get("result_count", 0),
        search_source=execution_source,
        entity_ids=[row.get("entity_id") for row in rows if row.get("entity_id")],
        object_ids=[row.get("evidence_object_id") for row in rows if row.get("evidence_object_id")],
        ai_used=meta["ai_used"],
        ai_provider=meta.get("ai_provider"),
        ai_model=meta.get("ai_model"),
        metadata={"query_mode": structured.execute_with, "interpretation": meta, "diagnostics": result.get("diagnostics")},
    )
    summary = _summarise_if_requested(request, rows, db, execution_source, audit_logger)
    return {"structured_query": structured.to_dict(), "interpretation": meta, "execution_source": execution_source, "result": result, "ai_summary": summary}


@router.post("/execute")
def execute_query(
    request: ExecuteRequest,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> dict[str, Any]:
    service = TrustVaultFeatureService(db)
    reader = FitsContainerReader(db)
    structured, meta = _interpret(request, db)
    terms = structured.search_terms or [request.query]
    search_query = " ".join(terms)

    if structured.capability == "archive_status":
        return _audit_and_return(request=request, structured=structured, meta=meta, result=_archive_status_result(service, structured), execution_source="archive_status", audit_logger=audit_logger, db=db)

    if structured.capability == "entity_summary":
        return _audit_and_return(request=request, structured=structured, meta=meta, result=_entity_summary_result(db, service, structured), execution_source="entity_summary", audit_logger=audit_logger, db=db)

    if structured.capability == "payload_metadata":
        return _audit_and_return(request=request, structured=structured, meta=meta, result=_payload_metadata_result(db, structured), execution_source="payload_metadata", audit_logger=audit_logger, db=db)

    if structured.capability == "entity_discovery":
        return _audit_and_return(request=request, structured=structured, meta=meta, result=_entity_discovery_result(service, structured, request.limit), execution_source="entity_metadata", audit_logger=audit_logger, db=db)

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
            result = {"result_count": len(runs), "results": runs, "diagnostics": {"matching_entity_count": len(customers), "execution_mode": "completeness_check"}}
        return _audit_and_return(request=request, structured=structured, meta=meta, result=result, execution_source="completeness_rules", audit_logger=audit_logger, db=db)

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

    return _audit_and_return(request=request, structured=structured, meta=meta, result=result, execution_source=execution_source, audit_logger=audit_logger, db=db)
