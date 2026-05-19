from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from trustvault.db.models import AppSetting

DOCUMENT_CLASSIFICATION_SETTING_KEY = "document_classification_config"

DEFAULT_DOCUMENT_CLASSIFICATION_CONFIG: dict[str, Any] = {
    "version": 1,
    "uncategorised_confidence_threshold": 0.8,
    "document_types": [
        {"document_type": "Passport", "category": "Identity", "filename_patterns": ["passport", "photo_id", "identity_document"]},
        {"document_type": "Driving Licence", "category": "Identity", "filename_patterns": ["driving_licence", "driving_license", "drivers_licence", "drivers_license"]},
        {"document_type": "Proof of Address", "category": "Address", "filename_patterns": ["proof_of_address", "address", "utility_bill", "council_tax", "bank_letter"]},
        {"document_type": "Source of Funds", "category": "Source of Funds", "filename_patterns": ["source_of_funds", "sof", "funds", "funding"]},
        {"document_type": "Source of Wealth", "category": "Source of Wealth", "filename_patterns": ["source_of_wealth", "sow", "wealth"]},
        {"document_type": "CDD Review", "category": "CDD", "filename_patterns": ["cdd", "review", "periodic_review", "customer_due_diligence"]},
        {"document_type": "Application", "category": "Onboarding", "filename_patterns": ["application", "onboarding", "account_opening", "new_customer"]},
        {"document_type": "Screening Evidence", "category": "Screening", "filename_patterns": ["screening", "sanctions", "pep", "aml_screening"]},
        {"document_type": "EDD Approval", "category": "EDD", "filename_patterns": ["edd", "enhanced_due_diligence", "approval"]},
        {"document_type": "Company Registry Extract", "category": "Corporate", "filename_patterns": ["registry", "company_extract", "company_registry", "certificate_of_incorporation"]},
        {"document_type": "Beneficial Owner Evidence", "category": "Corporate", "filename_patterns": ["beneficial_owner", "ubo", "ultimate_beneficial_owner"]},
        {"document_type": "Authorised Signatory ID", "category": "Corporate", "filename_patterns": ["authorised_signatory", "authorized_signatory", "signatory_id", "signatory"]},
        {"document_type": "Monthly Statement", "category": "Statement", "filename_patterns": ["statement", "monthly_statement", "bank_statement"]},
        {"document_type": "Transaction Extract", "category": "Transaction", "filename_patterns": ["transaction_extract", "transactions", "ledger_extract"]},
        {"document_type": "Customer Correspondence", "category": "Correspondence", "filename_patterns": ["correspondence", "email", "letter", "client_letter"]},
        {"document_type": "Customer Metadata", "category": "Customer Information", "filename_patterns": ["customer", "metadata", "customer_information", "profile"]},
        {"document_type": "Legacy Binary Payload", "category": "Legacy Evidence", "filename_patterns": ["legacy", "archive", "binary", "blob"]},
    ],
}


@dataclass(frozen=True)
class DocumentClassificationResult:
    document_type: str | None
    category: str | None
    confidence: float
    status: str
    source: str
    matched_pattern: str | None = None


class DocumentClassificationService:
    """Classifies evidence using configurable document type to category mappings.

    Folder names are treated only as weak context. The preferred path is:
    filename -> Document Type -> Category.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_config(self) -> dict[str, Any]:
        row = self.db.get(AppSetting, DOCUMENT_CLASSIFICATION_SETTING_KEY)
        if row is not None and isinstance(row.value_json, dict):
            value = row.value_json.get("value")
            if isinstance(value, dict) and isinstance(value.get("document_types"), list):
                return self._normalise_config(value)
        return self._normalise_config(DEFAULT_DOCUMENT_CLASSIFICATION_CONFIG)

    def save_config(self, config: dict[str, Any], *, updated_by_user_id: str | None = None) -> dict[str, Any]:
        normalised = self._normalise_config(config)
        row = self.db.get(AppSetting, DOCUMENT_CLASSIFICATION_SETTING_KEY)
        if row is None:
            row = AppSetting(
                key=DOCUMENT_CLASSIFICATION_SETTING_KEY,
                value_json={"value": normalised},
                value_type="json",
                category="Document classification",
                description="Document type to category mappings and filename matching rules used during evidence ingestion and categorisation.",
                is_secret=False,
                is_editable=True,
                updated_by_user_id=updated_by_user_id,
            )
            self.db.add(row)
        else:
            row.value_json = {"value": normalised}
            row.value_type = "json"
            row.category = "Document classification"
            row.description = "Document type to category mappings and filename matching rules used during evidence ingestion and categorisation."
            row.is_secret = False
            row.is_editable = True
            row.updated_by_user_id = updated_by_user_id
        self.db.commit()
        return normalised

    def document_types(self) -> list[str]:
        return [str(item["document_type"]) for item in self.get_config().get("document_types", [])]

    def category_for_document_type(self, document_type: str) -> str | None:
        target = self._normalise_token(document_type)
        for item in self.get_config().get("document_types", []):
            if self._normalise_token(str(item.get("document_type", ""))) == target:
                return str(item.get("category") or "") or None
        return None

    def classify(self, *, filename: str, source_path: str | None = None) -> DocumentClassificationResult:
        config = self.get_config()
        filename_text = self._normalise_filename(filename)
        source_text = self._normalise_filename(source_path or "")

        for item in config.get("document_types", []):
            document_type = str(item.get("document_type") or "").strip()
            category = str(item.get("category") or "").strip()
            patterns = [document_type, *[str(value) for value in item.get("filename_patterns", [])]]
            for pattern in patterns:
                normalised_pattern = self._normalise_filename(pattern)
                if not normalised_pattern:
                    continue
                if self._matches(filename_text, normalised_pattern):
                    return DocumentClassificationResult(
                        document_type=document_type,
                        category=category,
                        confidence=0.95,
                        status="classified",
                        source="filename_rule",
                        matched_pattern=pattern,
                    )
                if source_text and self._matches(source_text, normalised_pattern):
                    return DocumentClassificationResult(
                        document_type=document_type,
                        category=category,
                        confidence=0.7,
                        status="suggested",
                        source="source_path_rule",
                        matched_pattern=pattern,
                    )

        return DocumentClassificationResult(
            document_type=None,
            category=None,
            confidence=0.0,
            status="uncategorised",
            source="no_match",
            matched_pattern=None,
        )

    def build_metadata(
        self,
        *,
        filename: str,
        source_path: str | None = None,
        existing_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata = dict(existing_metadata or {})
        existing_document_type = str(metadata.get("document_type") or "").strip()
        existing_category = str(metadata.get("category") or "").strip()
        if existing_document_type and existing_category:
            metadata.setdefault("classification_status", "confirmed")
            metadata.setdefault("classification_source", "provided_metadata")
            metadata.setdefault("classification_confidence", 1.0)
            return metadata

        classification = self.classify(filename=filename, source_path=source_path)
        metadata.update(
            {
                "document_type": classification.document_type,
                "category": classification.category,
                "classification_status": classification.status,
                "classification_source": classification.source,
                "classification_confidence": classification.confidence,
                "classification_matched_pattern": classification.matched_pattern,
            }
        )
        return metadata

    def mark_confirmed(
        self,
        metadata: dict[str, Any] | None,
        *,
        document_type: str,
        updated_by: str | None,
    ) -> dict[str, Any]:
        category = self.category_for_document_type(document_type)
        now = datetime.now(timezone.utc).isoformat()
        next_metadata = dict(metadata or {})
        next_metadata.update(
            {
                "document_type": document_type,
                "category": category,
                "classification_status": "confirmed",
                "classification_source": "manual",
                "classification_confidence": 1.0,
                "classification_updated_by": updated_by,
                "classification_updated_at": now,
            }
        )
        return next_metadata

    def is_uncategorised(self, metadata: dict[str, Any] | None) -> bool:
        metadata = metadata or {}
        document_type = str(metadata.get("document_type") or "").strip()
        category = str(metadata.get("category") or "").strip()
        status = str(metadata.get("classification_status") or "").strip().lower()
        try:
            confidence = float(metadata.get("classification_confidence") or 0)
        except (TypeError, ValueError):
            confidence = 0
        threshold = float(self.get_config().get("uncategorised_confidence_threshold") or 0.8)
        return not document_type or not category or status == "uncategorised" or confidence < threshold

    def _normalise_config(self, config: dict[str, Any]) -> dict[str, Any]:
        document_types: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in config.get("document_types", []):
            if not isinstance(item, dict):
                continue
            document_type = str(item.get("document_type") or "").strip()
            category = str(item.get("category") or "").strip()
            if not document_type or not category:
                continue
            key = self._normalise_token(document_type)
            if key in seen:
                continue
            seen.add(key)
            patterns = item.get("filename_patterns", [])
            if not isinstance(patterns, list):
                patterns = []
            document_types.append(
                {
                    "document_type": document_type,
                    "category": category,
                    "filename_patterns": [str(pattern).strip() for pattern in patterns if str(pattern).strip()],
                }
            )
        return {
            "version": int(config.get("version") or 1),
            "uncategorised_confidence_threshold": float(config.get("uncategorised_confidence_threshold") or 0.8),
            "document_types": document_types or DEFAULT_DOCUMENT_CLASSIFICATION_CONFIG["document_types"],
        }

    def _normalise_filename(self, value: str) -> str:
        value = value.lower()
        value = re.sub(r"\.[a-z0-9]{1,8}$", "", value)
        value = re.sub(r"[^a-z0-9]+", " ", value)
        return re.sub(r"\s+", " ", value).strip()

    def _normalise_token(self, value: str) -> str:
        return self._normalise_filename(value).replace(" ", "_")

    def _matches(self, haystack: str, needle: str) -> bool:
        if not haystack or not needle:
            return False
        return haystack == needle or needle in haystack
