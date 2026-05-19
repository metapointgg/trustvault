from typing import Any

from sqlalchemy.orm import Session

from trustvault.audit.events import BULK_INGESTION_RUN
from trustvault.audit.logger import AuditLogger
from trustvault.core.auto_ingestion import DropFolderIngestionService


def handle_scan_drop_folder(db: Session, payload: dict[str, Any], correlation_id: str, job_id: str | None = None) -> dict[str, Any]:
    result = DropFolderIngestionService(db).scan_once()
    AuditLogger(db).log(
        BULK_INGESTION_RUN,
        correlation_id=correlation_id,
        job_id=job_id,
        metadata={
            "mode": "automatic_drop_folder_scan",
            "processed_count": result.get("processed_count", 0),
            "failed_count": result.get("failed_count", 0),
            "enabled": result.get("enabled", False),
        },
    )
    return result
