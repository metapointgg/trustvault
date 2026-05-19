#!/usr/bin/env bash
set -euo pipefail

FIXTURE=${1:?Usage: ./scripts/smoke_test_cust_000001.sh /path/to/CUST-000001.zip}
BASE_URL=${TRUSTVAULT_API_BASE_URL:-http://localhost:8000}

echo "Checking health"
curl -fsS "$BASE_URL/health" | python3 -m json.tool >/dev/null

echo "Uploading source folder fixture"
curl -fsS -X POST "$BASE_URL/api/v1/ingestion/source-folder/upload" \
  -F "file=@$FIXTURE" | python3 -m json.tool

echo "Inspecting FITS archive"
curl -fsS "$BASE_URL/api/v1/fits/entities/CUST-000001/inspect" | python3 -m json.tool >/dev/null

echo "Validating integrity"
curl -fsS "$BASE_URL/api/v1/integrity/entities/CUST-000001" | python3 -m json.tool >/dev/null

echo "Testing direct FITS search"
curl -fsS -X POST "$BASE_URL/api/v1/fits/entities/CUST-000001/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"passport","limit":50}' | python3 -m json.tool >/dev/null

echo "Testing completeness"
curl -fsS -X POST "$BASE_URL/api/v1/completeness/entities/CUST-000001/evaluate" \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool >/dev/null

echo "Testing duplicate upload idempotency"
curl -fsS -X POST "$BASE_URL/api/v1/ingestion/source-folder/upload" \
  -F "file=@$FIXTURE" | python3 -m json.tool

echo "Smoke test completed"
