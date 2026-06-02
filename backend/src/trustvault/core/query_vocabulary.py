from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from trustvault.core.app_settings import AppSettingsService
from trustvault.core.industry_packs import get_industry_pack


@dataclass(frozen=True)
class VocabularyMatch:
    dimension: str
    canonical_value: str
    matched_alias: str
    field_binding: str | None
    match_type: str
    confidence: float
    is_requirement_dimension: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "canonical_value": self.canonical_value,
            "matched_alias": self.matched_alias,
            "field_binding": self.field_binding,
            "match_type": self.match_type,
            "confidence": self.confidence,
            "is_requirement_dimension": self.is_requirement_dimension,
        }


class QueryVocabularyService:
    def __init__(self, db: Session):
        self.db = db
        self.values = AppSettingsService(db).effective_values()
        self.pack = get_industry_pack(str(self.values.get("client_industry") or "financial_services"))

    def active_pack(self) -> dict[str, Any]:
        return self.pack.to_dict()

    def resolve(self, query: str) -> dict[str, Any]:
        matches = self.matches(query)
        filters = [m for m in matches if not m.is_requirement_dimension]
        requirements = [m for m in matches if m.is_requirement_dimension]
        return {
            "industry_pack": self.pack.key,
            "filters": [m.to_dict() for m in filters],
            "requirements": [m.to_dict() for m in requirements],
            "matches": [m.to_dict() for m in matches],
        }

    def matches(self, query: str) -> list[VocabularyMatch]:
        normalised = self._normalise(query)
        output: list[VocabularyMatch] = []
        seen: set[tuple[str, str]] = set()
        for vocab in self.pack.vocabulary_lists:
            for item in vocab.items:
                candidates = (item.canonical_value, *item.aliases)
                for candidate in candidates:
                    candidate_norm = self._normalise(candidate)
                    if not candidate_norm:
                        continue
                    if self._contains_phrase(normalised, candidate_norm):
                        key = (vocab.list_key, item.canonical_value)
                        if key in seen:
                            continue
                        seen.add(key)
                        output.append(
                            VocabularyMatch(
                                dimension=vocab.list_key,
                                canonical_value=item.canonical_value,
                                matched_alias=candidate,
                                field_binding=vocab.field_binding,
                                match_type="phrase",
                                confidence=1.0 if candidate == item.canonical_value else 0.92,
                                is_requirement_dimension=vocab.is_requirement_dimension,
                            )
                        )
                        break
        for group in self.pack.requirement_groups:
            for candidate in (group.label, *group.aliases):
                candidate_norm = self._normalise(candidate)
                if candidate_norm and self._contains_phrase(normalised, candidate_norm):
                    key = ("requirement_group", group.key)
                    if key in seen:
                        continue
                    seen.add(key)
                    output.append(
                        VocabularyMatch(
                            dimension="requirement_group",
                            canonical_value=group.label,
                            matched_alias=candidate,
                            field_binding=None,
                            match_type="phrase",
                            confidence=1.0 if candidate == group.label else 0.92,
                            is_requirement_dimension=True,
                        )
                    )
                    break
        return output

    def legacy_structured_overrides(self, query: str) -> dict[str, Any]:
        """Return safe overrides for the existing legacy StructuredQuery fields.

        This keeps the current query execution path working while the new generic
        query object is introduced. Only validated vocabulary matches are allowed
        to populate legacy fields.
        """
        resolved = self.resolve(query)
        filters = resolved["filters"]
        requirements = resolved["requirements"]
        overrides: dict[str, Any] = {}
        for match in filters:
            if match["field_binding"] == "jurisdiction":
                overrides["jurisdiction"] = match["canonical_value"]
            if match["field_binding"] == "risk_rating":
                overrides["risk_rating"] = match["canonical_value"]
        if any(match["dimension"] == "requirement_group" and match["canonical_value"].lower() == "onboarding" for match in requirements):
            overrides["snapshot_id"] = "ONBOARDING"
            overrides["capability"] = "completeness_check"
            overrides["completeness_only"] = True
            overrides["missing_evidence_type"] = "mandatory_evidence"
        document_requirements = [m["canonical_value"] for m in requirements if m["dimension"] == "document_type"]
        if document_requirements:
            overrides["document_types"] = document_requirements
            if self._has_missing_intent(query):
                overrides["capability"] = "completeness_check"
                overrides["completeness_only"] = True
                overrides["missing_evidence_type"] = self._to_key(document_requirements[0])
        return {"overrides": overrides, "resolved_vocabulary": resolved}

    def _has_missing_intent(self, query: str) -> bool:
        normalised = self._normalise(query)
        return any(phrase in normalised for phrase in ("missing", "not supplied", "not provided", "without", "outstanding", "have not supplied", "has not supplied"))

    def _to_key(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")

    def _normalise(self, value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())).strip()

    def _contains_phrase(self, text: str, phrase: str) -> bool:
        if not phrase:
            return False
        return re.search(rf"(^|\s){re.escape(phrase)}($|\s)", text) is not None
