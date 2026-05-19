# TrustVault

**TrustVault — secure evidence preservation, search and assurance for regulated entity records.**

TrustVault is an evidence preservation and assurance platform for regulated financial-services organisations. It converts fragmented entity evidence from legacy systems, document stores, email archives, scanning processes and operational platforms into self-contained, verifiable **FITS evidence archives** with searchable metadata, completeness controls, audit trails, retention controls, integrity checks and regulator-ready export capability.

The core design principle is that the FITS archive remains the source of truth. PostgreSQL, indexes, summaries and UI views are operational projections that can be rebuilt from preserved evidence archives.

---

## Timestamped implementation log

### 2026-05-19 — Categorisation, customer information assurance gaps and inline PDF evidence viewing

Implemented and documented the following updates on branch `trustvault-production-ready-reset`:

1. Added filename-driven document classification through `DocumentClassificationService`.
2. Added predefined Document Type to Category mappings for regulated evidence, including Passport, Proof of Address, Source of Funds, Source of Wealth, CDD Review, Application, Screening Evidence, EDD Approval, corporate evidence, statements, correspondence, customer metadata and legacy payloads.
3. Added settings APIs for document classification:
   - `GET /api/v1/settings/document-classification`
   - `PUT /api/v1/settings/document-classification`
4. Added a Document Classification panel in Settings so administrators can review the seeded mappings and add further document type/category/pattern mappings.
5. Added uncategorised evidence retrieval:
   - `GET /api/v1/evidence/uncategorised`
6. Added manual evidence classification update:
   - `PATCH /api/v1/evidence/classification`
7. Added a Categorisation screen that allows users to select uncategorised documents and use **Set** to apply only the **Document Type**. The Category is then derived from Settings.
8. Changed source-folder ingestion so folder names are retained as provenance/hints, but the preferred classification route is:

```text
filename -> Document Type -> Category
```

Example:

```text
mike_ozanne_passport.pdf -> Passport -> Identity
```

9. Added support for ingesting a customer where `customer.json` is absent or incomplete. TrustVault creates the entity and records an open **Customer Information assurance gap** that can be resolved manually in the Categorisation screen.
10. Moved the operational workflow away from folder-driven ingestion by promoting Categorisation into the Operations menu and hiding direct Ingestion from non-admin users.
11. Added `pdfrx` as the Flutter PDF rendering dependency and introduced an authenticated PDF evidence viewer using `PdfViewer.data(...)` against bytes fetched through the authenticated API client.
12. Replaced the previous PDF preview placeholder in the entity evidence preview modal with inline PDF rendering. The existing Open action is retained as a fallback/access route.

Files touched or relevant to this update:

```text
backend/src/trustvault/core/document_classification.py
backend/src/trustvault/core/source_folder_ingestion.py
backend/src/trustvault/api/routes/evidence.py
backend/src/trustvault/api/routes/settings.py
backend/src/trustvault/api/routes/customers.py
frontend/trustvault_app/pubspec.yaml
frontend/trustvault_app/lib/core/api/trustvault_api_client.dart
frontend/trustvault_app/lib/features/categorisation/categorisation_screen.dart
frontend/trustvault_app/lib/features/entities/entities_screen.dart
frontend/trustvault_app/lib/features/settings/settings_screen.dart
frontend/trustvault_app/lib/shared/app_shell.dart
frontend/trustvault_app/lib/shared/evidence_pdf_viewer.dart
```

---

## Current client evidence folder guidance

TrustVault still supports production-style ZIP ingestion, but classification should no longer depend on the physical folder where a file was placed.

### Recommended ZIP shape

```text
CUST-000001/
  customer.json                         optional but recommended
  documents/
    mike_ozanne_passport.pdf
    mike_ozanne_utility_bill.pdf
    mike_ozanne_source_of_funds.pdf
    mike_ozanne_bank_statement_jan_2026.pdf
  emails/
    onboarding_email.eml
  extracts/
    legacy_customer_extract.csv
  sidecar/
    mike_ozanne_passport.search.txt
```

### Still-supported legacy ZIP shape

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

### Classification model

Classification now follows this order of preference:

1. Explicit metadata already present on the evidence object.
2. Filename-driven classification using Settings mappings.
3. Source path/folder as a weak hint only.
4. Manual classification through the Categorisation screen.

The intended operating model is that file names are meaningful enough to suggest document type:

```text
mike_ozanne_passport.pdf       -> Passport          -> Identity
mike_ozanne_utility_bill.pdf   -> Proof of Address  -> Address
mike_ozanne_source_of_funds.pdf -> Source of Funds  -> Source of Funds
```

Where classification is not possible, evidence appears in the Categorisation screen as uncategorised.

---

## Customer information assurance gap

`customer.json` is now optional for ingestion, but it remains recommended.

If `customer.json` is missing or incomplete, TrustVault will:

1. create or update the entity using the ZIP root or generated fallback identifier;
2. ingest and preserve the evidence;
3. mark customer information as incomplete;
4. create an open `customer_information_missing` assurance gap;
5. allow users to resolve the gap manually from the Categorisation screen;
6. rebuild the affected FITS archive and index once the customer information is completed.

Recommended customer metadata fields:

```json
{
  "entity_id": "CUST-000001",
  "display_name": "Mike Ozanne",
  "entity_type": "customer",
  "jurisdiction": "Guernsey",
  "risk_rating": "Medium"
}
```

---

## Evidence viewing

TrustVault supports viewing preserved evidence from entity evidence lists and search results.

Current preview behaviour:

- images render inline;
- text and `.eml` evidence render as safe text previews;
- PDF evidence renders inline using `pdfrx` and authenticated bytes from `/api/v1/evidence/{id}/file`;
- binary/unknown evidence displays a no-inline-preview message;
- Open and download routes remain available for fallback access.

The PDF implementation deliberately uses authenticated byte download rather than unauthenticated URL loading so that the viewer remains compatible with protected evidence routes.

---

## Repository structure

```text
trustvault/
  backend/
    alembic.ini
    migrations/
    src/trustvault/
      ai/
      api/
      audit/
      auth/
      core/
      db/
      storage/
      worker/
  frontend/
    trustvault_app/
      lib/
        core/
        features/
        shared/
  deployment/
  docker-compose.yml
  README.md
```

---

## Runtime components

The local Docker Compose build currently runs:

- `api` — FastAPI backend;
- `worker` — TrustVault worker process;
- `postgres` — PostgreSQL database.

The Flutter app is usually run separately during development.

---

## Local development quick start

From the repository root:

```bash
cd "/Users/mikeozanne/Projects Git/trustvault"
docker compose up -d --build
```

Backend API:

```text
http://localhost:8000
```

Health endpoint:

```bash
curl -s http://localhost:8000/api/v1/health | python3 -m json.tool
```

Flutter app:

```bash
cd frontend/trustvault_app
flutter pub get
flutter run -d chrome --dart-define=TRUSTVAULT_API_BASE_URL=http://localhost:8000
```

When dependencies change, run:

```bash
cd frontend/trustvault_app
flutter pub get
```

When backend models or routes change, rebuild the containers:

```bash
cd "/Users/mikeozanne/Projects Git/trustvault"
docker compose down --remove-orphans
docker compose up -d --build --force-recreate
```

---

## Core architecture

TrustVault is **FITS-native**.

The intended operating model is:

- one entity has one current self-contained FITS evidence archive;
- previous FITS archive versions may be preserved and superseded;
- FITS containers contain original payloads, manifest metadata, provenance, OCR/search text, lifecycle snapshots and hash reports;
- PostgreSQL stores operational state, job orchestration, audit logging, rulesets, users, completeness results, settings and rebuildable index/cache data;
- selected-entity searches can read directly from the FITS archive;
- cross-archive searches use PostgreSQL index projections rebuilt from FITS;
- AI is optional, local/private and evidence-bound;
- export gives controlled access to preserved FITS containers and derived evidence packs.

Do not treat generated reports, UI grids or AI summaries as the archive. The preserved FITS evidence container and payload hashes remain authoritative.

---

## Key functional areas

### Authentication and users

TrustVault includes local authentication, JWT-based API calls, local user administration and role-aware UI/backend foundations.

### Entities

The Entities screen shows entity metadata, risk rating, jurisdiction, evidence counts, FITS status and evidence actions. Entity evidence opens into a grid and then into previews.

### Categorisation

The Categorisation screen is the operational remediation point for:

- uncategorised evidence;
- manual document type assignment;
- Customer Information assurance gaps created during ingestion.

### Completeness

Completeness evaluates required evidence against configured rulesets. It supports archive-wide and selected-entity views, including filters for risk rating and jurisdiction.

### Rulesets

Rulesets define required evidence using rule key, category, document type, required flag, maximum age and applies-when metadata.

### Search and query

Search supports natural language query interpretation, selected-entity FITS search, cross-archive indexed search, completeness-style missing evidence queries and optional local AI summaries.

### Extraction

Extraction reports show OCR/search-text coverage, character counts, extraction status and extraction preview detail.

### Retention and legal hold

Retention views show retention class, retention-until date, legal hold state and deletion eligibility metadata.

### Integrity

Integrity checks validate preserved FITS containers and payload hashes.

### Export

Export supports downloading preserved FITS evidence archives. Derived regulator-ready packs remain a production enhancement area.

### Audit

Audit captures operational events such as ingestion, search, preview, export, settings and job activity.

### Settings

Settings now include both runtime configuration and Document Classification mappings.

---

## API surface summary

Representative API areas:

```text
/api/v1/auth/*
/api/v1/settings/*
/api/v1/settings/document-classification
/api/v1/health
/api/v1/dashboard/summary
/api/v1/customers
/api/v1/entities
/api/v1/evidence/*
/api/v1/evidence/uncategorised
/api/v1/evidence/classification
/api/v1/ingestion/*
/api/v1/auto-ingestion/*
/api/v1/fits/*
/api/v1/containers/*
/api/v1/query/*
/api/v1/completeness/*
/api/v1/extraction/*
/api/v1/retention/*
/api/v1/integrity/*
/api/v1/export/*
/api/v1/rulesets/*
/api/v1/jobs/*
/api/v1/audit/*
/api/v1/licence/*
```

Useful smoke-test calls:

```bash
curl -s "http://localhost:8000/api/v1/health" | python3 -m json.tool
curl -s "http://localhost:8000/api/v1/customers" | python3 -m json.tool
curl -s "http://localhost:8000/api/v1/settings/document-classification" | python3 -m json.tool
curl -s "http://localhost:8000/api/v1/evidence/uncategorised" | python3 -m json.tool
curl -s "http://localhost:8000/api/v1/completeness/summary" | python3 -m json.tool
```

For authenticated routes, include:

```bash
-H "Authorization: Bearer <token>"
```

---

## Database migrations

The project uses Alembic for database migrations.

Typical commands inside the API container:

```bash
docker compose exec api sh -c "cd /app && python -m alembic -c /app/alembic.ini current"
docker compose exec api sh -c "cd /app && python -m alembic -c /app/alembic.ini upgrade head"
```

Generate a migration:

```bash
docker compose exec api sh -c "cd /app && python -m alembic -c /app/alembic.ini revision --autogenerate -m 'describe change'"
```

If an existing database already matches the initial schema but is not stamped:

```bash
docker compose exec api sh -c "cd /app && python -m alembic -c /app/alembic.ini stamp head"
```

Use `stamp head` carefully. It marks the database as current without applying migrations.

---

## Production hardening roadmap

The current application is a functional product foundation. Before production use, continue work on:

- server-side pagination/filtering for large grids;
- large batch ingestion and quarantine workflows;
- malware scanning for ingested files;
- stronger document classification governance and approval;
- ruleset lifecycle and approval workflow;
- legal hold placement/removal workflow;
- retention policy administration;
- periodic integrity checks and attestations;
- export approval and regulator-ready pack generation;
- tamper-evident audit strategy;
- external IdP/MFA integration;
- signed licence validation and module enforcement;
- structured logging, metrics, backup/restore and runbooks.

---

## Important implementation note

TrustVault's archive/export artefact is the FITS file. Derived reports, AI summaries and UI grids make evidence easier to review, but the preserved FITS container and payload hashes remain the source of truth.
