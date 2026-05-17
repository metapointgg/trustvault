# TrustVault

**TrustVault — secure evidence assurance for regulated customer records.**

TrustVault is an evidence preservation and assurance platform for regulated financial-services clients.
It converts fragmented customer evidence from legacy systems, document stores, email archives and operational platforms into self-contained, verifiable **FITS evidence archives** with searchable metadata, completeness controls, audit trails, retention controls and regulator-ready export capability.

## Core architecture principle

TrustVault is FITS-native:

- one customer/entity has one current self-contained FITS evidence archive;
- previous FITS archive versions may be preserved and superseded;
- the FITS archive is the durable source of truth;
- PostgreSQL is an operational catalogue, job store, audit log and rebuildable index/cache layer;
- selected-customer evidence searches can read directly from the FITS archive;
- cross-customer/cohort searches use PostgreSQL index projections rebuilt from FITS;
- AI is optional, local/private and evidence-bound;
- export means controlled access to the FITS archive itself, plus optional derived reports later.

## Production components

The controlled deployment build contains:

- Python FastAPI backend;
- Python worker process for long-running jobs;
- PostgreSQL for operational state, jobs, audit events, rulesets, completeness results and index/cache data;
- object storage abstraction for filesystem now, with S3 and Azure Blob as production targets;
- queue abstraction, with database-backed local queue now and SQS/Azure queues as production targets;
- Flutter Web application as the primary UI;
- offline licence status foundation;
- evidence-bound optional AI/OCR provider extension points.

## Feature surface

The product surface is organised around:

- Dashboard;
- Health;
- Comparison;
- Customers;
- Search;
- Completeness;
- Rulesets;
- Ingestion;
- Extraction;
- Retention;
- Integrity;
- Export;
- API;
- Jobs;
- Audit;
- Licence.

## Local development

From the repository root:

```bash
docker compose up --build
```

Backend API:

```text
http://localhost:8000
```

Health endpoint:

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

Flutter app:

```bash
cd frontend/trustvault_app
flutter pub get
flutter run -d chrome --dart-define=TRUSTVAULT_API_BASE_URL=http://localhost:8000
```

## Ingest a production-style source folder

TrustVault supports the sample source folder shape used by the original POC and the `CUST-000001.zip` fixture:

```text
CUST-000001/
  metadata/customer.json
  metadata/audit_events.json
  documents/*.pdf
  documents/*.search.txt
  statements/*.pdf
  statements/*.search.txt
  emails/*.eml
  scans/*.jpg
  extracts/*.csv
  large_evidence/*.bin
```

Upload via multipart form:

```bash
curl -X POST "http://localhost:8000/api/v1/ingestion/source-folder/upload" \
  -F "file=@/path/to/CUST-000001.zip" | python3 -m json.tool
```

The upload will:

1. read `metadata/customer.json`;
2. create/update the customer entity;
3. ingest payload files while ignoring macOS sidecar files;
4. capture `.search.txt` sidecar text as searchable/OCR text;
5. store source payloads;
6. rebuild the affected customer FITS archive;
7. rebuild the FITS-derived index for that customer;
8. audit the ingestion.

## Smoke-test commands

After uploading `CUST-000001.zip`:

```bash
curl -s "http://localhost:8000/api/v1/customers" | python3 -m json.tool
curl -s "http://localhost:8000/api/v1/fits/entities/CUST-000001/inspect" | python3 -m json.tool
curl -X POST "http://localhost:8000/api/v1/fits/entities/CUST-000001/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"passport","limit":50}' | python3 -m json.tool
curl -X POST "http://localhost:8000/api/v1/completeness/entities/CUST-000001/evaluate" \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
curl -s "http://localhost:8000/api/v1/retention/entities/CUST-000001" | python3 -m json.tool
curl -s "http://localhost:8000/api/v1/integrity/entities/CUST-000001" | python3 -m json.tool
```

Download the current FITS archive by first locating the current version:

```bash
curl -s "http://localhost:8000/api/v1/containers/entities/CUST-000001/versions" | python3 -m json.tool
```

Then:

```bash
curl -L "http://localhost:8000/api/v1/export/containers/<container_version_id>/fits" \
  -o CUST-000001.fits
```

## Production cloud targets

AWS target:

- ECS Fargate;
- S3 for source imports, FITS containers, versions and derived reports;
- RDS PostgreSQL;
- SQS;
- ECR;
- Secrets Manager;
- KMS;
- CloudWatch;
- VPC/private subnets/VPC endpoints;
- ALB or private load balancer;
- Cognito or client OIDC/SAML.

Azure target:

- Azure Container Apps;
- Blob Storage;
- Azure Database for PostgreSQL;
- Service Bus or Storage Queues;
- Azure Container Registry;
- Key Vault;
- Managed Identity;
- Azure Monitor / Log Analytics;
- Private Endpoints;
- Entra ID.

## Important implementation note

Do not treat derived report packs as the archive model. TrustVault's archive/export artefact is the FITS file. Derived reports can be produced later for readability, approval packs or regulator presentation, but the source of truth remains the FITS container.
