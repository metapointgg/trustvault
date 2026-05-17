from trustvault.ai.base import AiProvider, AiResult


class NoAiProvider(AiProvider):
    def expand_query(self, query: str) -> AiResult:
        return AiResult(text=query, provider="none", warnings=["AI provider disabled"])

    def summarise_evidence(self, evidence: list[dict], question: str | None = None) -> AiResult:
        return AiResult(
            text="AI is disabled for this deployment. The preserved FITS evidence remains the source of truth.",
            provider="none",
            warnings=["AI provider disabled"],
        )
