from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from trustvault.audit.events import EVIDENCE_PACK_EXPORTED
from trustvault.audit.logger import AuditLogger
from trustvault.api.dependencies import get_audit_logger, get_database
from trustvault.core.export_pack import RegulatorEvidencePackExporter

router = APIRouter(prefix="/api/v1/exports", tags=["exports"])


class ExportPackResponse(BaseModel):
    id: str
    entity_id: str
    entity_external_id: str | None
    container_version_id: str
    container_version_number: int | None
    export_type: str
    status: str
    storage_uri: str
    sha256: str
    size_bytes: int
    evidence_object_count: int
    manifest_json: dict[str, Any]
    created_by_job_id: str | None
    created_by_user_id: str | None
    created_at: datetime


class CreateExportPackRequest(BaseModel):
    entity_id: str | None = None
    entity_external_id: str | None = None
    created_by_user_id: str | None = Field(default="local-user")


@router.post("/regulator-pack", response_model=ExportPackResponse)
def create_regulator_pack(
    request: CreateExportPackRequest,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> ExportPackResponse:
    entity_reference = request.entity_id or request.entity_external_id
    if not entity_reference:
        raise HTTPException(status_code=400, detail="Provide entity_id or entity_external_id")

    try:
        result = RegulatorEvidencePackExporter(db).export_entity_pack(
            entity_reference,
            created_by_user_id=request.created_by_user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    audit_logger.log(
        EVIDENCE_PACK_EXPORTED,
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
    return ExportPackResponse(**result)


@router.get("/entities/{entity_id}/packs", response_model=list[ExportPackResponse])
def list_entity_packs(
    entity_id: str,
    db: Session = Depends(get_database),
) -> list[ExportPackResponse]:
    try:
        packs = RegulatorEvidencePackExporter(db).list_entity_packs(entity_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [ExportPackResponse(**pack) for pack in packs]
