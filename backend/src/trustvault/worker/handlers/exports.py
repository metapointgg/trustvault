from typing import Any

from sqlalchemy.orm import Session

from trustvault.audit.events import EVIDENCE_PACK_EXPORTED
from trustvault.audit.logger import AuditLogger
from trustvault.core.export_pack import RegulatorEvidencePackExporter


def handle_export_regulator_pack(db: Session, payload: dict[str, Any], correlation_id: str, job_id: str | None = None) -> dict[str, Any]:
    entity_reference = payload.get("entity_id") or payload.get("entity_external_id")
    if not entity_reference:
        raise ValueError("Missing required payload field: entity_id or entity_external_id")

    result = RegulatorEvidencePackExporter(db).export_entity_pack(
        entity_reference,
        created_by_job_id=job_id,
        created_by_user_id=payload.get("created_by_user_id"),
    )

    AuditLogger(db).log(
        EVIDENCE_PACK_EXPORTED,
        correlation_id=correlation_id,
        job_id=job_id,
        entity_ids=[result["entity_id"]],
        export_path=result["storage_uri"],
        metadata={
            "export_pack_id": result["id"],
            "entity_external_id": result["entity_external_id"],
            "container_version_id": result["container_version_id"],
            "sha256": result["sha256"],
            "size_bytes": result["size_bytes"],
        },
    )
    return result
