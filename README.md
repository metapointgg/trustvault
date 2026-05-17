# TrustVault

TrustVault is an evidence preservation and assurance platform for regulated financial-services clients.

It converts fragmented customer evidence from legacy systems, document stores, email archives and operational platforms into self-contained, verifiable FITS evidence archives with searchable metadata, completeness controls, audit trails and regulator-ready export packs.

## Architecture

TrustVault is being built as a production-ready, single-tenant deployment pack with:

- a Python FastAPI backend;
- a Python worker process for long-running jobs;
- PostgreSQL for operational state, jobs, audit events, rulesets and index/cache data;
- object storage abstraction for filesystem, S3 and Azure Blob;
- queue abstraction for local development, AWS SQS and Azure queues;
- a Flutter Web application as the primary UI;
- offline signed JSON licensing;
- evidence-bound optional AI/OCR provider abstractions.

## Local development

```bash
docker compose up --build
```

Backend API:

```text
http://localhost:8000
```

Health endpoint:

```text
http://localhost:8000/health
```

Flutter app:

```bash
cd frontend/trustvault_app
flutter pub get
flutter run -d chrome --dart-define=TRUSTVAULT_API_BASE_URL=http://localhost:8000
```

## Initial scope

This repository contains the production skeleton for TrustVault. Existing proof-of-concept functionality from Entity Evidence Container Demo should be migrated into the backend `trustvault.core` package in controlled phases.

See `docs/implementation-roadmap.md` for the build plan.
