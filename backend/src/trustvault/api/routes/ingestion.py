import base64
from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from trustvault.audit.events import BULK_INGESTION_RUN
from trustvault.audit.logger import AuditLogger
from trustvault.api.dependencies import get_audit_logger, get_database
from trustvault.auth.dependencies import require_permission
from trustvault.auth.models import CurrentUser
from trustvault.core.container_builder import EntityContainerBuilder
from trustvault.core.fits_reader import FitsContainerReader
from trustvault.core.ingestion import LocalEvidenceIngestionService
from trustvault.core.source_folder_ingestion import SourceFolderIngestionService

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])


class TextEvidenceIngestionRequest(BaseModel):
    entity_external_id: str = Field(min_length=1)
    entity_display_name: str = Field(min_length=1)
    object_type: str = Field(default="document")
    source_system: str = Field(default="manual_upload")
    filename: str = Field(default="evidence.txt")
    text: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    rebuild_container: bool = True
    rebuild_index: bool = True


class Base64EvidenceIngestionRequest(BaseModel):
    entity_external_id: str = Field(min_length=1)
    entity_display_name: str = Field(min_length=1)
    object_type: str = Field(default="document")
    source_system: str = Field(default="manual_upload")
    filename: str = Field(min_length=1)
    content_base64: str = Field(min_length=1)
    content_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    rebuild_container: bool = True
    rebuild_index: bool = True


class SourceFolderIngestionRequest(BaseModel):
    zip_base64: str = Field(min_length=1)
    source_system_default: str = "source_folder"
    rebuild_container: bool = True
    rebuild_index: bool = True


class IngestionResponse(BaseModel):
    entity_id: str
    entity_external_id: str
    evidence_object_id: str
    storage_uri: str
    sha256: str
    container: dict[str, Any] | None = None
    index: dict[str, Any] | None = None


class SourceFolderIngestionResponse(BaseModel):
    entity_id: str
    entity_external_id: str
    entity_display_name: str
    evidence_object_count: int
    source_system_count: int
    skipped_count: int
    duplicate_count: int = 0
    evidence_object_ids: list[str]
    assurance_gaps: list[dict[str, Any]] = Field(default_factory=list)
    container: dict[str, Any] | None = None
    index: dict[str, Any] | None = None
    message: str | None = None


def _post_ingestion_rebuilds(
    db: Session,
    entity_external_id: str,
    rebuild_container: bool,
    rebuild_index: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    container = EntityContainerBuilder(db).rebuild(entity_external_id) if rebuild_container else None
    index = FitsContainerReader(db).rebuild_index_from_current_fits(entity_external_id) if rebuild_index else None
    return container, index


def _post_source_folder_rebuilds(
    db: Session,
    entity_external_id: str,
    inserted_count: int,
    rebuild_container: bool,
    rebuild_index: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    if inserted_count <= 0:
        return None, None, "No new evidence was ingested; source folder upload was duplicate-only. Current FITS archive was left unchanged."
    container, index = _post_ingestion_rebuilds(db, entity_external_id, rebuild_container, rebuild_index)
    return container, index, None


@router.post("/text", response_model=IngestionResponse)
def ingest_text_evidence(
    request: TextEvidenceIngestionRequest,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
    current_user: CurrentUser = Depends(require_permission("ingestion:submit")),
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
    container, index = _post_ingestion_rebuilds(
        db,
        result.entity_external_id,
        request.rebuild_container,
        request.rebuild_index,
    )
    audit_logger.log(
        BULK_INGESTION_RUN,
        user_id=current_user.subject,
        entity_ids=[result.entity_id],
        object_ids=[result.evidence_object_id],
        metadata={
            "mode": "api_text",
            "entity_external_id": result.entity_external_id,
            "source_system": request.source_system,
            "object_type": request.object_type,
            "container_rebuilt": container is not None,
            "index_rebuilt": index is not None,
        },
    )
    return IngestionResponse(**result.__dict__, container=container, index=index)


@router.post("/base64", response_model=IngestionResponse)
def ingest_base64_evidence(
    request: Base64EvidenceIngestionRequest,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
    current_user: CurrentUser = Depends(require_permission("ingestion:submit")),
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
    container, index = _post_ingestion_rebuilds(
        db,
        result.entity_external_id,
        request.rebuild_container,
        request.rebuild_index,
    )
    audit_logger.log(
        BULK_INGESTION_RUN,
        user_id=current_user.subject,
        entity_ids=[result.entity_id],
        object_ids=[result.evidence_object_id],
        metadata={
            "mode": "api_base64",
            "entity_external_id": result.entity_external_id,
            "source_system": request.source_system,
            "object_type": request.object_type,
            "container_rebuilt": container is not None,
            "index_rebuilt": index is not None,
        },
    )
    return IngestionResponse(**result.__dict__, container=container, index=index)


@router.post("/source-folder", response_model=SourceFolderIngestionResponse)
def ingest_source_folder_base64(
    request: SourceFolderIngestionRequest,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
    current_user: CurrentUser = Depends(require_permission("ingestion:submit")),
) -> SourceFolderIngestionResponse:
    zip_bytes = base64.b64decode(request.zip_base64)
    result = SourceFolderIngestionService(db).ingest_zip_bytes(
        zip_bytes,
        source_system_default=request.source_system_default,
    )
    container, index, message = _post_source_folder_rebuilds(
        db,
        result.entity_external_id,
        result.evidence_object_count,
        request.rebuild_container,
        request.rebuild_index,
    )
    audit_logger.log(
        BULK_INGESTION_RUN,
        user_id=current_user.subject,
        entity_ids=[result.entity_id],
        object_ids=result.evidence_object_ids,
        metadata={
            "mode": "source_folder_zip_base64",
            "entity_external_id": result.entity_external_id,
            "evidence_object_count": result.evidence_object_count,
            "duplicate_count": result.duplicate_count,
            "source_system_count": result.source_system_count,
            "assurance_gaps": result.assurance_gaps,
            "container_rebuilt": container is not None,
            "index_rebuilt": index is not None,
        },
    )
    return SourceFolderIngestionResponse(**result.__dict__, container=container, index=index, message=message)


@router.post("/source-folder/upload", response_model=SourceFolderIngestionResponse)
async def ingest_source_folder_upload(
    file: UploadFile = File(...),
    rebuild_container: bool = True,
    rebuild_index: bool = True,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
    current_user: CurrentUser = Depends(require_permission("ingestion:submit")),
) -> SourceFolderIngestionResponse:
    zip_bytes = await file.read()
    result = SourceFolderIngestionService(db).ingest_zip_bytes(zip_bytes)
    container, index, message = _post_source_folder_rebuilds(
        db,
        result.entity_external_id,
        result.evidence_object_count,
        rebuild_container,
        rebuild_index,
    )
    audit_logger.log(
        BULK_INGESTION_RUN,
        user_id=current_user.subject,
        entity_ids=[result.entity_id],
        object_ids=result.evidence_object_ids,
        metadata={
            "mode": "source_folder_upload",
            "filename": file.filename,
            "entity_external_id": result.entity_external_id,
            "evidence_object_count": result.evidence_object_count,
            "duplicate_count": result.duplicate_count,
            "source_system_count": result.source_system_count,
            "assurance_gaps": result.assurance_gaps,
            "container_rebuilt": container is not None,
            "index_rebuilt": index is not None,
        },
    )
    return SourceFolderIngestionResponse(**result.__dict__, container=container, index=index, message=message)
