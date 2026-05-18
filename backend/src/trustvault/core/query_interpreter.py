from __future__ import annotations

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

    This intentionally avoids AI as a source of truth. AI can later expand or
    paraphrase, but this interpreter normalises the operational query shape used
    by the API and tests.
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
        "screening",
        "cdd",
        "due diligence",
        "correspondence",
        "statement",
        "transaction",
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
        execute_with = "direct_fits" if entity and capability not in {"completeness_check", "entity_discovery"} else "fits_index"
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
                return token.upper()
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
        if "missing proof of address" in lower:
            return "proof_of_address"
        if "missing mandatory" in lower:
            return "mandatory_evidence"
        if "missing documents" in lower:
            return "documents"
        return None

    def _extract_evidence_terms(self, lower: str) -> tuple[list[str], list[str], list[str]]:
        document_types: list[str] = []
        categories: list[str] = []
        terms: list[str] = []
        mappings = [
            ("source of wealth", "source_of_wealth", "source_of_wealth", "source of wealth"),
            ("source of funds", "source_of_funds", "source_of_funds", "source of funds"),
            ("proof of address", "proof_of_address", "proof_of_address", "proof of address"),
            ("passport", "passport", "identity", "passport identity"),
            ("identity", "identity_document", "identity", "passport identity"),
            ("screening", "screening", "customer_documents", "screening"),
            ("cdd review", "cdd_risk_review", "cdd_review", "CDD review"),
            ("due diligence", "email", "communications", "due diligence correspondence"),
            ("correspondence", "email", "communications", "correspondence"),
            ("onboarding", "", "customer_documents", "onboarding documentation"),
        ]
        for phrase, doc_type, category, term in mappings:
            if phrase in lower:
                if doc_type and doc_type not in document_types:
                    document_types.append(doc_type)
                if category and category not in categories:
                    categories.append(category)
                if term not in terms:
                    terms.append(term)
        if not terms:
            terms.append(lower)
        return document_types, categories, terms
