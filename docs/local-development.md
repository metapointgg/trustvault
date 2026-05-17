# Local Development

## Prerequisites

- Docker Desktop
- Python 3.12, if running the backend outside Docker
- Flutter SDK with Chrome/web support enabled

## Start the backend stack

From the repository root:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Then run:

```bash
docker compose up --build
```

The API will be available at:

```text
http://localhost:8000
```

Check health:

```text
http://localhost:8000/health
```

## Run the Flutter app

In a second terminal:

```bash
cd frontend/trustvault_app
flutter pub get
flutter run -d chrome --dart-define=TRUSTVAULT_API_BASE_URL=http://localhost:8000
```

## Test the first operational path

1. Open the Flutter dashboard.
2. Confirm API status and database status are visible.
3. Open Jobs.
4. Click `Submit test job`.
5. Wait for the worker to process the queued job.
6. Open Audit.
7. Confirm `JOB_SUBMITTED` and `JOB_COMPLETED` events appear.

## Useful API calls

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/dashboard/summary
curl http://localhost:8000/api/v1/licence/status
curl http://localhost:8000/api/v1/jobs
curl http://localhost:8000/api/v1/audit/events
```

Create a job:

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{"job_type":"rebuild_index","payload":{"source":"curl"},"created_by_user_id":"local-user"}'
```
