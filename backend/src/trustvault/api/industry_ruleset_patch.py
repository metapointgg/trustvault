from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from trustvault.core.feature_services import TrustVaultFeatureService
from trustvault.core.industry_rulesets import IndustryRulesetService
from trustvault.db.models import CompletenessResult, CompletenessRun, Ruleset, RulesetRule


_PATCHED = False


def apply() -> None:
    """Patch TrustVaultFeatureService to use industry-specific completeness rulesets.

    This keeps the existing API surface intact while moving default completeness
    evaluation away from one global financial-services ruleset.
    """

    global _PATCHED
    if _PATCHED:
        return

    def ensure_default_ruleset(self: TrustVaultFeatureService) -> Ruleset:
        service = IndustryRulesetService(self.db)
        service.ensure_all_default_rulesets()
        return service.ensure_ruleset("financial_services")

    def rulesets(self: TrustVaultFeatureService) -> list[dict[str, Any]]:
        IndustryRulesetService(self.db).ensure_all_default_rulesets()
        rulesets = self.db.scalars(select(Ruleset).order_by(Ruleset.created_at.desc())).all()
        return [self._ruleset_dict(item) for item in rulesets]

    def evaluate_completeness(self: TrustVaultFeatureService, entity_id: str, ruleset_id: str | None = None) -> dict[str, Any]:
        entity = self._entity(entity_id)
        ruleset = self.db.get(Ruleset, uuid.UUID(ruleset_id)) if ruleset_id else IndustryRulesetService(self.db).ruleset_for_entity(entity)
        current = self._current_fits(entity.id, required=False)
        manifest = current.manifest_json.get("evidence_objects", []) if current else []
        rules = self.db.scalars(select(RulesetRule).where(RulesetRule.ruleset_id == ruleset.id)).all()
        results: list[dict[str, Any]] = []
        present_count = 0
        applicable_count = 0
        for rule in rules:
            if not self._rule_applies_to_entity(rule, entity):
                continue
            applicable_count += 1
            match = self._match_rule(rule, manifest)
            if match:
                present_count += 1
            results.append({
                "rule_key": rule.rule_key,
                "category": rule.category,
                "document_type": rule.document_type,
                "status": "present" if match else "missing",
                "matched_evidence_object_id": match.get("id") if match else None,
                "matched_filename": match.get("filename") if match else None,
            })
        required_count = applicable_count
        missing_count = required_count - present_count
        score = int((present_count / required_count) * 100) if required_count else 100
        run = CompletenessRun(
            entity_id=entity.id,
            ruleset_id=ruleset.id,
            container_version_id=current.id if current else None,
            status="completed",
            score=score,
            required_count=required_count,
            present_count=present_count,
            missing_count=missing_count,
            result_json={"results": results, "industry_pack": (ruleset.metadata_json or {}).get("industry_pack")},
        )
        self.db.add(run)
        self.db.flush()
        for row in results:
            self.db.add(CompletenessResult(
                run_id=run.id,
                entity_id=entity.id,
                rule_key=row["rule_key"],
                category=row["category"],
                document_type=row["document_type"],
                status=row["status"],
                matched_evidence_object_id=row["matched_evidence_object_id"],
                details_json=row,
            ))
        self.db.commit()
        return {
            "run_id": str(run.id),
            "entity_id": str(entity.id),
            "entity_external_id": entity.external_id,
            "ruleset_id": str(ruleset.id),
            "ruleset_name": ruleset.name,
            "industry_pack": (ruleset.metadata_json or {}).get("industry_pack"),
            "container_version_id": str(current.id) if current else None,
            "score": score,
            "required_count": required_count,
            "present_count": present_count,
            "missing_count": missing_count,
            "results": results,
        }

    original_rule_applies = TrustVaultFeatureService._rule_applies_to_entity

    def rule_applies_to_entity(self: TrustVaultFeatureService, rule: RulesetRule, entity: Any) -> bool:
        if not original_rule_applies(self, rule, entity):
            return False
        applies_when = rule.applies_when_json or {}
        metadata_filters = applies_when.get("metadata_filters") or (rule.metadata_json or {}).get("metadata_filters") or {}
        if not isinstance(metadata_filters, dict) or not metadata_filters:
            return True
        entity_metadata = entity.metadata_json or {}
        for key, expected in metadata_filters.items():
            if self._normalise(entity_metadata.get(key)) != self._normalise(expected):
                return False
        return True

    TrustVaultFeatureService.ensure_default_ruleset = ensure_default_ruleset
    TrustVaultFeatureService.rulesets = rulesets
    TrustVaultFeatureService.evaluate_completeness = evaluate_completeness
    TrustVaultFeatureService._rule_applies_to_entity = rule_applies_to_entity
    _PATCHED = True
