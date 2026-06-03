from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from sqlalchemy.orm import Session

from trustvault.core.app_settings import AppSettingsService

MAX_ROWS_FOR_PROMPT = 20
MAX_STRING_CHARS = 1000

SYSTEM_PROMPT = (
    "You are the TrustVault query answer agent. Write a concise user-facing "
    "narrative answer from the supplied structured query result. Use only the "
    "supplied data. Explain what was found, who or what it relates to, and any "
    "important caveat visible in the diagnostics. Do not refer to rows or JSON "
    "unless the user asked about technical output."
)


def summarise_query_results(
    *,
    db: Session,
    raw_query: str,
    structured_query: dict[str, Any],
    interpretation: dict[str, Any],
    execution_source: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    settings = AppSettingsService(db).effective_values()
    provider = str(settings.get("ai_provider") or "none").strip().lower()
    if provider in {"", "none", "disabled", "off"}:
        return _fallback(raw_query, result, provider or "none", "none", "AI provider is disabled.")
    if provider != "lm_studio":
        return _fallback(raw_query, result, provider, "unsupported", f"Provider {provider} is not implemented for query narratives yet.")

    base_url = str(settings.get("lm_studio_base_url") or "").rstrip("/")
    model = str(settings.get("lm_studio_model") or settings.get("lm_studio_query_model") or "").strip()
    if not base_url or not model:
        return _fallback(raw_query, result, provider, model or "unset", "LM Studio base URL or model is not configured.")

    try:
        summary = _call_lm_studio(base_url, model, _payload(raw_query, structured_query, interpretation, execution_source, result))
        if not summary:
            raise RuntimeError("empty summary returned")
        return {
            "available": True,
            "summary": summary,
            "provider": provider,
            "model": model,
            "warnings": [],
            "ai_used_for_summary": True,
        }
    except Exception as exc:  # noqa: BLE001 - summarisation must not fail query execution
        return _fallback(raw_query, result, provider, model, f"AI summary unavailable: {exc}")


def _call_lm_studio(base_url: str, model: str, payload: dict[str, Any]) -> str:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ],
        "temperature": 0.2,
        "max_tokens": 260,
        "stream": False,
    }
    request = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LM Studio HTTP {exc.code}: {error_body[:300]}") from exc
    message = ((data.get("choices") or [{}])[0].get("message") or {})
    return _clean_text(message.get("content"))


def _payload(
    raw_query: str,
    structured_query: dict[str, Any],
    interpretation: dict[str, Any],
    execution_source: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    rows = result.get("results") if isinstance(result.get("results"), list) else []
    diagnostics = result.get("diagnostics") if isinstance(result.get("diagnostics"), dict) else {}
    return {
        "user_query": raw_query,
        "structured_query": _compact(structured_query),
        "industry_context": _compact((interpretation.get("active_industry_context") or {})),
        "execution_source": execution_source,
        "result_count": result.get("result_count"),
        "filtered_entity_count": result.get("filtered_entity_count"),
        "diagnostics": _compact(diagnostics),
        "results": [_compact(row) for row in rows[:MAX_ROWS_FOR_PROMPT] if isinstance(row, dict)],
        "truncated_result_count": max(len(rows) - MAX_ROWS_FOR_PROMPT, 0),
    }


def _compact(value: Any, depth: int = 0) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= MAX_STRING_CHARS else f"{value[:MAX_STRING_CHARS]}... [truncated]"
    if isinstance(value, list):
        return [_compact(item, depth + 1) for item in value[:20]]
    if isinstance(value, dict):
        if depth >= 4:
            return "[nested object omitted]"
        output: dict[str, Any] = {}
        for key, item in list(value.items())[:80]:
            if str(key).startswith("_"):
                continue
            output[str(key)] = _compact(item, depth + 1)
        return output
    return str(value)


def _fallback(raw_query: str, result: dict[str, Any], provider: str, model: str, warning: str) -> dict[str, Any]:
    rows = result.get("results") if isinstance(result.get("results"), list) else []
    count = result.get("result_count", len(rows))
    return {
        "available": False,
        "summary": f"AI narrative summary is unavailable. The query returned {count} result(s) for: {raw_query}",
        "provider": provider,
        "model": model,
        "warnings": [warning],
        "ai_used_for_summary": False,
    }


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and parsed.get("summary"):
                text = str(parsed["summary"]).strip()
        except json.JSONDecodeError:
            pass
    return " ".join(text.split())
