from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.audit.events import CONTAINER_REBUILT
from trustvault.audit.logger import AuditLogger
from trustvault.api.dependencies import get_audit_logger, get_database
from trustvault.core.container_builder import EntityContainerBuilder
from trustvault.db.models import Entity, EntityContainerVersion

router = APIRouter(prefix="/api/v1/containers", tags=["containers"])


class ContainerVersionResponse(BaseModel):
    id: str
    entity_id: str
    version_number: int
    status: str
    storage_uri: str
    sha256: str
    size_bytes: int
    evidence_object_count: int
    manifest_json: dict[str, Any]
    hash_report_json: dict[str, Any]
    created_by_job_id: str | None
    created_at: datetime


class RebuildContainerRequest(BaseModel):
    entity_id: str | None = None
    entity_external_id: str | None = None


class RebuildContainerResponse(BaseModel):
    container_version_id: str
    entity_id: str
    entity_external_id: str
    version_number: int
    status: str
    storage_uri: str
    sha256: str
    size_bytes: int
    evidence_object_count: int


def serialise_version(version: EntityContainerVersion) -> ContainerVersionResponse:
    return ContainerVersionResponse(
        id=str(version.id),
        entity_id=str(version.entity_id),
        version_number=version.version_number,
        status=version.status,
        storage_uri=version.storage_uri,
        sha256=version.sha256,
        size_bytes=version.size_bytes,
        evidence_object_count=version.evidence_object_count,
        manifest_json=version.manifest_json,
        hash_report_json=version.hash_report_json,
        created_by_job_id=str(version.created_by_job_id) if version.created_by_job_id else None,
        created_at=version.created_at,
    )


@router.get("/entities/{entity_id}/versions", response_model=list[ContainerVersionResponse])
def list_entity_container_versions(
    entity_id: str,
    db: Session = Depends(get_database),
) -> list[ContainerVersionResponse]:
    entity = db.scalars(select(Entity).where(Entity.external_id == entity_id)).first()
    resolved_entity_id = entity.id if entity is not None else entity_id

    versions = db.scalars(
        select(EntityContainerVersion)
        .where(EntityContainerVersion.entity_id == resolved_entity_id)
        .order_by(EntityContainerVersion.version_number.desc())
    ).all()
    return [serialise_version(version) for version in versions]


@router.post("/rebuild", response_model=RebuildContainerResponse)
def rebuild_container(
    request: RebuildContainerRequest,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> RebuildContainerResponse:
    entity_reference = request.entity_id or request.entity_external_id
    if not entity_reference:
        raise HTTPException(status_code=400, detail="Provide entity_id or entity_external_id")

    try:
        result = EntityContainerBuilder(db).rebuild(entity_reference)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    audit_logger.log(
        CONTAINER_REBUILT,
        entity_ids=[result["entity_id"]],
        metadata={
            "mode": "api_sync",
            "container_version_id": result["container_version_id"],
            "entity_external_id": result["entity_external_id"],
            "version_number": result["version_number"],
            "storage_uri": result["storage_uri"],
        },
    )
    return RebuildContainerResponse(**result)
