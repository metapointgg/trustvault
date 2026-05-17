from typing import Any

from sqlalchemy.orm import Session

from trustvault.audit.events import INDEX_REBUILT
from trustvault.audit.logger import AuditLogger
from trustvault.core.fits_reader import FitsContainerReader


def handle_rebuild_fits_index(db: Session, payload: dict[str, Any], correlation_id: str, job_id: str | None = None) -> dict[str, Any]:
    entity_reference = payload.get("entity_id") or payload.get("entity_external_id")
    result = FitsContainerReader(db).rebuild_index_from_current_fits(entity_reference)

    AuditLogger(db).log(
        INDEX_REBUILT,
        correlation_id=correlation_id,
        job_id=job_id,
        metadata={
            "source": "current_fits_containers",
            "entity_reference": entity_reference,
            "indexed_entity_count": result["indexed_entity_count"],
            "skipped_entity_count": result["skipped_entity_count"],
        },
    )
    return result
