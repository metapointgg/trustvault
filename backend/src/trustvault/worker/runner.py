import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select

from trustvault.audit.events import JOB_COMPLETED, JOB_FAILED
from trustvault.audit.logger import AuditLogger
from trustvault.db.models import Job
from trustvault.db.session import SessionLocal

logger = logging.getLogger(__name__)


class WorkerRunner:
    def __init__(self, poll_seconds: int = 5):
        self.poll_seconds = poll_seconds

    def run_forever(self) -> None:
        logger.info("TrustVault worker started")
        while True:
            processed = self.process_next_job()
            if not processed:
                time.sleep(self.poll_seconds)

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
                # Placeholder until POC operations are migrated into handlers.
                job.status = "succeeded"
                job.completed_at = datetime.now(timezone.utc)
                job.result = {
                    "message": "Job processed by TrustVault worker skeleton",
                    "job_type": job.job_type,
                }
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
