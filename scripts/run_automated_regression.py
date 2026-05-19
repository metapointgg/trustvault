#!/usr/bin/env python3
"""Run the TrustVault automated regression suite.

This wrapper turns scripts/run_search_regression.py into a CI/local smoke test:

- obtains a local-auth token when credentials are supplied;
- writes a stable latest-search-regression.json artifact;
- writes a timestamped copy for history;
- exits non-zero when the regression report contains failures.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_search_regression import DEFAULT_BASE_URL, TrustVaultRegressionRunner


DEFAULT_OUTPUT_DIR = Path("local-data/search-regression")


def _json_request(method: str, url: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return {"ok": 200 <= response.status < 300, "status": response.status, "json": json.loads(raw) if raw else {}}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return {"ok": False, "status": exc.code, "json": parsed}


def _wait_for_health(base_url: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    last_error: str | None = None
    while time.time() < deadline:
        try:
            response = _json_request("GET", f"{base_url}/api/v1/health", timeout=10)
            if response.get("ok"):
                return
            last_error = f"status {response.get('status')}: {response.get('json')}"
        except Exception as exc:  # noqa: BLE001 - local automation should keep polling
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(2)
    raise RuntimeError(f"TrustVault API did not become healthy within {timeout_seconds}s. Last error: {last_error}")


def _login(base_url: str, email: str, verifier: str, timeout: int) -> str:
    response = _json_request(
        "POST",
        f"{base_url}/api/v1/auth/login",
        {"email": email, "verifier": verifier},
        timeout=timeout,
    )
    if not response.get("ok"):
        raise RuntimeError(f"Login failed with status {response.get('status')}: {response.get('json')}")
    token = str((response.get("json") or {}).get("access_token") or "")
    if not token:
        raise RuntimeError("Login response did not include an access_token.")
    return token


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run TrustVault automated search/query regression tests.")
    parser.add_argument("--base-url", default=os.environ.get("TRUSTVAULT_API_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--token", default=os.environ.get("TRUSTVAULT_TOKEN") or os.environ.get("TOKEN"))
    parser.add_argument("--email", default=os.environ.get("TRUSTVAULT_REGRESSION_EMAIL") or os.environ.get("TRUSTVAULT_LOCAL_ADMIN_EMAIL"))
    parser.add_argument("--verifier", default=os.environ.get("TRUSTVAULT_REGRESSION_VERIFIER") or os.environ.get("TRUSTVAULT_LOCAL_ADMIN_PASSWORD"))
    parser.add_argument("--mode", default=os.environ.get("TRUSTVAULT_QUERY_MODE", "auto"), choices=["auto", "ai", "deterministic"])
    parser.add_argument("--limit", type=int, default=int(os.environ.get("TRUSTVAULT_QUERY_LIMIT", "50")))
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("TRUSTVAULT_QUERY_TIMEOUT", "90")))
    parser.add_argument("--health-timeout", type=int, default=int(os.environ.get("TRUSTVAULT_HEALTH_TIMEOUT", "120")))
    parser.add_argument("--no-ai-summary", action="store_true")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    _wait_for_health(base_url, args.health_timeout)

    token = args.token
    if not token and args.email and args.verifier:
        token = _login(base_url, args.email, args.verifier, args.timeout)
    if not token:
        raise RuntimeError("Provide TRUSTVAULT_TOKEN or TRUSTVAULT_REGRESSION_EMAIL/TRUSTVAULT_REGRESSION_VERIFIER.")

    runner = TrustVaultRegressionRunner(
        base_url=base_url,
        token=token,
        mode=args.mode,
        limit=args.limit,
        include_ai_summary=not args.no_ai_summary,
        timeout=args.timeout,
    )
    report = runner.run()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    latest = output_dir / "latest-search-regression.json"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    historical = output_dir / f"search-regression-{timestamp}.json"
    payload = json.dumps(report, indent=2, sort_keys=False)
    latest.write_text(payload, encoding="utf-8")
    historical.write_text(payload, encoding="utf-8")

    summary = report["summary"]
    print(f"Wrote latest regression report: {latest}")
    print(f"Wrote timestamped regression report: {historical}")
    print(f"Tests: {summary['total_tests']} | Passed: {summary['passed_tests']} | Failed: {summary['failed_tests']}")
    if summary["failed_tests"]:
        for failure in summary["failing_tests"]:
            print(f"- {failure['id']} [{failure['group']}]: {', '.join(failure['issues'])}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
