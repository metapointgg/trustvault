from typing import Any

from sqlalchemy.orm import Session

from trustvault.audit.events import CONTAINER_REBUILT
from trustvault.audit.logger import AuditLogger
from trustvault.core.container_builder import EntityContainerBuilder


def handle_rebuild_entity_container(db: Session, payload: dict[str, Any], correlation_id: str, job_id: str | None = None) -> dict[str, Any]:
    entity_id = payload.get("entity_id") or payload.get("entity_external_id")
    if not entity_id:
        raise ValueError("Missing required payload field: entity_id or entity_external_id")

    result = EntityContainerBuilder(db).rebuild(entity_id, created_by_job_id=job_id)

    AuditLogger(db).log(
        CONTAINER_REBUILT,
        correlation_id=correlation_id,
        entity_ids=[result["entity_id"]],
        job_id=job_id,
        metadata={
            "container_version_id": result["container_version_id"],
            "entity_external_id": result["entity_external_id"],
            "version_number": result["version_number"],
            "storage_uri": result["storage_uri"],
            "evidence_object_count": result["evidence_object_count"],
        },
    )
    return result
