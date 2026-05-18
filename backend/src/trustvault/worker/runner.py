import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select

from trustvault.audit.events import JOB_COMPLETED, JOB_FAILED
from trustvault.audit.logger import AuditLogger
from trustvault.core.app_settings import AppSettingsService
from trustvault.core.auto_ingestion import DropFolderIngestionService
from trustvault.db.models import Job
from trustvault.db.session import SessionLocal
from trustvault.worker.handlers.auto_ingestion import handle_scan_drop_folder
from trustvault.worker.handlers.containers import handle_rebuild_entity_container
from trustvault.worker.handlers.fits_index import handle_rebuild_fits_index
from trustvault.worker.handlers.ingestion import handle_ingest_text_evidence

logger = logging.getLogger(__name__)

JobHandler = Callable[[Any, dict[str, Any], str, str | None], dict[str, Any]]


def _ingest_text_adapter(db: Any, payload: dict[str, Any], correlation_id: str, job_id: str | None) -> dict[str, Any]:
    return handle_ingest_text_evidence(db, payload, correlation_id)


class WorkerRunner:
    def __init__(self, poll_seconds: int = 5):
        self.poll_seconds = poll_seconds
        self._last_auto_scan_at = 0.0
        self.handlers: dict[str, JobHandler] = {
            "ingest_text_evidence": _ingest_text_adapter,
            "rebuild_entity_container": handle_rebuild_entity_container,
            "rebuild_fits_index": handle_rebuild_fits_index,
            "rebuild_index": handle_rebuild_fits_index,
            "scan_drop_folder": handle_scan_drop_folder,
            "automatic_source_folder_ingestion": handle_scan_drop_folder,
        }

    def run_forever(self) -> None:
        logger.info("TrustVault worker started")
        while True:
            processed = self.process_next_job()
            if not processed:
                self.scan_drop_folder_if_due()
                time.sleep(self.poll_seconds)

    def scan_drop_folder_if_due(self) -> None:
        now = time.time()
        with SessionLocal() as db:
            values = AppSettingsService(db).effective_values()
            enabled = bool(values.get("auto_ingestion_enabled", True))
            interval = int(values.get("auto_ingestion_poll_seconds", 10) or 10)
            if not enabled or now - self._last_auto_scan_at < interval:
                return
            self._last_auto_scan_at = now
            result = DropFolderIngestionService(db).scan_once()
            if result.get("processed_count") or result.get("failed_count"):
                logger.info("Automatic drop-folder ingestion scan result: %s", result)

    def process_next_job(self) -> bool:
        with SessionLocal() as db:
            job = db.scalars(
                select(Job)
                .where(Job.status == "queued")
                .order_by(Job.created_at.asc())
                .limit(1)
            ).first()

            if job is None:
                return False

            audit_logger = AuditLogger(db)
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(job)

            try:
                handler = self.handlers.get(job.job_type)
                if handler is None:
                    result = {
                        "message": "Job type has no registered production handler",
                        "job_type": job.job_type,
                        "handler": "unregistered",
                    }
                else:
                    result = handler(db, job.payload, job.correlation_id, str(job.id))

                job.status = "succeeded"
                job.completed_at = datetime.now(timezone.utc)
                job.result = result
                db.commit()
                audit_logger.log(
                    JOB_COMPLETED,
                    correlation_id=job.correlation_id,
                    job_id=job.id,
                    metadata={"job_type": job.job_type},
                )
                logger.info("Completed job %s", job.id)
                return True
            except Exception as exc:  # pragma: no cover - defensive worker boundary
                job.status = "failed"
                job.completed_at = datetime.now(timezone.utc)
                job.error_message = str(exc)
                db.commit()
                audit_logger.log(
                    JOB_FAILED,
                    status="error",
                    correlation_id=job.correlation_id,
                    job_id=job.id,
                    error_message=str(exc),
                    metadata={"job_type": job.job_type},
                )
                logger.exception("Failed job %s", job.id)
                return True
