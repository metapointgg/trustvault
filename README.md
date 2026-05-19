# TrustVault

**TrustVault — secure evidence preservation, search and assurance for regulated entity records.**

TrustVault is an evidence preservation and assurance platform for regulated financial-services organisations. It converts fragmented entity evidence from legacy systems, document stores, email archives, scanning processes and operational platforms into self-contained, verifiable **FITS evidence archives** with searchable metadata, completeness controls, audit trails, retention controls, integrity checks and regulator-ready export capability.

The product is designed for use cases such as customer due diligence, onboarding evidence preservation, proof-of-identity and proof-of-address evidence control, source-of-funds/source-of-wealth evidence review, periodic CDD refresh, legal hold management, archive assurance and regulator response preparation.

---

## 1. What TrustVault does

TrustVault provides a controlled evidence archive and assurance layer for regulated entity files.

At a functional level it allows an operator to:

- ingest structured evidence packs for entities;
- preserve original evidence payloads in FITS containers;
- maintain an operational catalogue of entities, evidence objects, FITS versions and metadata;
- search evidence across the archive or directly inside a selected entity FITS archive;
- interpret natural-language queries into structured archive operations;
- optionally use local AI for query interpretation and narrative summaries;
- assess whether required evidence is present or missing using rulesets;
- view extraction status, OCR/search text and extraction events;
- view legal hold, retention class, retention-until and deletion eligibility metadata;
- validate archive integrity using FITS structure, hash checks and payload checks;
- view and export audit events;
- manage local users and roles;
- manage rulesets and rules through the UI;
- export/download preserved FITS containers.

The core design principle is that the FITS archive remains the source of truth. PostgreSQL, indexes, summaries and UI views are operational projections that can be rebuilt from the preserved evidence archive.

---

## 2. Core architecture principle

TrustVault is **FITS-native**.

The intended operating model is:

- one entity has one current self-contained FITS evidence archive;
- previous FITS archive versions may be preserved and superseded;
- FITS containers contain original payloads, manifest metadata, provenance, OCR/search text, snapshots and hash reports;
- PostgreSQL is used for operational state, job orchestration, audit logging, rulesets, user administration, completeness results and rebuildable index/cache data;
- selected-entity searches can read directly from the FITS archive;
- cross-archive/cohort searches use PostgreSQL index projections rebuilt from FITS;
- AI is optional, local/private and evidence-bound;
- export means controlled access to the preserved FITS container, with derived presentation reports being secondary artefacts.

Do not treat generated reports, UI grids or AI summaries as the archive. The source of truth is the preserved FITS evidence container and its payload hashes.

---

## 3. Current repository structure

The repository currently contains:

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
      workers/
  frontend/
    trustvault_app/
      lib/
        core/
        features/
        shared/
  docker-compose.yml
  README.md
```

### Backend

The backend is a Python FastAPI application. It exposes REST APIs for ingestion, entity management, evidence access, FITS operations, query execution, completeness, extraction, retention, integrity, audit, rulesets, jobs, settings, licence status and local authentication.

### Worker

The worker process is used for longer-running background operations, such as queued ingestion, index rebuilds and automatic source-folder processing. The current local deployment uses a database-backed job table.

### Database

PostgreSQL stores operational and rebuildable state, including:

- entities;
- evidence objects;
- FITS container versions;
- FITS index entries;
- source systems;
- rulesets and rules;
- completeness runs and results;
- retention policies;
- extraction events;
- local users;
- application settings;
- jobs;
- audit events;
- licence status.

### Frontend

The frontend is a Flutter Web application. It provides the operational TrustVault UI, including dashboard, health, entities, search/query, completeness, extraction, retention/legal hold, integrity, ingestion, export, jobs, rulesets, settings, audit and user administration screens.

---

## 4. Runtime components

The local Docker Compose build currently runs:

- `api` — FastAPI backend;
- `worker` — TrustVault worker process;
- `postgres` — PostgreSQL database.

The Flutter app is usually run separately during development using `flutter run -d chrome`.

---

## 5. Local development quick start

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

## 6. Authentication and local users

TrustVault currently includes a local authentication foundation.

The current app supports:

- login screen;
- JWT-based authenticated API calls from Flutter;
- local users stored in the application database;
- local roles stored against users;
- initial administrator bootstrap;
- user administration screen;
- role-aware UI and backend foundations.

The intended role model is to allow an administrator to manage users locally in the TrustVault database. This is suitable for the current local/proof-of-concept build and can be extended to enterprise identity providers later.

Future production options include:

- client OIDC;
- SAML;
- Entra ID;
- Cognito;
- role mapping from external identity claims;
- stronger password lifecycle controls;
- MFA;
- full session administration.

---

## 7. FITS evidence archive model

TrustVault uses FITS containers to preserve evidence in a structured, verifiable format.

A FITS container may include:

- primary HDU;
- entity metadata;
- summary HDU;
- lifecycle snapshots;
- manifest;
- provenance;
- OCR/search text;
- hash report;
- container manifest;
- payload HDUs for original evidence files.

The FITS container is designed to be self-contained. It carries the payloads and the metadata required to interpret and validate them.

The operational database stores references, indexes and summaries, but the FITS archive remains the durable archive artefact.

---

## 8. Source folder ingestion

TrustVault supports ingestion of production-style zipped source folders.

The expected source folder shape is:

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
  -H "Authorization: Bearer <token>" \
  -F "file=@/path/to/CUST-000001.zip" | python3 -m json.tool
```

The ingestion process currently:

1. validates and extracts the zip file;
2. reads `metadata/customer.json`;
3. creates or updates the entity;
4. ingests payload files while ignoring macOS sidecar files;
5. captures `.search.txt` sidecar text as searchable/OCR text;
6. parses `.eml` files into searchable email text if no sidecar text is supplied;
7. calculates SHA-256 hashes for payloads;
8. stores evidence objects;
9. generates default retention metadata;
10. rebuilds the entity FITS archive;
11. rebuilds the FITS-derived index for that entity;
12. records audit events.

---

## 9. Automatic source-folder ingestion

TrustVault now includes a foundation for automatic ingestion from a predefined folder.

The intended lifecycle is:

```text
incoming zip dropped into source folder
  -> worker scans configured folder
  -> zip structure is validated
  -> valid zip is ingested
  -> successful zip is moved to processed folder
  -> failed zip is moved to failed folder
  -> job and audit events are recorded
```

The Settings screen exposes automatic ingestion configuration and scan controls.

Current status:

- database-backed jobs exist;
- source-folder scan controls exist;
- automatic ingestion settings exist;
- duplicate detection has been improved but should continue to be hardened for production;
- folder movement and failure reporting should be re-tested for edge cases and large batches.

---

## 10. Entities

The Entities screen provides an operational view of all known entities.

It shows information such as:

- entity external ID;
- display name;
- risk rating;
- jurisdiction;
- entity type;
- status;
- evidence object count;
- whether a current FITS container exists;
- current FITS container version.

The screen now uses a PlutoGrid-backed reusable grid with:

- column sorting;
- column filtering;
- global grid search;
- show/hide columns;
- CSV export;
- dense operational layout;
- row click to open entity evidence;
- action menu for evidence, FITS versions, search, completeness and rebuild actions.

Entity modals also use grids for:

- evidence objects;
- FITS archive versions;
- payload validation results.

---

## 11. Evidence viewing

TrustVault supports viewing preserved evidence from search results and entity evidence lists.

The current UI supports:

- evidence preview modal;
- image preview for JPG-style evidence;
- safe text preview for text and `.eml` content;
- PDF open/download flow;
- evidence file route;
- evidence download route.

Supported evidence types include:

- PDF;
- JPG/image evidence;
- EML/email evidence;
- text/search sidecar evidence;
- CSV/extract-style evidence;
- binary evidence stored as payloads.

Items still to refine:

- embedded PDF viewer inside Flutter Web rather than opening a browser tab;
- richer email rendering with headers, body and attachment metadata;
- improved content-type detection for legacy evidence;
- safer redaction/preview policies by role.

---

## 12. Search and Query

The Search & Query screen is the main evidence discovery interface.

It supports:

- natural-language query entry;
- all-entity search;
- selected-entity search;
- optional local AI interpretation;
- optional AI narrative summary;
- example query browser;
- structured query, interpretation, diagnostics and raw JSON modals;
- result grid with row click behaviour.

### Search execution modes

TrustVault supports several logical search modes:

1. **Archive/cohort search**
   - Uses the rebuilt PostgreSQL FITS index projection.
   - Suitable for questions across many entities.

2. **Selected-entity direct FITS search**
   - Reads directly from the selected entity FITS container.
   - Suitable when the user wants to search preserved evidence for one entity.

3. **Completeness query execution**
   - Used when the query asks for missing evidence, incomplete files or completeness checks.
   - Returns rule-based missing/present rows rather than evidence search rows.

4. **Entity discovery**
   - Used when the query asks to list entities by risk rating, jurisdiction or other metadata.

5. **Archive/status checks**
   - Used when the query asks about archive counts, configuration or system status.

### Example queries

Examples include:

```text
Show me all onboarding documentation for high risk entities in Guernsey.
Show me entities who are high risk and do not have proof of address.
Search the archive for source of funds evidence.
Search CUST-000001 directly for passport or identity evidence.
Summarise entity CUST-000001.
Check evidence completeness for CUST-000001.
Find evidence that would help respond to a regulator asking about source of wealth.
```

---

## 13. Query interpretation and AI

TrustVault has deterministic query interpretation and optional local AI interpretation.

The current AI provider integration is aimed at local/private models, such as LM Studio.

AI can be used for:

- interpreting natural-language queries into structured search/completeness/entity/status operations;
- query expansion;
- AI narrative summaries above grids;
- richer entity summaries;
- completeness summaries.

Important AI constraints:

- AI must not be the source of truth;
- AI must not invent entity IDs, document types or evidence;
- AI must stay evidence-bound;
- preserved FITS evidence and hashes remain authoritative;
- deterministic fallback behaviour is available;
- source/result grids remain the main operational output.

The current AI summary prompt has been tightened to use Entity/Entities terminology and avoid overstating completeness findings. For example, a missing proof-of-address finding should be described as no matched evidence for the required completeness rule, not as a blanket claim that the entity has no files or no evidence.

---

## 14. Completeness

The Completeness screen evaluates required evidence using configured rulesets.

The page now follows the original proof-of-concept pattern more closely:

- Risk rating filter;
- Jurisdiction filter;
- Entity selector with All entities / Selected entity mode;
- AI summary toggle;
- KPI cards;
- rule-level data grid.

The KPI cards show:

- Entities evaluated;
- Complete;
- Incomplete;
- Missing evidence items.

The data grid includes fields such as:

- entity ID;
- entity name;
- entity type;
- risk rating;
- jurisdiction;
- rule status;
- rule key;
- category;
- document type;
- completeness score;
- required count;
- present count;
- missing count;
- matched filename;
- matched evidence object;
- ruleset.

### Batch completeness summary endpoint

To avoid slow first loads and repeated per-entity calls, the UI now uses a batch endpoint:

```text
GET /api/v1/completeness/summary
```

Supported query parameters include:

```text
risk_rating
jurisdiction
entity_external_id
ruleset_id
limit
```

The per-entity auditable evaluation endpoint still exists:

```text
POST /api/v1/completeness/entities/{entity_id}/evaluate
```

Use the summary endpoint for dashboards and grids. Use the evaluate endpoint when a formal completeness review run needs to be recorded.

---

## 15. Rulesets

Rulesets define the evidence requirements used by completeness checks.

A ruleset contains one or more rules. A rule may include:

- rule key;
- category;
- document type;
- required flag;
- maximum age days;
- applies-when JSON;
- metadata.

The Rulesets UI now supports CRUD-style operations:

- list rulesets;
- create rulesets;
- edit rulesets;
- delete rulesets;
- list rules within a selected ruleset;
- add rules;
- edit rules;
- delete rules;
- inspect rule JSON.

The screen uses the reusable PlutoGrid-backed data grid.

Items still to refine:

- validation of rule keys and document-type vocabulary;
- controlled rule templates;
- version promotion workflow;
- active/draft/superseded lifecycle controls;
- rule import/export;
- approval workflow for ruleset changes.

---

## 16. Extraction

The Extraction screen shows OCR/search-text coverage and extraction status.

The initial page load has been optimised to use a lightweight summary endpoint:

```text
GET /api/v1/extraction/summary
```

This endpoint reads the FITS index projection rather than opening every FITS container on first load.

It returns archive-wide entity extraction coverage, including:

- indexed entry count;
- text row count;
- character count;
- extraction status;
- issue count;
- summary text.

Detailed entity extraction is still available via:

```text
GET /api/v1/extraction/entities/{entity_id}/report
```

The entity-level detail includes extraction/OCR/search-text rows with:

- filename;
- method;
- confidence;
- character count;
- extracted text preview;
- object ID.

Items still to refine:

- real OCR provider integration;
- confidence scoring by provider;
- extraction-event lifecycle display;
- side-by-side evidence preview and extracted text;
- batch retry of failed extraction;
- queue-based OCR processing for large volumes.

---

## 17. Legal Hold and Retention

The Legal Hold & Retention screen shows retention metadata and legal hold status.

It supports:

- archive-wide retention summary;
- entity-level drill-down;
- filename;
- category;
- document type;
- retention class;
- retention-until date;
- legal hold status;
- deletion eligibility;
- object ID.

The current retention model is metadata-driven and suitable for the proof-of-concept/product foundation.

Items still to refine:

- full legal hold workflow;
- reason and authority for hold placement/removal;
- immutable hold audit trail;
- retention policy administration;
- disposal approval workflow;
- legal hold override handling;
- defensible deletion controls.

---

## 18. Integrity

The Integrity screen validates preserved FITS containers and payloads.

Integrity validation checks include:

- container hash;
- expected and actual size;
- FITS file openability;
- required HDUs;
- payload HDU presence;
- payload SHA-256;
- payload header SHA-256;
- payload size;
- failed payload count;
- missing HDU count;
- overall status.

The archive-wide integrity screen now reads the existing summary response correctly:

```text
GET /api/v1/integrity/summary
```

The response contains:

```text
checked_count
results[]
```

Each result is mapped into an entity-level grid row.

Entity-level detail remains available through:

```text
GET /api/v1/integrity/entities/{entity_id}
```

Items still to refine:

- clearer distinction between no current FITS container and invalid FITS container;
- scheduled periodic integrity checks;
- integrity remediation workflow;
- alerting for failed validation;
- immutable validation reports;
- exportable integrity attestations.

---

## 19. Comparison

The Comparison capability compares what is preserved in FITS with what is projected into the operational database/index.

It is primarily useful for technical assurance and development testing.

Current purpose:

- confirm FITS-to-index consistency;
- identify missing index rows;
- compare query results from direct FITS versus database/index search;
- support debugging of ingestion and indexing behaviour.

Potential production decision:

- keep it as an administrator/technical assurance screen; or
- remove it from the production user menu and retain only API/test coverage.

---

## 20. Export

TrustVault exports preserved FITS evidence archives.

Current capability includes:

- search/select entity;
- list current and historical FITS versions;
- download FITS container;
- export routes requiring authentication.

The FITS file is the primary archive/export artefact.

Future export enhancements may include:

- regulator response packs;
- human-readable PDF summary reports;
- evidence bundle manifests;
- signed export attestations;
- export approval workflow;
- export audit enrichment;
- temporary secure download links;
- role-based export restrictions.

---

## 21. Jobs and ingestion history

The Jobs screen shows database-backed background jobs and ingestion history.

It supports:

- job list;
- status;
- job type;
- correlation ID;
- created/started/completed times;
- payload and result inspection;
- error messages;
- CSV export;
- test job submission.

Potential job types include:

- rebuild index;
- rebuild entity container;
- ingest text evidence;
- scan drop folder;
- queued ingestion operations.

Items still to refine:

- clearer separation between system jobs and ingestion history;
- cancellation/retry controls;
- progress reporting;
- worker heartbeat display;
- SLA/age indicators;
- failed job remediation actions.

---

## 22. Audit log

The Audit screen provides a searchable operational audit log.

The audit grid includes:

- time;
- task/event;
- status;
- user;
- entity;
- object;
- result count;
- source;
- correlation ID;
- raw query;
- metadata;
- full event JSON inspection.

The audit screen now uses the reusable PlutoGrid-backed data grid.

Items still to refine:

- richer user display-name mapping across all events;
- consistent entity/object capture across all backend routes;
- export by date range;
- date and time filters;
- audit event retention controls;
- tamper-evident audit log strategy;
- correlation across jobs, queries, exports and evidence opens.

---

## 23. Settings

The Settings screen provides local runtime configuration.

Configuration areas include:

- local source folders;
- containers folder;
- index path;
- exports folder;
- automatic source-folder ingestion;
- AI provider settings;
- OCR provider settings;
- storage provider settings;
- queue provider settings;
- app/environment settings.

The Settings screen should remain fully scrollable because configuration panels can exceed the viewport height.

Items still to refine:

- validation of configured paths;
- secret handling and masking;
- provider-specific configuration panels;
- environment variable import/export;
- production-safe settings locks;
- restart-required indicators.

---

## 24. Licence

TrustVault includes an offline licence status foundation.

The Licence screen should support:

- current licence state;
- customer/licence ID;
- valid-until date;
- enabled modules;
- upload and apply new licence file.

Current status:

- licence status endpoint exists;
- licence upload route exists;
- UI foundations exist;
- production-grade licence validation/signature verification should be completed before commercial deployment.

---

## 25. Health

The Health screen and health API show component status.

Health areas include:

- API;
- database;
- storage;
- queue;
- worker;
- AI provider;
- OCR provider;
- environment;
- configured providers.

The Health screen should present these as user-readable cards, not raw JSON.

Items still to refine:

- clearer explanations of each health card;
- last worker heartbeat time;
- storage read/write test;
- AI connectivity test;
- OCR provider test;
- degraded state explanations;
- supportable operational messages for non-technical users.

---

## 26. Dashboard

The Dashboard is the app landing page.

The intended dashboard should show:

- licence status and expiry;
- database status;
- archive counts;
- entities count;
- container count;
- indexed evidence object count;
- recent ingestion/job status;
- key assurance status;
- missing evidence summary;
- recent audit events.

Items already identified for refinement:

- remove production build status card if not useful to production users;
- show meaningful database status rather than `Unknown`;
- make licence state and expiry prominent;
- avoid technical-only cards where they do not help the operator.

---

## 27. Data grids

The app now uses a reusable `TrustVaultDataGrid` component backed by `pluto_grid`.

The grid is intended to provide a Streamlit-like operational data-frame experience in Flutter Web.

Screens using the shared grid include:

- Search results;
- Entities;
- Audit log;
- Completeness;
- Extraction;
- Legal Hold & Retention;
- Integrity;
- Rulesets;
- Jobs / ingestion history;
- evidence modals;
- FITS archive version modals;
- validation result modals.

Grid features include:

- column sorting;
- column filtering;
- global search;
- show/hide columns;
- CSV export;
- horizontal and vertical scrolling;
- dense operational layout;
- row click actions;
- custom cell renderers such as status pills.

Items still to refine:

- server-side pagination for very large datasets;
- server-side filtering for large archives;
- saved grid views;
- user-specific column preferences;
- richer export formats;
- date/range filters;
- bulk actions.

---

## 28. API surface summary

Representative current API areas:

```text
/api/v1/auth/*
/api/v1/settings/*
/api/v1/health
/api/v1/dashboard/summary
/api/v1/api/status
/api/v1/customers
/api/v1/entities
/api/v1/evidence/*
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
curl -s "http://localhost:8000/api/v1/completeness/summary" | python3 -m json.tool
curl -s "http://localhost:8000/api/v1/extraction/summary" | python3 -m json.tool
curl -s "http://localhost:8000/api/v1/integrity/summary" | python3 -m json.tool
```

For authenticated routes, include:

```bash
-H "Authorization: Bearer <token>"
```

---

## 29. Database migrations

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

## 30. Regression testing search capability

A regression test script exists or is intended to exercise the expected TrustVault natural-language query scenarios.

The target scenarios include:

1. Archive/status checks;
2. Entity discovery;
3. Entity summary;
4. Direct FITS search for selected entity;
5. Cross-archive search;
6. Query interpretation tests;
7. Execute natural-language queries;
8. Completeness checks;
9. Payload metadata checks.

The regression output should be written to:

```text
local-data/search-regression/latest-search-regression.json
```

This file can be shared for diagnosis when search, query interpretation or execution behaviour regresses.

---

## 31. Production cloud targets

### AWS target

Potential AWS deployment architecture:

- ECS Fargate for API and worker;
- S3 for source imports, FITS containers, versions and derived reports;
- RDS PostgreSQL;
- SQS;
- ECR;
- Secrets Manager;
- KMS;
- CloudWatch;
- VPC/private subnets/VPC endpoints;
- ALB or private load balancer;
- Cognito or client OIDC/SAML;
- WAF and logging controls.

### Azure target

Potential Azure deployment architecture:

- Azure Container Apps;
- Blob Storage;
- Azure Database for PostgreSQL;
- Service Bus or Storage Queues;
- Azure Container Registry;
- Key Vault;
- Managed Identity;
- Azure Monitor / Log Analytics;
- Private Endpoints;
- Entra ID;
- Application Gateway / Front Door depending on deployment model.

---

## 32. Security and compliance considerations

TrustVault is intended for regulated evidence, so production deployment should address:

- encryption at rest;
- encryption in transit;
- strong authentication;
- role-based access control;
- least privilege service identities;
- audit immutability strategy;
- export approval workflow;
- secure evidence preview controls;
- malware scanning for ingested evidence;
- retention and disposal governance;
- legal hold governance;
- model/provider governance for AI/OCR;
- environment segregation;
- backup and restore;
- disaster recovery;
- penetration testing;
- operational monitoring;
- incident response processes.

---

## 33. Known incomplete developments and roadmap

The current application is a strong functional/product foundation, but the following items remain incomplete or require hardening before production use.

### Performance and scalability

- Add server-side pagination for all large grids.
- Add server-side filtering and sorting for entity, audit, search and assurance grids.
- Avoid any remaining serial per-entity API loops on page load.
- Optimise FITS index rebuilds for large archives.
- Add batch APIs for all assurance summary use cases.
- Add queue concurrency controls and job prioritisation.

### Search and AI

- Continue hardening natural-language query interpretation.
- Add more deterministic guardrails for missing-evidence queries.
- Expand regression tests for all listed query scenarios.
- Add confidence and warning display for AI interpretation.
- Add AI summary quality checks and safer fallback summaries.
- Support more precise selected-entity versus archive-wide search UX.

### Evidence preview

- Add embedded PDF preview.
- Improve email rendering.
- Add safe preview controls by file type and role.
- Add evidence redaction option.
- Improve binary/unknown file handling.

### Completeness and rulesets

- Add ruleset lifecycle management: draft, active, superseded, archived.
- Add approval workflow for ruleset changes.
- Add rule templates for common CDD regimes.
- Add import/export for rulesets.
- Add stronger validation for rule JSON.
- Add historical completeness trend reporting.

### Extraction and OCR

- Integrate real OCR providers.
- Add extraction retry workflow.
- Add extraction queue jobs.
- Store and display detailed extraction events.
- Add confidence thresholds and review queues.

### Retention and legal hold

- Implement full legal hold placement/removal workflow.
- Add hold reason, authority, case reference and expiry/review dates.
- Add disposal approval workflow.
- Add retention policy administration.
- Add deletion simulation before actual deletion.

### Integrity

- Schedule periodic integrity validation.
- Add alerting for failed integrity checks.
- Add validation reports and attestations.
- Add remediation workflow for missing/invalid payloads.
- Distinguish clearly between missing FITS, invalid FITS and unchecked FITS.

### Ingestion

- Harden duplicate detection.
- Add large batch handling.
- Add richer zip validation error reporting.
- Add source-folder monitoring modes.
- Add quarantine for suspicious or malformed files.
- Add malware scanning integration.

### Audit

- Ensure every route captures user, entity and object consistently.
- Add audit date range filters.
- Add export by time period, task or user.
- Add tamper-evident audit strategy.
- Add correlation between ingestion, jobs, query, preview and export actions.

### User administration

- Add password reset flow.
- Add MFA or external IdP integration.
- Add role management UI if roles become configurable.
- Add session management.
- Add account lockout and password policy enforcement.

### Licence

- Complete signed licence validation.
- Add module enforcement.
- Add expiry warnings.
- Add licence upload/apply confirmation workflow.
- Add offline validation cache.

### Production operations

- Add structured logging.
- Add metrics.
- Add health checks suitable for orchestrators.
- Add backup and restore documentation.
- Add deployment IaC.
- Add environment-specific configuration examples.
- Add runbooks.

---

## 34. Important implementation note

Do not treat derived report packs, AI summaries or UI grids as the archive model.

TrustVault's archive/export artefact is the FITS file. Derived reports can be produced for readability, approval packs or regulator presentation, but the preserved FITS container and payload hashes remain the source of truth.
