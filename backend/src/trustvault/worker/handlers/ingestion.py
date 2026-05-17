from typing import Any

from sqlalchemy.orm import Session

from trustvault.audit.events import BULK_INGESTION_RUN
from trustvault.audit.logger import AuditLogger
from trustvault.core.ingestion import LocalEvidenceIngestionService


def handle_ingest_text_evidence(db: Session, payload: dict[str, Any], correlation_id: str) -> dict[str, Any]:
    required_fields = ["entity_external_id", "entity_display_name", "text"]
    missing = [field for field in required_fields if not payload.get(field)]
    if missing:
        raise ValueError(f"Missing required ingestion payload fields: {', '.join(missing)}")

    service = LocalEvidenceIngestionService(db)
    result = service.ingest_text_evidence(
        entity_external_id=payload["entity_external_id"],
        entity_display_name=payload["entity_display_name"],
        object_type=payload.get("object_type", "document"),
        source_system=payload.get("source_system", "queued_ingestion"),
        filename=payload.get("filename", "evidence.txt"),
        text=payload["text"],
        metadata=payload.get("metadata", {}),
    )

    AuditLogger(db).log(
        BULK_INGESTION_RUN,
        correlation_id=correlation_id,
        entity_ids=[result.entity_id],
        object_ids=[result.evidence_object_id],
        metadata={
            "mode": "queued_text",
            "entity_external_id": result.entity_external_id,
            "source_system": payload.get("source_system", "queued_ingestion"),
        },
    )

    return result.__dict__
