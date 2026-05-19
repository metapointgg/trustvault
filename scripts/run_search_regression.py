#!/usr/bin/env python3
"""Run TrustVault search/query regression checks and write one shareable JSON file.

This script is intentionally dependency-free and uses Python's standard library only.

Examples:
    export TOKEN="<jwt>"
    python3 scripts/run_search_regression.py

    python3 scripts/run_search_regression.py \
      --base-url http://localhost:8000 \
      --token "$TOKEN" \
      --output local-data/search-regression/search-regression.json

The generated JSON file is designed to be shared for diagnosis. It includes:
- environment and runtime metadata;
- each request payload;
- HTTP status and response body;
- structured query summary;
- execution result count;
- diagnostics;
- automatically detected issues.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_LIMIT = 50


TESTS: list[dict[str, Any]] = [
    # 1. Archive/status checks
    {
        "id": "archive_status_endpoint",
        "group": "Archive/status checks",
        "kind": "get",
        "path": "/api/v1/query/archive/status",
        "description": "Direct archive status endpoint.",
        "expect_non_empty": True,
    },
    {
        "id": "archive_status_nl",
        "group": "Archive/status checks",
        "kind": "execute",
        "query": "Show me the archive status.",
        "expected_capability_any": ["archive_status", "entity_discovery", "evidence_search"],
    },
    {
        "id": "archive_counts_nl",
        "group": "Archive/status checks",
        "kind": "execute",
        "query": "Tell me how many entities, containers and indexed evidence objects are available.",
        "expected_capability_any": ["archive_status", "entity_discovery", "evidence_search"],
    },
    {
        "id": "archive_config_nl",
        "group": "Archive/status checks",
        "kind": "execute",
        "query": "Show the configured source folder, containers folder, index path and exports folder.",
        "expected_capability_any": ["archive_status", "entity_discovery", "evidence_search"],
    },

    # 2. Entity discovery
    {
        "id": "entity_discovery_first_10",
        "group": "Entity discovery",
        "kind": "execute",
        "query": "List the first 10 entities.",
        "expected_capability": "entity_discovery",
        "expected_execution_source": "entity_metadata",
        "expect_result_count_min": 1,
    },
    {
        "id": "entity_discovery_high_risk",
        "group": "Entity discovery",
        "kind": "execute",
        "query": "Show me customers who are high risk.",
        "expected_capability": "entity_discovery",
        "expected_execution_source": "entity_metadata",
        "expect_result_count_min": 1,
    },
    {
        "id": "entity_discovery_high_risk_guernsey",
        "group": "Entity discovery",
        "kind": "execute",
        "query": "List high risk entities in Guernsey.",
        "expected_capability": "entity_discovery",
        "expected_execution_source": "entity_metadata",
        "expect_result_count_min": 1,
    },
    {
        "id": "entity_discovery_medium_risk_jersey",
        "group": "Entity discovery",
        "kind": "execute",
        "query": "List medium risk entities in Jersey.",
        "expected_capability": "entity_discovery",
        "expected_execution_source": "entity_metadata",
    },
    {
        "id": "entity_discovery_low_risk_uk",
        "group": "Entity discovery",
        "kind": "execute",
        "query": "List low risk entities in the United Kingdom.",
        "expected_capability": "entity_discovery",
        "expected_execution_source": "entity_metadata",
    },

    # 3. Entity summary
    {
        "id": "entity_summary_cust_000001",
        "group": "Entity summary",
        "kind": "execute",
        "query": "Summarise entity CUST-000001.",
        "entity_external_id": "CUST-000001",
        "expected_scope": "entity",
    },
    {
        "id": "entity_fits_containers_cust_000001",
        "group": "Entity summary",
        "kind": "execute",
        "query": "Show the FITS containers available for CUST-000001.",
        "entity_external_id": "CUST-000001",
        "expected_scope": "entity",
    },
    {
        "id": "entity_counts_by_category_cust_000001",
        "group": "Entity summary",
        "kind": "execute",
        "query": "Show the evidence counts by category and document type for CUST-000001.",
        "entity_external_id": "CUST-000001",
        "expected_scope": "entity",
    },
    {
        "id": "entity_retention_summary_cust_000001",
        "group": "Entity summary",
        "kind": "execute",
        "query": "Show the retention and legal hold summary for CUST-000001.",
        "entity_external_id": "CUST-000001",
        "expected_scope": "entity",
    },

    # 4. Direct FITS search for selected customer
    {
        "id": "direct_fits_sow_cust_000001",
        "group": "Direct FITS search for selected customer",
        "kind": "execute",
        "query": "Search the FITS container for CUST-000001 for source of wealth evidence.",
        "entity_external_id": "CUST-000001",
        "expected_execute_with": "direct_fits",
        "expected_execution_source": "direct_fits_container",
        "expect_result_count_min": 1,
    },
    {
        "id": "direct_fits_onboarding_cust_000001",
        "group": "Direct FITS search for selected customer",
        "kind": "execute",
        "query": "Search CUST-000001 directly for onboarding documentation.",
        "entity_external_id": "CUST-000001",
        "expected_execute_with": "direct_fits",
        "expected_execution_source": "direct_fits_container",
    },
    {
        "id": "direct_fits_poa_cust_000001",
        "group": "Direct FITS search for selected customer",
        "kind": "execute",
        "query": "Search CUST-000001 for proof of address evidence.",
        "entity_external_id": "CUST-000001",
        "expected_execute_with": "direct_fits",
        "expected_execution_source": "direct_fits_container",
        "expect_result_count_min": 1,
    },
    {
        "id": "direct_fits_identity_cust_000001",
        "group": "Direct FITS search for selected customer",
        "kind": "execute",
        "query": "Search CUST-000001 for passport or identity evidence.",
        "entity_external_id": "CUST-000001",
        "expected_execute_with": "direct_fits",
        "expected_execution_source": "direct_fits_container",
        "expect_result_count_min": 1,
    },
    {
        "id": "direct_fits_screening_cust_000001",
        "group": "Direct FITS search for selected customer",
        "kind": "execute",
        "query": "Search CUST-000001 for screening evidence.",
        "entity_external_id": "CUST-000001",
        "expected_execute_with": "direct_fits",
        "expected_execution_source": "direct_fits_container",
        "expect_result_count_min": 1,
    },
    {
        "id": "direct_fits_due_diligence_correspondence_cust_000001",
        "group": "Direct FITS search for selected customer",
        "kind": "execute",
        "query": "Search CUST-000001 for correspondence about due diligence.",
        "entity_external_id": "CUST-000001",
        "expected_execute_with": "direct_fits",
        "expected_execution_source": "direct_fits_container",
    },

    # 5. Cross-archive search
    {
        "id": "archive_search_sof",
        "group": "Cross-archive search",
        "kind": "execute",
        "query": "Search the archive for source of funds evidence.",
        "expected_execution_source": "fits_index",
        "expect_result_count_min": 1,
    },
    {
        "id": "archive_search_onboarding_high_guernsey",
        "group": "Cross-archive search",
        "kind": "execute",
        "query": "Show me all onboarding documentation for high risk clients in Guernsey.",
        "expected_execution_source": "fits_index",
        "expected_snapshot_id": "ONBOARDING",
        "expect_result_count_min": 1,
    },
    {
        "id": "archive_search_cdd_high",
        "group": "Cross-archive search",
        "kind": "execute",
        "query": "Find CDD review evidence for high risk customers.",
        "expected_execution_source": "fits_index",
        "expect_result_count_min": 1,
    },
    {
        "id": "archive_search_screening_guernsey",
        "group": "Cross-archive search",
        "kind": "execute",
        "query": "Find all screening evidence for Guernsey customers.",
        "expected_execution_source": "fits_index",
        "expect_result_count_min": 1,
    },
    {
        "id": "archive_search_missing_documents_correspondence",
        "group": "Cross-archive search",
        "kind": "execute",
        "query": "Search for customer correspondence mentioning missing documents.",
        "expected_execution_source": "fits_index",
    },
    {
        "id": "archive_search_regulator_sow_response",
        "group": "Cross-archive search",
        "kind": "execute",
        "query": "Find evidence that would help respond to a regulator asking about source of wealth.",
        "expected_execution_source": "fits_index",
        "expect_result_count_min": 1,
    },

    # 6. Query interpretation tests
    {
        "id": "interpret_onboarding_high_guernsey",
        "group": "Query interpretation tests",
        "kind": "interpret",
        "query": "Show me all onboarding documentation for high risk clients in Guernsey.",
        "expected_snapshot_id": "ONBOARDING",
        "forbidden_document_type": "ONBOARDING",
    },
    {
        "id": "interpret_missing_poa_high_guernsey",
        "group": "Query interpretation tests",
        "kind": "interpret",
        "query": "Which high risk clients in Guernsey are missing proof of address?",
        "expected_capability": "completeness_check",
    },
    {
        "id": "interpret_sow_and_screening_high",
        "group": "Query interpretation tests",
        "kind": "interpret",
        "query": "Show me source of wealth and screening evidence for high risk customers.",
    },
    {
        "id": "interpret_onboarding_complete_cust_000001",
        "group": "Query interpretation tests",
        "kind": "interpret",
        "query": "Is the onboarding file complete for CUST-000001?",
        "entity_external_id": "CUST-000001",
        "expected_capability": "completeness_check",
    },

    # 7. Execute natural-language queries
    {
        "id": "execute_onboarding_high_guernsey",
        "group": "Execute natural-language queries",
        "kind": "execute",
        "query": "Show me all onboarding documentation for high risk clients in Guernsey.",
        "expected_snapshot_id": "ONBOARDING",
        "expected_execution_source": "fits_index",
        "expect_result_count_min": 1,
    },
    {
        "id": "execute_missing_poa",
        "group": "Execute natural-language queries",
        "kind": "execute",
        "query": "Which customers are missing proof of address?",
        "expected_capability": "completeness_check",
    },
    {
        "id": "execute_sow_cust_000001",
        "group": "Execute natural-language queries",
        "kind": "execute",
        "query": "Show me source of wealth evidence.",
        "entity_external_id": "CUST-000001",
        "expected_execute_with": "direct_fits",
        "expect_result_count_min": 1,
    },
    {
        "id": "execute_money_source_cust_000001",
        "group": "Execute natural-language queries",
        "kind": "execute",
        "query": "What evidence explains where the customer money came from?",
        "entity_external_id": "CUST-000001",
    },
    {
        "id": "execute_high_risk_with_sof",
        "group": "Execute natural-language queries",
        "kind": "execute",
        "query": "Find high risk customers with source of funds evidence.",
        "expected_execution_source": "fits_index",
        "expect_result_count_min": 1,
    },

    # 8. Completeness checks
    {
        "id": "completeness_cust_000001",
        "group": "Completeness checks",
        "kind": "execute",
        "query": "Check evidence completeness for CUST-000001.",
        "entity_external_id": "CUST-000001",
        "expected_capability": "completeness_check",
    },
    {
        "id": "completeness_high_guernsey",
        "group": "Completeness checks",
        "kind": "execute",
        "query": "Check completeness for high risk customers in Guernsey.",
        "expected_capability": "completeness_check",
    },
    {
        "id": "completeness_incomplete_high",
        "group": "Completeness checks",
        "kind": "execute",
        "query": "Show only incomplete high risk customer files.",
        "expected_capability": "completeness_check",
    },
    {
        "id": "completeness_missing_mandatory",
        "group": "Completeness checks",
        "kind": "execute",
        "query": "Identify customers missing mandatory evidence.",
        "expected_capability": "completeness_check",
    },
    {
        "id": "completeness_onboarding_cust_000001",
        "group": "Completeness checks",
        "kind": "execute",
        "query": "Check whether the onboarding evidence is complete for CUST-000001.",
        "entity_external_id": "CUST-000001",
        "expected_capability": "completeness_check",
    },

    # 9. Payload metadata checks - dynamic object id resolved by seed query where possible
    {
        "id": "payload_metadata_basic",
        "group": "Payload metadata checks",
        "kind": "execute",
        "query": "Show metadata for object {object_id} for entity {object_entity}.",
        "requires_object_id": True,
        "entity_external_id_template": "{object_entity}",
    },
    {
        "id": "payload_metadata_filename_hash_preview",
        "group": "Payload metadata checks",
        "kind": "execute",
        "query": "Show the filename, document type, category, source system, SHA-256 and safe preview for object {object_id} for {object_entity}.",
        "requires_object_id": True,
        "entity_external_id_template": "{object_entity}",
    },
    {
        "id": "payload_metadata_retention_hold",
        "group": "Payload metadata checks",
        "kind": "execute",
        "query": "Show the retention metadata and legal hold status for object {object_id} for {object_entity}.",
        "requires_object_id": True,
        "entity_external_id_template": "{object_entity}",
    },
]


class TrustVaultRegressionRunner:
    def __init__(self, base_url: str, token: str | None, mode: str, limit: int, include_ai_summary: bool, timeout: int):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.mode = mode
        self.limit = limit
        self.include_ai_summary = include_ai_summary
        self.timeout = timeout
        self.dynamic_values: dict[str, str] = {}

    def run(self) -> dict[str, Any]:
        started = datetime.now(timezone.utc)
        report: dict[str, Any] = {
            "product": "TrustVault",
            "purpose": "search_query_regression_capture",
            "started_at": started.isoformat(),
            "base_url": self.base_url,
            "mode": self.mode,
            "include_ai_summary": self.include_ai_summary,
            "limit": self.limit,
            "python": sys.version,
            "platform": platform.platform(),
            "token_supplied": bool(self.token),
            "dynamic_values": {},
            "tests": [],
            "summary": {},
        }

        report["preflight"] = self._preflight()
        self._resolve_dynamic_object_id(report)
        report["dynamic_values"] = dict(self.dynamic_values)

        for test in TESTS:
            test_result = self._run_test(test)
            report["tests"].append(test_result)

        finished = datetime.now(timezone.utc)
        report["finished_at"] = finished.isoformat()
        report["duration_seconds"] = round((finished - started).total_seconds(), 3)
        report["summary"] = self._summarise_report(report)
        return report

    def _preflight(self) -> dict[str, Any]:
        checks = []
        for name, path in [
            ("health", "/api/v1/health"),
            ("archive_status", "/api/v1/query/archive/status"),
            ("scenarios", "/api/v1/query/scenarios"),
        ]:
            checks.append({"name": name, **self._request("GET", path)})
        return {"checks": checks}

    def _resolve_dynamic_object_id(self, report: dict[str, Any]) -> None:
        object_id = os.environ.get("TRUSTVAULT_TEST_OBJECT_ID") or os.environ.get("OBJECT_ID")
        object_entity = os.environ.get("TRUSTVAULT_TEST_OBJECT_ENTITY") or os.environ.get("OBJECT_ENTITY") or "CUST-000001"
        if object_id:
            self.dynamic_values["object_id"] = object_id
            self.dynamic_values["object_entity"] = object_entity
            return

        seed_payload = {
            "query": "Search CUST-000001 for passport or identity evidence.",
            "entity_external_id": "CUST-000001",
            "mode": self.mode,
            "include_ai_summary": False,
            "limit": 5,
        }
        seed = self._request("POST", "/api/v1/query/execute", seed_payload)
        report["dynamic_object_seed"] = seed
        data = seed.get("json") if isinstance(seed.get("json"), dict) else {}
        rows = (((data.get("result") or {}).get("results")) or []) if isinstance(data, dict) else []
        for row in rows:
            candidate = row.get("evidence_object_id") if isinstance(row, dict) else None
            entity = row.get("entity_external_id") if isinstance(row, dict) else None
            if candidate:
                self.dynamic_values["object_id"] = str(candidate)
                self.dynamic_values["object_entity"] = str(entity or object_entity)
                return
        self.dynamic_values["object_id"] = "OBJ-000001"
        self.dynamic_values["object_entity"] = object_entity

    def _run_test(self, test: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        result: dict[str, Any] = {
            "id": test["id"],
            "group": test["group"],
            "kind": test["kind"],
            "description": test.get("description"),
            "issues": [],
        }
        try:
            if test["kind"] == "get":
                response = self._request("GET", test["path"])
                result["request"] = {"method": "GET", "path": test["path"]}
            else:
                query = self._format_template(test["query"])
                entity_external_id = test.get("entity_external_id")
                if not entity_external_id and test.get("entity_external_id_template"):
                    entity_external_id = self._format_template(test["entity_external_id_template"])
                payload: dict[str, Any] = {
                    "query": query,
                    "mode": self.mode,
                }
                if entity_external_id:
                    payload["entity_external_id"] = entity_external_id
                if test["kind"] == "execute":
                    payload["include_ai_summary"] = self.include_ai_summary
                    payload["limit"] = self.limit
                    path = "/api/v1/query/execute"
                elif test["kind"] == "interpret":
                    path = "/api/v1/query/interpret"
                else:
                    raise ValueError(f"Unsupported test kind: {test['kind']}")
                response = self._request("POST", path, payload)
                result["request"] = {"method": "POST", "path": path, "payload": payload}

            result["response"] = response
            result["derived"] = self._derive(response)
            result["issues"].extend(self._check_expectations(test, response, result["derived"]))
        except Exception as exc:  # noqa: BLE001 - regression script should capture everything
            result["issues"].append("script_exception")
            result["exception"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
        result["duration_seconds"] = round(time.perf_counter() - started, 3)
        return result

    def _format_template(self, value: str) -> str:
        return value.format(**self.dynamic_values)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(url, data=body, method=method, headers=headers)
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
                return self._response_payload(response.status, dict(response.headers), raw, time.perf_counter() - started)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            return self._response_payload(exc.code, dict(exc.headers), raw, time.perf_counter() - started)
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "status": None,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }

    def _response_payload(self, status: int, headers: dict[str, Any], raw: str, elapsed: float) -> dict[str, Any]:
        parsed: Any | None = None
        parse_error: str | None = None
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError as exc:
            parse_error = str(exc)
        return {
            "ok": 200 <= status < 300,
            "status": status,
            "elapsed_seconds": round(elapsed, 3),
            "headers_subset": {
                "content-type": headers.get("content-type") or headers.get("Content-Type"),
            },
            "json": parsed,
            "text": None if parsed is not None else raw[:4000],
            "json_parse_error": parse_error,
        }

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

    def _summarise_report(self, report: dict[str, Any]) -> dict[str, Any]:
        tests = report.get("tests", [])
        issue_counts: dict[str, int] = {}
        failing_tests = []
        by_group: dict[str, dict[str, int]] = {}
        for test in tests:
            group = test.get("group", "Unknown")
            by_group.setdefault(group, {"total": 0, "failed": 0})
            by_group[group]["total"] += 1
            issues = test.get("issues") or []
            if issues:
                by_group[group]["failed"] += 1
                failing_tests.append({"id": test.get("id"), "group": group, "issues": issues})
            for issue in issues:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
        return {
            "total_tests": len(tests),
            "passed_tests": len([test for test in tests if not test.get("issues")]),
            "failed_tests": len(failing_tests),
            "failing_tests": failing_tests,
            "issue_counts": issue_counts,
            "by_group": by_group,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run TrustVault search/query regression tests and write one JSON output file.")
    parser.add_argument("--base-url", default=os.environ.get("TRUSTVAULT_API_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--token", default=os.environ.get("TRUSTVAULT_TOKEN") or os.environ.get("TOKEN"))
    parser.add_argument("--mode", default=os.environ.get("TRUSTVAULT_QUERY_MODE", "auto"), choices=["auto", "ai", "deterministic"])
    parser.add_argument("--limit", type=int, default=int(os.environ.get("TRUSTVAULT_QUERY_LIMIT", DEFAULT_LIMIT)))
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("TRUSTVAULT_QUERY_TIMEOUT", 90)))
    parser.add_argument("--no-ai-summary", action="store_true", help="Do not request AI summaries during execute tests.")
    parser.add_argument("--output", default=None, help="Output JSON file. Defaults to local-data/search-regression/search-regression-<timestamp>.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = Path(args.output or f"local-data/search-regression/search-regression-{timestamp}.json")
    output.parent.mkdir(parents=True, exist_ok=True)

    runner = TrustVaultRegressionRunner(
        base_url=args.base_url,
        token=args.token,
        mode=args.mode,
        limit=args.limit,
        include_ai_summary=not args.no_ai_summary,
        timeout=args.timeout,
    )
    report = runner.run()
    output.write_text(json.dumps(report, indent=2, sort_keys=False), encoding="utf-8")

    summary = report["summary"]
    print(f"Wrote regression report: {output}")
    print(f"Tests: {summary['total_tests']} | Passed: {summary['passed_tests']} | Failed: {summary['failed_tests']}")
    if summary["failed_tests"]:
        print("Failing tests:")
        for failure in summary["failing_tests"]:
            print(f"- {failure['id']} [{failure['group']}]: {', '.join(failure['issues'])}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
