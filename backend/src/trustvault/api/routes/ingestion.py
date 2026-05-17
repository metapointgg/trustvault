from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from trustvault.audit.events import BULK_INGESTION_RUN
from trustvault.audit.logger import AuditLogger
from trustvault.api.dependencies import get_audit_logger, get_database
from trustvault.core.ingestion import LocalEvidenceIngestionService

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])


class TextEvidenceIngestionRequest(BaseModel):
    entity_external_id: str = Field(min_length=1)
    entity_display_name: str = Field(min_length=1)
    object_type: str = Field(default="document")
    source_system: str = Field(default="manual_upload")
    filename: str = Field(default="evidence.txt")
    text: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Base64EvidenceIngestionRequest(BaseModel):
    entity_external_id: str = Field(min_length=1)
    entity_display_name: str = Field(min_length=1)
    object_type: str = Field(default="document")
    source_system: str = Field(default="manual_upload")
    filename: str = Field(min_length=1)
    content_base64: str = Field(min_length=1)
    content_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestionResponse(BaseModel):
    entity_id: str
    entity_external_id: str
    evidence_object_id: str
    storage_uri: str
    sha256: str


@router.post("/text", response_model=IngestionResponse)
def ingest_text_evidence(
    request: TextEvidenceIngestionRequest,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> IngestionResponse:
    service = LocalEvidenceIngestionService(db)
    result = service.ingest_text_evidence(
        entity_external_id=request.entity_external_id,
        entity_display_name=request.entity_display_name,
        object_type=request.object_type,
        source_system=request.source_system,
        filename=request.filename,
        text=request.text,
        metadata=request.metadata,
    )
    audit_logger.log(
        BULK_INGESTION_RUN,
        entity_ids=[result.entity_id],
        object_ids=[result.evidence_object_id],
        metadata={
            "mode": "api_text",
            "entity_external_id": result.entity_external_id,
            "source_system": request.source_system,
            "object_type": request.object_type,
        },
    )
    return IngestionResponse(**result.__dict__)


@router.post("/base64", response_model=IngestionResponse)
def ingest_base64_evidence(
    request: Base64EvidenceIngestionRequest,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> IngestionResponse:
    service = LocalEvidenceIngestionService(db)
    result = service.ingest_base64_evidence(
        entity_external_id=request.entity_external_id,
        entity_display_name=request.entity_display_name,
        object_type=request.object_type,
        source_system=request.source_system,
        filename=request.filename,
        content_base64=request.content_base64,
        content_type=request.content_type,
        metadata=request.metadata,
    )
    audit_logger.log(
        BULK_INGESTION_RUN,
        entity_ids=[result.entity_id],
        object_ids=[result.evidence_object_id],
        metadata={
            "mode": "api_base64",
            "entity_external_id": result.entity_external_id,
            "source_system": request.source_system,
            "object_type": request.object_type,
        },
    )
    return IngestionResponse(**result.__dict__)
