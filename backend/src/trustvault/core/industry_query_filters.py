from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from trustvault.core.app_settings import AppSettingsService
from trustvault.core.query_vocabulary import QueryVocabularyService


FINANCIAL_ENTITY_TYPES = {"person", "organisation", "customer", "company", "trust", "fund"}
INDUSTRY_ENTITY_TYPES = {
    "healthcare": {"patient", "clinician", "department", "referral"},
    "supplier_due_diligence": {"supplier", "vendor", "contractor", "service_provider"},
}
NON_EVIDENCE_DOCUMENT_TYPES = {
    "email",
    "audit_events",
    "bulk_archive_attachment",
    "structured_extract",
    "statement",
}
NON_EVIDENCE_CATEGORIES = {
    "communications",
    "audit",
    "large_evidence",
    "structured_extracts",
    "statements",
}


def active_industry_key(db: Session) -> str:
    values = AppSettingsService(db).effective_values()
    return str(values.get("client_industry") or "financial_services").strip().lower()


def infer_industry_key(db: Session, raw_query: str) -> str:
    """Use explicit query subject terms before falling back to the UI setting."""
    query = _normalise(raw_query)
    if any(term in query.split("_") for term in ("supplier", "suppliers", "vendor", "vendors")) or any(phrase in query for phrase in ("service_provider", "service_providers")):
        return "supplier_due_diligence"
    if any(term in query.split("_") for term in ("patient", "patients", "clinician", "doctor")) or any(phrase in query for phrase in ("dr_jones", "dr_smith", "oncology", "cancer", "consent_form")):
        return "healthcare"
    if any(term in query.split("_") for term in ("customer", "customers", "client", "clients")):
        return "financial_services"
    return active_industry_key(db)


def active_query_context(db: Session, raw_query: str) -> dict[str, Any]:
    industry_key = infer_industry_key(db, raw_query)
    resolved = QueryVocabularyService(db, industry_key=industry_key).resolve(raw_query)
    return {
        "industry_key": industry_key,
        "resolved_vocabulary": resolved,
        "metadata_filters": [
            item for item in resolved.get("filters", [])
            if item.get("field_binding") not in {None, "risk_rating", "jurisdiction", "evidence_status"}
        ],
        "document_requirements": [
            item.get("canonical_value") for item in resolved.get("requirements", [])
            if item.get("dimension") == "document_type" and item.get("canonical_value")
        ],
        "requirement_groups": [
            item.get("canonical_value") for item in resolved.get("requirements", [])
            if item.get("dimension") == "requirement_group" and item.get("canonical_value")
        ],
    }


def entity_matches_active_industry(entity_row: dict[str, Any], industry_key: str) -> bool:
    """Match an entity to an industry using metadata, not naming conventions.

    `industry_pack` is the strongest signal. `demo_archive_key` is retained as a
    secondary source for generated/demo data. Entity type is an industry template
    fallback only, so the platform can still work with older records that do not
    yet have industry metadata.
    """

    metadata = entity_row.get("metadata_json") if isinstance(entity_row.get("metadata_json"), dict) else {}
    entity_type = _normalise(entity_row.get("entity_type"))
    tagged_industry = _normalise(metadata.get("industry_pack") or metadata.get("industry") or metadata.get("demo_archive_key"))
    requested = _normalise(industry_key)

    if tagged_industry:
        return tagged_industry == requested

    if requested == "financial_services":
        return entity_type in FINANCIAL_ENTITY_TYPES

    expected_entity_types = INDUSTRY_ENTITY_TYPES.get(requested, set())
    return entity_type in expected_entity_types


def entity_matches_metadata_filters(entity_row: dict[str, Any], filters: list[dict[str, Any]]) -> bool:
    metadata = entity_row.get("metadata_json") if isinstance(entity_row.get("metadata_json"), dict) else {}
    for item in filters:
        field = item.get("field_binding")
        if not field:
            continue
        actual = metadata.get(field) or entity_row.get(field)
        expected = item.get("canonical_value")
        if _normalise(actual) != _normalise(expected):
            return False
    return True


def entity_matches_context(entity_row: dict[str, Any], context: dict[str, Any]) -> bool:
    return entity_matches_active_industry(entity_row, context["industry_key"]) and entity_matches_metadata_filters(entity_row, context.get("metadata_filters") or [])


def document_types_for_missing_check(context: dict[str, Any]) -> list[str]:
    docs = [str(item) for item in context.get("document_requirements") or [] if item]
    if docs:
        return docs
    groups = {_normalise(item) for item in context.get("requirement_groups") or []}
    if "treatment_consent" in groups:
        return ["Consent Form"]
    if "patient_onboarding" in groups:
        return ["Referral Letter", "Medical History"]
    if "supplier_onboarding" in groups:
        return ["Certificate of Incorporation", "Insurance Certificate"]
    if "cyber_due_diligence" in groups:
        return ["ISO 27001 Certificate", "SOC 2 Report"]
    if "onboarding" in groups:
        return ["Account Opening Application", "Passport", "Proof of Address"]
    return []


def evidence_has_document_type(row_or_item: dict[str, Any], document_type: str) -> bool:
    """Return whether a FITS/index row satisfies a required document type.

    Filenames are useful for classifying genuine uploaded documents, but they can
    create false positives when an email or audit record merely mentions the
    required evidence. Therefore communications, audit rows, bulk blobs,
    statements and structured extracts cannot satisfy a required evidence type by
    filename alone.
    """

    target = _normalise(document_type)
    category = _normalise(row_or_item.get("category"))
    document_value = _normalise(row_or_item.get("document_type"))
    object_value = _normalise(row_or_item.get("object_type"))
    filename_value = _normalise(row_or_item.get("filename"))

    direct_values = [document_value, object_value, category]
    for value in direct_values:
        if _value_matches_target(value, target):
            return True

    if category in NON_EVIDENCE_CATEGORIES or document_value in NON_EVIDENCE_DOCUMENT_TYPES or object_value in NON_EVIDENCE_DOCUMENT_TYPES:
        return False

    # Filename is a final fallback only for rows that are not already classified
    # as communications/audit/bulk/statement/structured extract evidence.
    return _value_matches_target(filename_value, target)


def _value_matches_target(value: str, target: str) -> bool:
    if not value or not target:
        return False
    return value == target or target in value or value in target


def _normalise(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
