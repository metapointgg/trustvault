from typing import Any

from trustvault.ai.base import AiProvider, AiResult


class NoAiProvider(AiProvider):
    def expand_query(self, query: str) -> AiResult:
        return AiResult(text=query, provider="none", warnings=["AI provider disabled"])

    def interpret_query(self, query: str, deterministic_query: dict[str, Any], context: dict[str, Any] | None = None) -> AiResult:
        return AiResult(
            text="",
            provider="none",
            data=deterministic_query,
            warnings=["AI provider disabled; deterministic interpretation used"],
        )

    def summarise_evidence(self, evidence: list[dict], question: str | None = None) -> AiResult:
        return AiResult(
            text="AI is disabled for this deployment. The preserved FITS evidence remains the source of truth.",
            provider="none",
            warnings=["AI provider disabled"],
        )
