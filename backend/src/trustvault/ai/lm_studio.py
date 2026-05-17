import json
import urllib.request

from trustvault.ai.base import AiProvider, AiResult


class LmStudioAiProvider(AiProvider):
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def expand_query(self, query: str) -> AiResult:
        return AiResult(text=query, provider="lm_studio", warnings=["Query expansion prompt not enabled in this scaffold"])

    def summarise_evidence(self, evidence: list[dict], question: str | None = None) -> AiResult:
        prompt = {
            "messages": [
                {"role": "system", "content": "Summarise only the provided TrustVault evidence. State that FITS evidence is source of truth."},
                {"role": "user", "content": json.dumps({"question": question, "evidence": evidence}, default=str)},
            ],
            "temperature": 0.1,
        }
        request = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(prompt).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
            text = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
            return AiResult(text=text, provider="lm_studio", model=payload.get("model"))
        except Exception as exc:
            return AiResult(text="", provider="lm_studio", warnings=[str(exc)])
