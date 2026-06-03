#!/usr/bin/env python3
"""Run TrustVault query regression cases and emit a pass/fail JSON report.

Usage:
  TRUSTVAULT_TOKEN=<token> python scripts/run_query_regression_tests.py \
    --base-url http://localhost:8000 \
    --output /tmp/trustvault-query-regression.json

The runner sets the configured client industry before each case, executes the
query, evaluates configured expectations, and restores the original industry at
the end. The output includes summary counts plus per-case pass/fail reasons.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def request_json(
    method: str,
    url: str,
    *,
    token: str,
    body: dict[str, Any] | None = None,
    attempts: int = 5,
    retry_delay_seconds: float = 1.0,
) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Authorization", f"Bearer {token}")
        request.add_header("Accept", "application/json")
        if body is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            if exc.code in {400, 401, 403, 404, 422}:
                raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {payload}") from exc
            last_error = RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {payload}")
        except (ConnectionResetError, ConnectionRefusedError, TimeoutError, socket.timeout, urllib.error.URLError) as exc:
            last_error = exc
        if attempt < attempts:
            time.sleep(retry_delay_seconds * attempt)
    raise RuntimeError(f"{method} {url} failed after {attempts} attempt(s): {last_error}") from last_error


def current_client_industry(base_url: str, token: str) -> str | None:
    data = request_json("GET", f"{base_url}/api/v1/settings/industry-packs", token=token, attempts=10)
    value = data.get("active_industry")
    return str(value) if value else None


def set_client_industry(base_url: str, token: str, industry: str | None) -> None:
    if not industry:
        return
    request_json(
        "PATCH",
        f"{base_url}/api/v1/settings",
        token=token,
        body={"updates": {"client_industry": industry}},
    )


def compact_response(case: dict[str, Any], response: dict[str, Any], elapsed_ms: int) -> dict[str, Any]:
    result = response.get("result") or {}
    diagnostics = result.get("diagnostics") or {}
    interpretation = response.get("interpretation") or {}
    context = interpretation.get("active_industry_context") or {}
    resolved = interpretation.get("resolved_vocabulary") or {}
    structured = response.get("structured_query") or {}
    rows = result.get("results") or []
    entity_ids = sorted({str(row.get("entity_external_id") or row.get("external_id")) for row in rows if row.get("entity_external_id") or row.get("external_id")})
    missing_docs = sorted({str(row.get("document_type") or row.get("missing_evidence_type")) for row in rows if row.get("document_type") or row.get("missing_evidence_type")})
    actual = {
        "structured_query": structured,
        "execution_source": response.get("execution_source"),
        "result_count": result.get("result_count"),
        "entity_external_ids": entity_ids,
        "missing_document_types": missing_docs,
        "active_industry_context": context,
        "resolved_vocabulary": resolved,
        "diagnostics": {
            "execution_mode": diagnostics.get("execution_mode"),
            "active_industry": diagnostics.get("active_industry"),
            "industry_filter_source": diagnostics.get("industry_filter_source"),
            "metadata_filters": diagnostics.get("metadata_filters"),
            "expected_document_types": diagnostics.get("expected_document_types"),
            "matching_entity_count": diagnostics.get("matching_entity_count"),
            "matching_entity_external_ids": diagnostics.get("matching_entity_external_ids"),
            "matched_before_limit": diagnostics.get("matched_before_limit"),
        },
    }
    passed, reasons = evaluate_expectations(case.get("expect") or {}, actual)
    return {
        "id": case.get("id"),
        "source": case.get("source", "core_regression"),
        "scenario_group": case.get("scenario_group"),
        "industry": case.get("industry"),
        "query": case.get("query"),
        "elapsed_ms": elapsed_ms,
        "passed": passed,
        "failure_reasons": reasons,
        "expect": case.get("expect") or {},
        "actual": actual,
    }


def evaluate_expectations(expect: dict[str, Any], actual: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    structured = actual.get("structured_query") or {}
    diagnostics = actual.get("diagnostics") or {}
    context = actual.get("active_industry_context") or {}
    entity_ids = set(actual.get("entity_external_ids") or [])
    missing_docs = set(actual.get("missing_document_types") or [])

    if expect.get("no_error") and actual.get("error"):
        reasons.append(f"unexpected error: {actual['error']}")
    if expect.get("capability") and structured.get("capability") != expect["capability"]:
        reasons.append(f"capability expected {expect['capability']} got {structured.get('capability')}")
    if expect.get("execution_source") and actual.get("execution_source") != expect["execution_source"]:
        reasons.append(f"execution_source expected {expect['execution_source']} got {actual.get('execution_source')}")
    if expect.get("active_industry"):
        active = diagnostics.get("active_industry") or context.get("industry_key")
        if active != expect["active_industry"]:
            reasons.append(f"active_industry expected {expect['active_industry']} got {active}")
    if expect.get("risk_rating") and structured.get("risk_rating") != expect["risk_rating"]:
        reasons.append(f"risk_rating expected {expect['risk_rating']} got {structured.get('risk_rating')}")
    if expect.get("jurisdiction") and structured.get("jurisdiction") != expect["jurisdiction"]:
        reasons.append(f"jurisdiction expected {expect['jurisdiction']} got {structured.get('jurisdiction')}")
    if "result_count" in expect and actual.get("result_count") != expect["result_count"]:
        reasons.append(f"result_count expected {expect['result_count']} got {actual.get('result_count')}")
    if "min_result_count" in expect and int(actual.get("result_count") or 0) < int(expect["min_result_count"]):
        reasons.append(f"result_count expected at least {expect['min_result_count']} got {actual.get('result_count')}")

    expected_entities = set(expect.get("expected_entity_external_ids") or [])
    missing_expected_entities = sorted(expected_entities - entity_ids)
    if missing_expected_entities:
        reasons.append(f"missing expected entity_external_ids: {missing_expected_entities}")
    forbidden_entities = set(expect.get("forbidden_entity_external_ids") or [])
    present_forbidden_entities = sorted(forbidden_entities & entity_ids)
    if present_forbidden_entities:
        reasons.append(f"forbidden entity_external_ids present: {present_forbidden_entities}")

    expected_docs = set(expect.get("document_types") or [])
    if expected_docs:
        structured_docs = set(structured.get("document_types") or [])
        diagnostic_docs = set(diagnostics.get("expected_document_types") or [])
        seen_docs = missing_docs | structured_docs | diagnostic_docs
        missing_expected_docs = sorted(expected_docs - seen_docs)
        if missing_expected_docs:
            reasons.append(f"missing expected document_types: {missing_expected_docs}")

    expected_filters = expect.get("metadata_filters") or {}
    if isinstance(expected_filters, dict) and expected_filters:
        actual_filters = _flatten_metadata_filters(context.get("metadata_filters") or diagnostics.get("metadata_filters") or [])
        for key, expected_value in expected_filters.items():
            if actual_filters.get(key) != expected_value:
                reasons.append(f"metadata_filter {key} expected {expected_value} got {actual_filters.get(key)}")

    forbidden_risk = expect.get("forbidden_risk_rating")
    if forbidden_risk:
        filters = (actual.get("resolved_vocabulary") or {}).get("filters") or []
        if any(item.get("field_binding") == "risk_rating" and item.get("canonical_value") == forbidden_risk for item in filters):
            reasons.append(f"forbidden risk_rating match present: {forbidden_risk}")

    return not reasons, reasons


def _flatten_metadata_filters(filters: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for item in filters:
        field = item.get("field_binding")
        if field:
            output[str(field)] = item.get("canonical_value")
    return output


def error_case(case: dict[str, Any], error: Exception, elapsed_ms: int) -> dict[str, Any]:
    actual = {"error": str(error)}
    passed, reasons = evaluate_expectations(case.get("expect") or {}, actual)
    if not reasons:
        reasons = [str(error)]
    return {
        "id": case.get("id"),
        "source": case.get("source", "core_regression"),
        "scenario_group": case.get("scenario_group"),
        "industry": case.get("industry"),
        "query": case.get("query"),
        "elapsed_ms": elapsed_ms,
        "passed": False,
        "failure_reasons": reasons,
        "expect": case.get("expect") or {},
        "actual": actual,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TrustVault query regression cases")
    parser.add_argument("--base-url", default=os.environ.get("TRUSTVAULT_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--token", default=os.environ.get("TRUSTVAULT_TOKEN") or os.environ.get("TOKEN"))
    parser.add_argument("--output", default="")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--fail-on-regression", action="store_true", help="Exit with status 1 if any case fails")
    args = parser.parse_args()

    if not args.token:
        print("Set TRUSTVAULT_TOKEN or TOKEN, or pass --token.", file=sys.stderr)
        return 2

    base_url = args.base_url.rstrip("/")
    original_industry = current_client_industry(base_url, args.token)
    manifest = request_json("GET", f"{base_url}/api/v1/query/test-cases", token=args.token, attempts=10)
    cases = manifest.get("test_cases") or []
    report: dict[str, Any] = {
        "base_url": base_url,
        "generated_at_epoch": int(time.time()),
        "original_client_industry": original_industry,
        "test_case_count": len(cases),
        "passed_count": 0,
        "failed_count": 0,
        "failed_case_ids": [],
        "cases": [],
    }

    try:
        for case in cases:
            start = time.time()
            try:
                set_client_industry(base_url, args.token, case.get("industry"))
                response = request_json(
                    "POST",
                    f"{base_url}/api/v1/query/execute",
                    token=args.token,
                    body={
                        "query": case["query"],
                        "mode": case.get("mode", "auto"),
                        "limit": args.limit,
                        "include_ai_summary": False,
                    },
                )
                elapsed_ms = int((time.time() - start) * 1000)
                case_result = compact_response(case, response, elapsed_ms)
            except Exception as exc:  # noqa: BLE001 - command-line diagnostic output
                elapsed_ms = int((time.time() - start) * 1000)
                case_result = error_case(case, exc, elapsed_ms)
            report["cases"].append(case_result)
            if case_result["passed"]:
                report["passed_count"] += 1
            else:
                report["failed_count"] += 1
                report["failed_case_ids"].append(case_result["id"])
    finally:
        set_client_industry(base_url, args.token, original_industry)
        report["restored_client_industry"] = original_industry

    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.write("\n")
    print(text)
    return 1 if args.fail_on_regression and report["failed_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
