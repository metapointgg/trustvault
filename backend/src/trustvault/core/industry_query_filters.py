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


def active_industry_key(db: Session) -> str:
    values = AppSettingsService(db).effective_values()
    return str(values.get("client_industry") or "financial_services").strip().lower()


def active_query_context(db: Session, raw_query: str) -> dict[str, Any]:
    resolved = QueryVocabularyService(db).resolve(raw_query)
    return {
        "industry_key": active_industry_key(db),
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
    target = _normalise(document_type)
    values = [
        row_or_item.get("document_type"),
        row_or_item.get("object_type"),
        row_or_item.get("filename"),
        row_or_item.get("category"),
    ]
    for value in values:
        normalised = _normalise(value)
        if normalised == target or target in normalised or normalised in target:
            return True
    return False


def _normalise(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
