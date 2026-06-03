from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.core.industry_query_filters import active_industry_key
from trustvault.db.models import Entity, Ruleset, RulesetRule


@dataclass(frozen=True)
class CompletenessRuleTemplate:
    rule_key: str
    category: str
    document_type: str
    entity_types: tuple[str, ...]
    metadata_filters: dict[str, Any] | None = None


INDUSTRY_RULESET_TEMPLATES: dict[str, dict[str, Any]] = {
    "financial_services": {
        "name": "Financial Services Evidence Ruleset",
        "description": "KYC, onboarding, screening and account-opening evidence completeness rules.",
        "rules": (
            CompletenessRuleTemplate("identity_passport", "identity", "passport", ("person", "customer")),
            CompletenessRuleTemplate("proof_of_address", "proof_of_address", "proof_of_address", ("person", "customer")),
            CompletenessRuleTemplate("source_of_wealth", "source_of_wealth", "source_of_wealth", ("person", "customer")),
            CompletenessRuleTemplate("cdd_risk_review", "cdd_review", "cdd_risk_review", ("person", "organisation", "customer")),
            CompletenessRuleTemplate("account_opening_application", "customer_documents", "account_opening_application", ("person", "organisation", "customer")),
            CompletenessRuleTemplate("screening_evidence", "customer_documents", "screening", ("person", "organisation", "customer")),
            CompletenessRuleTemplate("correspondence_due_diligence", "communications", "email", ("person", "organisation", "customer")),
            CompletenessRuleTemplate("organisation_chart", "ownership_and_control", "organisation_chart", ("organisation",)),
            CompletenessRuleTemplate("shareholder_certificate", "ownership_and_control", "shareholder_certificate", ("organisation",)),
            CompletenessRuleTemplate("certificate_of_incorporation", "organisation_identity", "certificate_of_incorporation", ("organisation",)),
        ),
    },
    "healthcare": {
        "name": "Healthcare Evidence Ruleset",
        "description": "Patient referral, consent, treatment and diagnostic evidence completeness rules.",
        "rules": (
            CompletenessRuleTemplate("referral_letter", "clinical_referral", "Referral Letter", ("patient",)),
            CompletenessRuleTemplate("consent_form", "clinical_consent", "Consent Form", ("patient",)),
            CompletenessRuleTemplate("treatment_plan", "clinical_treatment", "Treatment Plan", ("patient",)),
            CompletenessRuleTemplate("diagnostic_report", "clinical_diagnostics", "Diagnostic Report", ("patient",), {"department": "Oncology"}),
        ),
    },
    "supplier_due_diligence": {
        "name": "Supplier Due Diligence Evidence Ruleset",
        "description": "Supplier onboarding, corporate evidence, insurance and cyber due-diligence completeness rules.",
        "rules": (
            CompletenessRuleTemplate("certificate_of_incorporation", "supplier_corporate", "Certificate of Incorporation", ("supplier", "vendor", "contractor", "service_provider")),
            CompletenessRuleTemplate("insurance_certificate", "supplier_corporate", "Insurance Certificate", ("supplier", "vendor", "contractor", "service_provider")),
            CompletenessRuleTemplate("iso_27001_certificate", "supplier_cyber", "ISO 27001 Certificate", ("supplier", "vendor", "service_provider"), {"supplier_category": "IT"}),
            CompletenessRuleTemplate("soc_2_report", "supplier_cyber", "SOC 2 Report", ("supplier", "vendor", "service_provider"), {"supplier_category": "IT"}),
            CompletenessRuleTemplate("data_processing_agreement", "supplier_data_protection", "Data Processing Agreement", ("supplier", "vendor", "service_provider"), {"supplier_category": "IT"}),
        ),
    },
}


class IndustryRulesetService:
    def __init__(self, db: Session):
        self.db = db

    def ensure_all_default_rulesets(self) -> None:
        for industry_key in INDUSTRY_RULESET_TEMPLATES:
            self.ensure_ruleset(industry_key)

    def ensure_ruleset(self, industry_key: str | None) -> Ruleset:
        key = self._normalise_industry(industry_key)
        template = INDUSTRY_RULESET_TEMPLATES.get(key) or INDUSTRY_RULESET_TEMPLATES["financial_services"]
        existing = self.db.scalars(
            select(Ruleset).where(Ruleset.metadata_json["industry_pack"].as_string() == key).where(Ruleset.status == "active")
        ).first()
        if existing is not None:
            return existing

        ruleset = Ruleset(
            name=template["name"],
            version=1,
            status="active",
            description=template["description"],
            metadata_json={"source": "system_default", "industry_pack": key},
        )
        self.db.add(ruleset)
        self.db.flush()
        for rule in template["rules"]:
            self.db.add(
                RulesetRule(
                    ruleset_id=ruleset.id,
                    rule_key=rule.rule_key,
                    category=rule.category,
                    document_type=rule.document_type,
                    required=True,
                    applies_when_json={"entity_types": list(rule.entity_types), "metadata_filters": rule.metadata_filters or {}},
                    metadata_json={"source": "system_default", "industry_pack": key, "applies_to_entity_types": list(rule.entity_types), "metadata_filters": rule.metadata_filters or {}},
                )
            )
        self.db.commit()
        self.db.refresh(ruleset)
        return ruleset

    def list_configs(self) -> dict[str, Any]:
        self.ensure_all_default_rulesets()
        return {
            "industry_rulesets": [self.ruleset_config(key) for key in INDUSTRY_RULESET_TEMPLATES],
            "active_industry": active_industry_key(self.db),
        }

    def ruleset_config(self, industry_key: str | None) -> dict[str, Any]:
        ruleset = self.ensure_ruleset(industry_key)
        rules = self.db.scalars(select(RulesetRule).where(RulesetRule.ruleset_id == ruleset.id).order_by(RulesetRule.rule_key.asc())).all()
        metadata = ruleset.metadata_json or {}
        return {
            "industry_key": metadata.get("industry_pack") or self._normalise_industry(industry_key),
            "ruleset_id": str(ruleset.id),
            "name": ruleset.name,
            "version": ruleset.version,
            "status": ruleset.status,
            "description": ruleset.description,
            "customised": metadata.get("source") == "admin_override",
            "metadata_json": metadata,
            "rules": [self._rule_config(rule) for rule in rules],
        }

    def save_ruleset_config(self, industry_key: str, config: dict[str, Any], *, updated_by_user_id: str | None = None) -> dict[str, Any]:
        key = self._normalise_industry(industry_key)
        if not isinstance(config, dict):
            raise ValueError("Ruleset config must be a JSON object")
        ruleset = self.ensure_ruleset(key)
        ruleset.name = str(config.get("name") or ruleset.name)
        ruleset.version = int(config.get("version") or ruleset.version or 1)
        ruleset.status = str(config.get("status") or "active")
        ruleset.description = config.get("description") if config.get("description") is not None else ruleset.description
        ruleset.metadata_json = {**(config.get("metadata_json") or {}), "source": "admin_override", "industry_pack": key, "updated_by_user_id": updated_by_user_id}
        self.db.query(RulesetRule).filter(RulesetRule.ruleset_id == ruleset.id).delete()
        for raw_rule in config.get("rules") or []:
            rule = self._validate_rule(raw_rule, key)
            self.db.add(RulesetRule(ruleset_id=ruleset.id, **rule))
        self.db.commit()
        return self.ruleset_config(key)

    def reset_ruleset_config(self, industry_key: str) -> dict[str, Any]:
        key = self._normalise_industry(industry_key)
        existing = self.db.scalars(select(Ruleset).where(Ruleset.metadata_json["industry_pack"].as_string() == key)).all()
        for ruleset in existing:
            self.db.query(RulesetRule).filter(RulesetRule.ruleset_id == ruleset.id).delete()
            self.db.delete(ruleset)
        self.db.commit()
        return self.ruleset_config(key)

    def ruleset_for_entity(self, entity: Entity) -> Ruleset:
        metadata = entity.metadata_json or {}
        industry_key = metadata.get("industry_pack") or metadata.get("industry") or metadata.get("demo_archive_key") or self._industry_from_entity_type(entity.entity_type) or active_industry_key(self.db)
        return self.ensure_ruleset(str(industry_key))

    def _rule_config(self, rule: RulesetRule) -> dict[str, Any]:
        applies_when = rule.applies_when_json or {}
        metadata = rule.metadata_json or {}
        return {
            "id": str(rule.id),
            "rule_key": rule.rule_key,
            "category": rule.category,
            "document_type": rule.document_type,
            "required": rule.required,
            "applies_to_entity_types": applies_when.get("entity_types") or metadata.get("applies_to_entity_types") or [],
            "metadata_filters": applies_when.get("metadata_filters") or metadata.get("metadata_filters") or {},
            "applies_when_json": applies_when,
            "max_age_days": rule.max_age_days,
            "metadata_json": metadata,
        }

    def _validate_rule(self, raw_rule: dict[str, Any], industry_key: str) -> dict[str, Any]:
        if not isinstance(raw_rule, dict):
            raise ValueError("Each rule must be a JSON object")
        rule_key = str(raw_rule.get("rule_key") or "").strip()
        category = str(raw_rule.get("category") or "").strip()
        document_type = str(raw_rule.get("document_type") or "").strip()
        if not rule_key or not category or not document_type:
            raise ValueError("Each rule requires rule_key, category and document_type")
        entity_types = raw_rule.get("applies_to_entity_types") or (raw_rule.get("applies_when_json") or {}).get("entity_types") or []
        metadata_filters = raw_rule.get("metadata_filters") or (raw_rule.get("applies_when_json") or {}).get("metadata_filters") or {}
        applies_when = {"entity_types": [str(item) for item in entity_types], "metadata_filters": metadata_filters if isinstance(metadata_filters, dict) else {}}
        metadata = {**(raw_rule.get("metadata_json") or {}), "source": "admin_override", "industry_pack": industry_key, "applies_to_entity_types": applies_when["entity_types"], "metadata_filters": applies_when["metadata_filters"]}
        return {
            "rule_key": rule_key,
            "category": category,
            "document_type": document_type,
            "required": bool(raw_rule.get("required", True)),
            "applies_when_json": applies_when,
            "max_age_days": raw_rule.get("max_age_days"),
            "metadata_json": metadata,
        }

    def _industry_from_entity_type(self, entity_type: str | None) -> str | None:
        normalised = self._normalise(entity_type)
        if normalised in {"patient", "clinician", "department", "referral"}:
            return "healthcare"
        if normalised in {"supplier", "vendor", "contractor", "service_provider"}:
            return "supplier_due_diligence"
        if normalised in {"person", "organisation", "customer", "company", "trust", "fund"}:
            return "financial_services"
        return None

    def _normalise_industry(self, industry_key: str | None) -> str:
        key = self._normalise(industry_key)
        return key if key in INDUSTRY_RULESET_TEMPLATES else "financial_services"

    def _normalise(self, value: Any) -> str:
        return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
