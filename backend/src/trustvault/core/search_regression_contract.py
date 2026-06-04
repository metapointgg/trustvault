from __future__ import annotations

from typing import Any


class TrustVaultRegressionRunner:
    """Importable regression contract helper used by backend unit tests.

    The executable regression scripts live outside the backend Docker build
    context. This helper keeps the expectation-derivation contract available to
    the containerised backend test suite without depending on top-level repo
    scripts being mounted into /app.
    """

    def __init__(self, base_url: str, token: str | None, mode: str, limit: int, include_ai_summary: bool, timeout: int):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.mode = mode
        self.limit = limit
        self.include_ai_summary = include_ai_summary
        self.timeout = timeout
        self.dynamic_values: dict[str, str] = {}

    def _derive(self, response: dict[str, Any]) -> dict[str, Any]:
        data = response.get("json") if isinstance(response.get("json"), dict) else {}
        structured = data.get("structured_query") if isinstance(data, dict) else None
        interpretation = data.get("interpretation") if isinstance(data, dict) else None
        result = data.get("result") if isinstance(data, dict) else None
        if result is None and isinstance(data, dict) and "result_count" in data:
            result = data
        ai_summary = data.get("ai_summary") if isinstance(data, dict) else None
        diagnostics = result.get("diagnostics") if isinstance(result, dict) else None
        rows = result.get("results") if isinstance(result, dict) else None
        return {
            "structured_query": structured,
            "capability": structured.get("capability") if isinstance(structured, dict) else None,
            "scope": structured.get("scope") if isinstance(structured, dict) else None,
            "execute_with": structured.get("execute_with") if isinstance(structured, dict) else None,
            "risk_rating": structured.get("risk_rating") if isinstance(structured, dict) else None,
            "jurisdiction": structured.get("jurisdiction") if isinstance(structured, dict) else None,
            "snapshot_id": structured.get("snapshot_id") if isinstance(structured, dict) else None,
            "document_types": structured.get("document_types") if isinstance(structured, dict) else None,
            "categories": structured.get("categories") if isinstance(structured, dict) else None,
            "search_terms": structured.get("search_terms") if isinstance(structured, dict) else None,
            "execution_source": data.get("execution_source") if isinstance(data, dict) else None,
            "result_count": result.get("result_count") if isinstance(result, dict) else None,
            "filtered_entity_count": result.get("filtered_entity_count") if isinstance(result, dict) else None,
            "diagnostics": diagnostics,
            "row_count": len(rows) if isinstance(rows, list) else None,
            "first_result": rows[0] if isinstance(rows, list) and rows else None,
            "ai_summary_available": ai_summary.get("available") if isinstance(ai_summary, dict) else None,
            "ai_summary_provider": ai_summary.get("provider") if isinstance(ai_summary, dict) else None,
            "ai_summary_warnings": ai_summary.get("warnings") if isinstance(ai_summary, dict) else None,
            "interpretation_ai_used": interpretation.get("ai_used") if isinstance(interpretation, dict) else None,
            "interpretation_ai_warnings": interpretation.get("ai_warnings") if isinstance(interpretation, dict) else None,
        }

    def _check_expectations(self, test: dict[str, Any], response: dict[str, Any], derived: dict[str, Any]) -> list[str]:
        issues: list[str] = []
        if not response.get("ok"):
            issues.append("http_not_ok")
            return issues
        if test.get("expect_non_empty") and not response.get("json"):
            issues.append("empty_response")
        expected_json_keys = test.get("expected_json_keys") or []
        response_json = response.get("json") if isinstance(response.get("json"), dict) else {}
        for key in expected_json_keys:
            if key not in response_json:
                issues.append(f"missing_json_key_{key}")
        for key, expected_value in (test.get("expected_json_value") or {}).items():
            if response_json.get(key) != expected_value:
                issues.append(f"json_value_{key}_expected_{expected_value}_got_{response_json.get(key)}")
        max_elapsed = test.get("max_elapsed_seconds")
        elapsed = response.get("elapsed_seconds")
        if max_elapsed is not None and elapsed is not None and elapsed > max_elapsed:
            issues.append(f"elapsed_seconds_expected_max_{max_elapsed}_got_{elapsed}")
        expected = test.get("expected_capability")
        if expected and derived.get("capability") != expected:
            issues.append(f"capability_expected_{expected}_got_{derived.get('capability')}")
        expected_any = test.get("expected_capability_any")
        if expected_any and derived.get("capability") not in expected_any:
            issues.append(f"capability_not_in_{expected_any}_got_{derived.get('capability')}")
        expected_scope = test.get("expected_scope")
        if expected_scope and derived.get("scope") != expected_scope:
            issues.append(f"scope_expected_{expected_scope}_got_{derived.get('scope')}")
        expected_execute_with = test.get("expected_execute_with")
        if expected_execute_with and derived.get("execute_with") != expected_execute_with:
            issues.append(f"execute_with_expected_{expected_execute_with}_got_{derived.get('execute_with')}")
        expected_execution_source = test.get("expected_execution_source")
        if expected_execution_source and derived.get("execution_source") != expected_execution_source:
            issues.append(f"execution_source_expected_{expected_execution_source}_got_{derived.get('execution_source')}")
        expected_snapshot_id = test.get("expected_snapshot_id")
        if expected_snapshot_id and derived.get("snapshot_id") != expected_snapshot_id:
            issues.append(f"snapshot_id_expected_{expected_snapshot_id}_got_{derived.get('snapshot_id')}")
        forbidden_document_type = test.get("forbidden_document_type")
        document_types = derived.get("document_types") or []
        if forbidden_document_type and forbidden_document_type in document_types:
            issues.append(f"forbidden_document_type_present_{forbidden_document_type}")
        min_count = test.get("expect_result_count_min")
        result_count = derived.get("result_count")
        if min_count is not None and (result_count is None or result_count < min_count):
            issues.append(f"result_count_expected_min_{min_count}_got_{result_count}")
        return issues
