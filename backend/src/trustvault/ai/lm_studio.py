import json
import urllib.request
from typing import Any

from trustvault.ai.base import AiProvider, AiResult
from trustvault.settings import get_settings


class LmStudioAiProvider(AiProvider):
    def __init__(self, base_url: str, model: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model or get_settings().lm_studio_query_model

    def expand_query(self, query: str) -> AiResult:
        prompt = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Generate concise evidence archive search terms. Return JSON only."},
                {"role": "user", "content": json.dumps({"query": query, "schema": {"terms": ["string"]}})},
            ],
            "temperature": 0.1,
        }
        payload, warning = self._post_chat(prompt)
        if warning:
            return AiResult(text=query, provider="lm_studio", model=self.model, warnings=[warning])
        content = self._content(payload)
        data = self._extract_json(content) or {}
        terms = data.get("terms") if isinstance(data, dict) else None
        if isinstance(terms, list) and terms:
            return AiResult(text=" ".join(str(term) for term in terms[:12]), provider="lm_studio", model=payload.get("model", self.model), data={"terms": terms})
        return AiResult(text=query, provider="lm_studio", model=payload.get("model", self.model), warnings=["No valid terms returned"])

    def interpret_query(self, query: str, deterministic_query: dict[str, Any], context: dict[str, Any] | None = None) -> AiResult:
        prompt = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You convert regulated evidence archive questions into strict JSON. "
                        "Return JSON only. Never generate SQL. Never invent entity IDs, document types or categories. "
                        "FITS containers and indexes are the source of truth; your role is interpretation only."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "user_query": query,
                            "deterministic_interpretation": deterministic_query,
                            "context": context or {},
                            "controlled_vocabulary": {
                                "scopes": ["archive", "entity"],
                                "capabilities": ["evidence_search", "completeness_check", "entity_discovery", "archive_status", "payload_metadata"],
                                "execute_with": ["fits_index", "direct_fits"],
                                "risk_rating": ["High", "Medium", "Low"],
                                "jurisdiction": ["Guernsey", "Jersey", "United Kingdom", "Isle of Man", "Other"],
                                "categories": [
                                    "customer_documents", "identity", "proof_of_address", "source_of_wealth",
                                    "source_of_funds", "cdd_review", "communications", "screening",
                                ],
                                "document_types": [
                                    "passport", "identity_document", "proof_of_address", "source_of_wealth",
                                    "source_of_funds", "cdd_risk_review", "screening", "email",
                                    "account_opening_application",
                                ],
                            },
                            "hard_rules": [
                                "Onboarding is a lifecycle snapshot, not a document type.",
                                "For onboarding, set snapshot_id to ONBOARDING and do not set document_types to ONBOARDING.",
                                "If an entity ID is not present in the user query or selected context, keep entity_external_id null.",
                                "Selected-customer evidence search uses direct_fits; archive/cohort search uses fits_index.",
                            ],
                            "output_schema": {
                                "scope": "archive|entity",
                                "capability": "evidence_search|completeness_check|entity_discovery|archive_status|payload_metadata",
                                "entity_external_id": None,
                                "risk_rating": None,
                                "jurisdiction": None,
                                "snapshot_id": None,
                                "document_types": [],
                                "categories": [],
                                "search_terms": [],
                                "completeness_only": False,
                                "missing_evidence_type": None,
                                "execute_with": "fits_index|direct_fits",
                                "confidence": 0.0,
                                "reason": "brief explanation",
                            },
                        },
                        default=str,
                    ),
                },
            ],
            "temperature": 0.1,
        }
        payload, warning = self._post_chat(prompt)
        if warning:
            return AiResult(text="", provider="lm_studio", model=self.model, data=deterministic_query, warnings=[warning])
        content = self._content(payload)
        data = self._extract_json(content)
        if not isinstance(data, dict):
            return AiResult(text=content, provider="lm_studio", model=payload.get("model", self.model), data=deterministic_query, warnings=["AI did not return valid JSON; deterministic interpretation used"])
        return AiResult(text=content, provider="lm_studio", model=payload.get("model", self.model), data=data)

    def summarise_evidence(self, evidence: list[dict], question: str | None = None) -> AiResult:
        prompt = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Summarise only the provided TrustVault evidence. State that FITS evidence is source of truth."},
                {"role": "user", "content": json.dumps({"question": question, "evidence": evidence}, default=str)},
            ],
            "temperature": 0.1,
        }
        payload, warning = self._post_chat(prompt)
        if warning:
            return AiResult(text="", provider="lm_studio", model=self.model, warnings=[warning])
        return AiResult(text=self._content(payload), provider="lm_studio", model=payload.get("model", self.model))

    def _post_chat(self, payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        url = f"{self.base_url}/v1/chat/completions" if not self.base_url.endswith("/v1") else f"{self.base_url}/chat/completions"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8")), None
        except Exception as exc:
            return {}, str(exc)

    def _content(self, payload: dict[str, Any]) -> str:
        choice = (payload.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        return message.get("content") or message.get("reasoning_content") or ""

    def _extract_json(self, text: str) -> dict[str, Any] | None:
        text = text.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
        return None
