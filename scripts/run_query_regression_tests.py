#!/usr/bin/env python3
"""Run TrustVault query regression cases and emit a compact JSON report.

Usage:
  TRUSTVAULT_TOKEN=<token> python scripts/run_query_regression_tests.py \
    --base-url http://localhost:8000 \
    --output /tmp/trustvault-query-regression.json

The script intentionally does not decide pass/fail. It records the configured
expectations alongside the actual structured query, interpretation context,
execution source, diagnostics and returned entity ids. Paste the output into the
next ChatGPT session for validation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def request_json(method: str, url: str, *, token: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
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
        raise RuntimeError(f"{method} {url} failed with HTTP {exc.code}: {payload}") from exc


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
    return {
        "id": case.get("id"),
        "industry": case.get("industry"),
        "query": case.get("query"),
        "elapsed_ms": elapsed_ms,
        "expect": case.get("expect") or {},
        "actual": {
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
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TrustVault query regression cases")
    parser.add_argument("--base-url", default=os.environ.get("TRUSTVAULT_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--token", default=os.environ.get("TRUSTVAULT_TOKEN") or os.environ.get("TOKEN"))
    parser.add_argument("--output", default="")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    if not args.token:
        print("Set TRUSTVAULT_TOKEN or TOKEN, or pass --token.", file=sys.stderr)
        return 2

    base_url = args.base_url.rstrip("/")
    manifest = request_json("GET", f"{base_url}/api/v1/query/test-cases", token=args.token)
    cases = manifest.get("test_cases") or []
    report: dict[str, Any] = {
        "base_url": base_url,
        "generated_at_epoch": int(time.time()),
        "test_case_count": len(cases),
        "cases": [],
    }

    for case in cases:
        start = time.time()
        try:
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
            report["cases"].append(compact_response(case, response, elapsed_ms))
        except Exception as exc:  # noqa: BLE001 - command-line diagnostic output
            elapsed_ms = int((time.time() - start) * 1000)
            report["cases"].append({
                "id": case.get("id"),
                "industry": case.get("industry"),
                "query": case.get("query"),
                "elapsed_ms": elapsed_ms,
                "expect": case.get("expect") or {},
                "error": str(exc),
            })

    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.write("\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
