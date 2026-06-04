from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from trustvault.core.industry_pack_config import IndustryPackConfigService
from trustvault.db.models import Entity


@dataclass(frozen=True)
class EvidenceClassification:
    category: str
    document_type: str
    classification_status: str
    classification_confidence: float
    matched_alias: str | None
    industry_pack: str
    source: str = "industry_vocabulary"

    def to_metadata(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "document_type": self.document_type,
            "classification_status": self.classification_status,
            "classification_confidence": self.classification_confidence,
            "classification_matched_alias": self.matched_alias,
            "classification_source": self.source,
            "industry_pack": self.industry_pack,
        }


class EvidenceClassifier:
    """Classify evidence using configured industry pack vocabulary.

    This is intentionally industry-agnostic. It derives candidate document types
    from the selected industry's vocabulary lists and requirement groups rather
    than hardcoding healthcare, supplier or financial-services document names in
    the classifier itself.
    """

    _AUTHORITATIVE_CLASSIFICATION_SOURCES = {"system_metadata"}
    _SELF_DESCRIBING_OBJECT_TYPES = {"email", "audit_events", "audit events", "statement", "statements"}

    def __init__(self, db: Session):
        self.db = db
        self.pack_config = IndustryPackConfigService(db)

    def classify(
        self,
        *,
        filename: str | None = None,
        object_type: str | None = None,
        source_system: str | None = None,
        text_content: str | None = None,
        metadata: dict[str, Any] | None = None,
        entity: Entity | None = None,
        industry_key: str | None = None,
    ) -> EvidenceClassification | None:
        metadata = metadata or {}
        if self._should_preserve_existing_classification(metadata=metadata, object_type=object_type, filename=filename):
            return None

        industry = self._resolve_industry(entity=entity, metadata=metadata, industry_key=industry_key)
        pack = self.pack_config.get_pack(industry)
        candidates = self._document_type_candidates(pack)
        if not candidates:
            return None

        # Classification should be based on document identity signals, not the
        # whole document body or arbitrary metadata. In particular, do not use
        # content_type because values such as application/pdf collide with broad
        # business aliases such as "application".
        identity_haystack = self._normalise_text(
            "\n".join(
                [
                    filename or "",
                    object_type or "",
                    source_system or "",
                    self._identity_metadata_text(metadata),
                ]
            )
        )
        if not identity_haystack:
            return None

        best: tuple[float, str, str | None] | None = None
        for document_type, aliases in candidates.items():
            for alias in sorted({document_type, *aliases}, key=len, reverse=True):
                score = self._match_score(
                    identity_haystack,
                    alias,
                    filename=filename,
                    object_type=object_type,
                    metadata=metadata,
                )
                if score <= 0:
                    continue
                if best is None or score > best[0] or (score == best[0] and len(document_type) > len(best[1])):
                    best = (score, document_type, alias)
        if best is None:
            return None

        confidence, document_type, alias = best
        category = self._category_for_document_type(pack, document_type)
        return EvidenceClassification(
            category=category,
            document_type=document_type,
            classification_status="classified" if confidence >= 0.75 else "suggested",
            classification_confidence=round(confidence, 2),
            matched_alias=alias,
            industry_pack=industry,
        )

    def classify_metadata(self, *, metadata: dict[str, Any], entity: Entity | None = None, industry_key: str | None = None) -> dict[str, Any]:
        classification = self.classify(
            filename=metadata.get("filename"),
            object_type=metadata.get("object_type"),
            source_system=metadata.get("source_system"),
            text_content=metadata.get("search_text") or metadata.get("text_content"),
            metadata=metadata,
            entity=entity,
            industry_key=industry_key,
        )
        return classification.to_metadata() if classification else {}

    def _resolve_industry(self, *, entity: Entity | None, metadata: dict[str, Any], industry_key: str | None) -> str:
        value = industry_key or metadata.get("industry_pack") or metadata.get("industry") or metadata.get("demo_archive_key")
        if not value and entity is not None and isinstance(entity.metadata_json, dict):
            value = entity.metadata_json.get("industry_pack") or entity.metadata_json.get("industry") or entity.metadata_json.get("demo_archive_key")
        return str(value or "financial_services").strip().lower().replace("-", "_")

    def _document_type_candidates(self, pack: dict[str, Any]) -> dict[str, set[str]]:
        candidates: dict[str, set[str]] = {}
        for vocab in pack.get("vocabulary_lists") or []:
            if not vocab.get("is_requirement_dimension") and str(vocab.get("list_key") or "") != "document_type":
                continue
            for item in vocab.get("items") or []:
                canonical = str(item.get("canonical_value") or "").strip()
                if not canonical:
                    continue
                candidates.setdefault(canonical, set()).update(str(alias).strip() for alias in item.get("aliases") or [] if str(alias).strip())
        for group in pack.get("requirement_groups") or []:
            for doc in group.get("default_document_types") or []:
                canonical = str(doc or "").strip()
                if canonical:
                    candidates.setdefault(canonical, set())
        return candidates

    def _category_for_document_type(self, pack: dict[str, Any], document_type: str) -> str:
        document_norm = self._normalise_token(document_type)
        for group in pack.get("requirement_groups") or []:
            docs = [self._normalise_token(item) for item in group.get("default_document_types") or []]
            if document_norm in docs:
                return self._normalise_key(str(group.get("key") or group.get("label") or "evidence"))
        return "general_evidence"

    def _match_score(self, haystack: str, alias: str, *, filename: str | None, object_type: str | None, metadata: dict[str, Any]) -> float:
        alias_norm = self._normalise_text(alias)
        if not alias_norm:
            return 0.0
        alias_tokens = [token for token in alias_norm.split() if len(token) > 1]
        if not alias_tokens:
            return 0.0

        filename_norm = self._normalise_text(filename)
        object_type_norm = self._normalise_text(object_type)
        existing_doc_norm = self._normalise_text(metadata.get("document_type"))
        existing_category_norm = self._normalise_text(metadata.get("category"))

        if alias_norm in {filename_norm, object_type_norm, existing_doc_norm}:
            return 1.0
        if alias_norm and (alias_norm in filename_norm or alias_norm in object_type_norm or alias_norm in existing_doc_norm):
            return 0.98

        # Single-word aliases such as "application" or "report" are useful for
        # document identity fields but are too broad for a general haystack match.
        # They must not classify from incidental metadata or source-system text.
        if len(alias_tokens) == 1:
            return 0.0

        if alias_norm and alias_norm in haystack:
            return 0.92

        token_hits = sum(1 for token in alias_tokens if token in haystack)
        if token_hits == len(alias_tokens):
            return 0.88
        if len(alias_tokens) > 1 and token_hits >= max(1, len(alias_tokens) - 1):
            return 0.72
        if existing_category_norm and alias_norm in existing_category_norm:
            return 0.70
        return 0.0

    def _should_preserve_existing_classification(
        self,
        *,
        metadata: dict[str, Any],
        object_type: str | None,
        filename: str | None,
    ) -> bool:
        nested = metadata.get("metadata") if isinstance(metadata.get("metadata"), dict) else {}
        classification_source = self._normalise_token(metadata.get("classification_source") or nested.get("classification_source"))
        classification_status = self._normalise_token(metadata.get("classification_status") or nested.get("classification_status"))
        if classification_status == "classified" and classification_source in self._AUTHORITATIVE_CLASSIFICATION_SOURCES:
            return True

        object_type_norm = self._normalise_token(object_type or metadata.get("object_type") or nested.get("object_type"))
        document_type_norm = self._normalise_token(metadata.get("document_type") or nested.get("document_type"))
        filename_norm = self._normalise_token(filename or metadata.get("filename") or nested.get("filename"))
        if object_type_norm in self._SELF_DESCRIBING_OBJECT_TYPES or document_type_norm in self._SELF_DESCRIBING_OBJECT_TYPES:
            return True
        if filename_norm.endswith("_eml") or filename_norm.endswith("_email"):
            return True
        return False

    def _identity_metadata_text(self, metadata: dict[str, Any]) -> str:
        nested = metadata.get("metadata") if isinstance(metadata.get("metadata"), dict) else {}
        values: list[str] = []
        for key in (
            "filename",
            "object_type",
            "document_type",
            "category",
            "classification_matched_alias",
        ):
            value = metadata.get(key) if metadata.get(key) is not None else nested.get(key)
            if isinstance(value, (str, int, float, bool)):
                values.append(f"{key} {value}")
        return "\n".join(values)

    def _metadata_text(self, metadata: dict[str, Any]) -> str:
        values: list[str] = []
        for key, value in metadata.items():
            if key.startswith("_"):
                continue
            if isinstance(value, (str, int, float, bool)):
                values.append(f"{key} {value}")
            elif isinstance(value, list):
                values.extend(str(item) for item in value[:20])
            elif isinstance(value, dict):
                values.append(self._metadata_text(value))
        return "\n".join(values)

    def _normalise_text(self, value: Any) -> str:
        text = str(value or "").lower()
        text = re.sub(r"[_\-./]+", " ", text)
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _normalise_token(self, value: Any) -> str:
        return self._normalise_text(value).replace(" ", "_")

    def _normalise_key(self, value: str) -> str:
        return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.lower())).strip("_") or "general_evidence"
