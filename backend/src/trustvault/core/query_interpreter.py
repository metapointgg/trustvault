from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class StructuredQuery:
    raw_query: str
    scope: str
    capability: str
    entity_external_id: str | None = None
    risk_rating: str | None = None
    jurisdiction: str | None = None
    snapshot_id: str | None = None
    document_types: list[str] | None = None
    categories: list[str] | None = None
    search_terms: list[str] | None = None
    completeness_only: bool = False
    missing_evidence_type: str | None = None
    execute_with: str = "fits_index"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TrustVaultQueryInterpreter:
    """Deterministic first-pass interpreter for TrustVault evidence queries.

    AI may improve language understanding, but this deterministic layer protects
    the operational contract: FITS evidence remains the source of truth and
    natural-language queries must resolve to stable TrustVault capabilities.
    """

    JURISDICTIONS = {
        "guernsey": "Guernsey",
        "jersey": "Jersey",
        "united kingdom": "United Kingdom",
        "uk": "United Kingdom",
        "isle of man": "Isle of Man",
        "iom": "Isle of Man",
    }

    CUSTOMER_DISCOVERY_TERMS = (
        "customer",
        "customers",
        "client",
        "clients",
        "entity",
        "entities",
    )

    EVIDENCE_INTENT_TERMS = (
        "evidence",
        "document",
        "documents",
        "documentation",
        "file",
        "files",
        "passport",
        "identity",
        "proof of address",
        "source of wealth",
        "source of funds",
        "where the customer money came from",
        "money came from",
        "screening",
        "cdd",
        "due diligence",
        "correspondence",
        "statement",
        "transaction",
    )

    ARCHIVE_STATUS_TERMS = (
        "archive status",
        "how many entities",
        "how many customers",
        "how many containers",
        "indexed evidence objects",
        "configured source folder",
        "containers folder",
        "index path",
        "exports folder",
        "source folder",
    )

    ENTITY_SUMMARY_TERMS = (
        "summarise entity",
        "summarize entity",
        "fits containers available",
        "evidence counts by category",
        "counts by category",
        "document type for",
        "retention and legal hold summary",
    )

    def interpret(self, raw_query: str, *, entity_external_id: str | None = None, execute: bool = False) -> StructuredQuery:
        q = raw_query.strip()
        lower = q.lower()
        entity = entity_external_id or self._extract_entity(lower)
        risk = self._extract_risk(lower)
        jurisdiction = self._extract_jurisdiction(lower)
        snapshot_id = "ONBOARDING" if "onboarding" in lower else None
        document_types, categories, terms = self._extract_evidence_terms(lower)
        missing_type = self._extract_missing_type(lower)
        completeness = "complete" in lower or "completeness" in lower or "missing mandatory" in lower or missing_type is not None
        scope = "entity" if entity else "archive"
        capability = self._capability(lower, completeness, snapshot_id, document_types, categories)
        execute_with = "direct_fits" if entity and capability not in {"completeness_check", "entity_discovery", "entity_summary", "archive_status", "payload_metadata"} else "fits_index"
        return StructuredQuery(
            raw_query=q,
            scope=scope,
            capability=capability,
            entity_external_id=entity,
            risk_rating=risk,
            jurisdiction=jurisdiction,
            snapshot_id=snapshot_id,
            document_types=document_types,
            categories=categories,
            search_terms=terms,
            completeness_only=completeness,
            missing_evidence_type=missing_type,
            execute_with=execute_with,
        )

    def _capability(
        self,
        lower: str,
        completeness: bool,
        snapshot_id: str | None,
        document_types: list[str],
        categories: list[str],
    ) -> str:
        if any(term in lower for term in self.ARCHIVE_STATUS_TERMS):
            return "archive_status"
        if "object" in lower and re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", lower):
            return "payload_metadata"
        if any(term in lower for term in self.ENTITY_SUMMARY_TERMS):
            return "entity_summary"
        if completeness:
            return "completeness_check"
        customer_intent = any(term in lower for term in self.CUSTOMER_DISCOVERY_TERMS)
        evidence_intent = any(term in lower for term in self.EVIDENCE_INTENT_TERMS)
        has_specific_evidence_filter = bool(snapshot_id or document_types or categories)
        if customer_intent and not evidence_intent and not has_specific_evidence_filter:
            return "entity_discovery"
        if customer_intent and ("list" in lower or "show" in lower or "find" in lower) and not has_specific_evidence_filter:
            return "entity_discovery"
        return "evidence_search"

    def _extract_entity(self, lower: str) -> str | None:
        for token in lower.replace(":", " ").replace(",", " ").split():
            if token.startswith("cust-"):
                return token.strip(". ").upper()
        return None

    def _extract_risk(self, lower: str) -> str | None:
        if "high risk" in lower:
            return "High"
        if "medium risk" in lower:
            return "Medium"
        if "low risk" in lower:
            return "Low"
        return None

    def _extract_jurisdiction(self, lower: str) -> str | None:
        for key, value in self.JURISDICTIONS.items():
            if key in lower:
                return value
        return None

    def _extract_missing_type(self, lower: str) -> str | None:
        # "correspondence mentioning missing documents" is an evidence search,
        # not a completeness workflow. Treat explicit correspondence/email
        # wording as an indexed evidence query.
        if "correspondence" in lower or "email" in lower:
            return None
        if "missing proof of address" in lower:
            return "proof_of_address"
        if "missing mandatory" in lower:
            return "mandatory_evidence"
        if "missing documents" in lower and ("which" in lower or "identify" in lower or "customers are missing" in lower):
            return "documents"
        return None

    def _extract_evidence_terms(self, lower: str) -> tuple[list[str], list[str], list[str]]:
        document_types: list[str] = []
        categories: list[str] = []
        terms: list[str] = []

        def add(doc_types: list[str] | None = None, cats: list[str] | None = None, search_terms: list[str] | None = None) -> None:
            for item in doc_types or []:
                if item and item not in document_types:
                    document_types.append(item)
            for item in cats or []:
                if item and item not in categories:
                    categories.append(item)
            for item in search_terms or []:
                if item and item not in terms:
                    terms.append(item)

        if "source of wealth" in lower:
            add(["source_of_wealth"], ["source_of_wealth"], ["source of wealth", "wealth", "proceeds"])
        if "source of funds" in lower or "money came from" in lower or "where the customer money came from" in lower:
            # The current archive stores retail KYC funding evidence under the
            # source-of-wealth category. Keep source-of-funds as a search term,
            # but search the actual preserved evidence class.
            add(["source_of_wealth", "source_of_funds"], ["source_of_wealth", "source_of_funds"], ["source of funds", "source of wealth", "funds", "proceeds"])
        if "proof of address" in lower:
            add(["proof_of_address"], ["proof_of_address"], ["proof of address"])
        if "passport" in lower:
            add(["passport", "identity_document"], ["identity"], ["passport", "identity"])
        if "identity" in lower:
            add(["identity_document", "passport"], ["identity"], ["identity", "passport"])
        if "screening" in lower:
            add(["screening", "cdd_risk_review"], ["customer_documents", "cdd_review"], ["screening", "pep", "sanctions", "adverse media"])
        if "cdd review" in lower:
            add(["cdd_risk_review"], ["cdd_review"], ["CDD review", "customer due diligence"])
        if "due diligence" in lower:
            add(["email", "cdd_risk_review"], ["communications", "cdd_review"], ["due diligence", "correspondence"])
        if "correspondence" in lower:
            add(["email"], ["communications"], ["correspondence"])
        if "missing documents" in lower and ("correspondence" in lower or "email" in lower):
            add(["email"], ["communications"], ["missing documents", "missing", "correspondence"])
        if "onboarding" in lower:
            add([], ["customer_documents"], ["onboarding documentation"])

        if not terms:
            terms.append(lower)
        return document_types, categories, terms
