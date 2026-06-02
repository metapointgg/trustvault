from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from trustvault.core.industry_pack_config import IndustryPackConfigService


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
        self.pack = IndustryPackConfigService(db).active_pack()

    def active_pack(self) -> dict[str, Any]:
        return self.pack

    def resolve(self, query: str) -> dict[str, Any]:
        matches = self.matches(query)
        filters = [m for m in matches if not m.is_requirement_dimension]
        requirements = [m for m in matches if m.is_requirement_dimension]
        return {
            "industry_pack": self.pack.get("key"),
            "filters": [m.to_dict() for m in filters],
            "requirements": [m.to_dict() for m in requirements],
            "matches": [m.to_dict() for m in matches],
        }

    def matches(self, query: str) -> list[VocabularyMatch]:
        normalised = self._normalise(query)
        output: list[VocabularyMatch] = []
        seen: set[tuple[str, str]] = set()
        for vocab in self.pack.get("vocabulary_lists") or []:
            for item in vocab.get("items") or []:
                canonical = str(item.get("canonical_value") or "")
                aliases = [str(alias) for alias in (item.get("aliases") or [])]
                candidates = [canonical, *aliases]
                for candidate in candidates:
                    candidate_norm = self._normalise(candidate)
                    if not candidate_norm:
                        continue
                    if self._contains_phrase(normalised, candidate_norm):
                        key = (str(vocab.get("list_key") or ""), canonical)
                        if key in seen:
                            continue
                        seen.add(key)
                        output.append(
                            VocabularyMatch(
                                dimension=str(vocab.get("list_key") or ""),
                                canonical_value=canonical,
                                matched_alias=candidate,
                                field_binding=vocab.get("field_binding"),
                                match_type="phrase",
                                confidence=1.0 if candidate == canonical else 0.92,
                                is_requirement_dimension=bool(vocab.get("is_requirement_dimension")),
                            )
                        )
                        break
        for group in self.pack.get("requirement_groups") or []:
            label = str(group.get("label") or "")
            aliases = [str(alias) for alias in (group.get("aliases") or [])]
            for candidate in [label, *aliases]:
                candidate_norm = self._normalise(candidate)
                if candidate_norm and self._contains_phrase(normalised, candidate_norm):
                    key = ("requirement_group", str(group.get("key") or label))
                    if key in seen:
                        continue
                    seen.add(key)
                    output.append(
                        VocabularyMatch(
                            dimension="requirement_group",
                            canonical_value=label,
                            matched_alias=candidate,
                            field_binding=None,
                            match_type="phrase",
                            confidence=1.0 if candidate == label else 0.92,
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
        for match in requirements:
            if match["dimension"] == "requirement_group":
                overrides["capability"] = "completeness_check"
                overrides["completeness_only"] = True
                overrides["missing_evidence_type"] = "mandatory_evidence"
                if self._normalise(match["canonical_value"]) in {"onboarding", "patient onboarding", "supplier onboarding"}:
                    overrides["snapshot_id"] = "ONBOARDING"
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
