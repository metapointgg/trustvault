# TrustVault Implementation Roadmap

## Current repository state

This repository contains the first production-shaped TrustVault scaffold:

- FastAPI backend;
- PostgreSQL database bootstrap;
- worker process;
- jobs table and job API;
- audit events table and audit API;
- licence status API;
- local filesystem storage provider;
- Docker Compose for API, worker and PostgreSQL;
- Flutter Web application shell.

The next phase is to migrate working functionality from the Entity Evidence Container Demo proof of concept into the backend `trustvault.core` package.

## Architecture principle

FITS containers are the durable source of truth. PostgreSQL is used for operational state, search/index acceleration, rulesets, audit events, job status and licence state.

## Phase 1: Production skeleton

Status: started.

Scope:

- backend package structure;
- FastAPI app;
- worker app;
- PostgreSQL models;
- Docker Compose;
- Flutter shell;
- first operational endpoints.

## Phase 2: Migrate core POC logic

Move the existing proof-of-concept code into:

```text
backend/src/trustvault/core/
```

Suggested modules:

```text
fits_container.py
manifest.py
hashing.py
search.py
completeness.py
rulesets.py
export_pack.py
ingestion.py
```

Keep existing working behaviour, but remove UI dependencies from the core logic.

## Phase 3: Entity and evidence APIs

Add:

```text
GET    /api/v1/entities
GET    /api/v1/entities/{entity_id}
GET    /api/v1/entities/{entity_id}/evidence
GET    /api/v1/entities/{entity_id}/completeness
POST   /api/v1/search
POST   /api/v1/search/direct-fits
```

Add Flutter screens for:

- entity list;
- entity detail;
- evidence timeline;
- evidence preview;
- direct FITS search;
- cohort search.

## Phase 4: Job handlers

Replace the placeholder worker handler with specific handlers:

```text
bulk_ingestion
continuous_ingestion
rebuild_entity_container
rebuild_index
ocr_extraction
evidence_pack_export
integrity_validation
retention_report
```

Each handler must:

- update job state;
- record audit events;
- write outputs through the storage provider;
- avoid direct local file path assumptions.

## Phase 5: Storage providers

Add:

```text
S3Storage
AzureBlobStorage
```

All source files, FITS containers, versions and exports should go through the storage provider interface.

## Phase 6: Licensing

Current licence validation checks the JSON structure and dates. Next:

- add Ed25519 signature verification;
- add module enforcement;
- add licence-only/admin mode;
- add expired-after-grace read/search-only mode;
- audit licence validation and unlicensed feature attempts.

## Phase 7: Authentication and authorisation

Add:

- local development auth;
- OIDC bearer token validation;
- role and permission model;
- Cognito deployment option;
- Entra ID deployment option.

Roles:

```text
Admin
Compliance Manager
Compliance Analyst
Read-only Auditor
Ingestion Operator
Export Approver
```

## Phase 8: Cloud deployment

AWS:

- ECS Fargate;
- S3;
- RDS PostgreSQL;
- SQS;
- ECR;
- Secrets Manager;
- KMS;
- CloudWatch.

Azure:

- Azure Container Apps;
- Blob Storage;
- Azure Database for PostgreSQL;
- Service Bus or Storage Queues;
- Azure Container Registry;
- Key Vault;
- Managed Identity;
- Azure Monitor.

## Immediate next work

1. Clone this repository locally.
2. Copy `.env.example` to `.env`.
3. Run `docker compose up --build`.
4. Run the Flutter app.
5. Confirm the dashboard connects to the API.
6. Submit a test job.
7. Confirm the worker marks the job as succeeded.
8. Confirm audit events are visible.
9. Start migrating POC FITS functionality into `trustvault.core`.
