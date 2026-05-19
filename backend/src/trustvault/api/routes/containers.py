from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.audit.events import CONTAINER_REBUILT, INTEGRITY_VALIDATION_RUN
from trustvault.audit.logger import AuditLogger
from trustvault.api.dependencies import get_audit_logger, get_database
from trustvault.auth.dependencies import require_permission
from trustvault.auth.models import CurrentUser
from trustvault.core.container_builder import EntityContainerBuilder
from trustvault.core.container_normalisation import ContainerVersionNormaliser
from trustvault.core.container_status import ContainerStatusService
from trustvault.core.integrity import ContainerIntegrityValidator
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
    container_format: str | None = None


class ContainerValidationResponse(BaseModel):
    container_version_id: str
    entity_id: str
    version_number: int
    status: str
    storage_uri: str
    expected_container_sha256: str
    actual_container_sha256: str
    container_hash_matches: bool
    size_bytes: int
    expected_size_bytes: int
    size_matches: bool
    is_fits_uri: bool
    fits_opened: bool
    missing_required_hdus: list[str]
    payload_results: list[dict[str, Any]]
    overall_status: str
    errors: list[str]
    hdu_names: list[str] | None = None


class ContainerNormalisationResponse(BaseModel):
    updated_count: int
    skipped_count: int
    updated: list[dict[str, Any]]
    skipped: list[dict[str, Any]]


class ContainerStatusResponse(BaseModel):
    entity_count: int
    entities_with_current_fits: int
    entities_missing_current_fits: int
    entities: list[dict[str, Any]]


class RebuildMissingFitsResponse(BaseModel):
    rebuilt_count: int
    skipped_count: int
    rebuilt: list[dict[str, Any]]
    skipped: list[dict[str, Any]]


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
    current_user: CurrentUser = Depends(require_permission("evidence:read")),
) -> list[ContainerVersionResponse]:
    entity = db.scalars(select(Entity).where(Entity.external_id == entity_id)).first()
    resolved_entity_id = entity.id if entity is not None else entity_id

    versions = db.scalars(
        select(EntityContainerVersion)
        .where(EntityContainerVersion.entity_id == resolved_entity_id)
        .order_by(EntityContainerVersion.version_number.desc())
    ).all()
    return [serialise_version(version) for version in versions]


@router.get("/admin/status", response_model=ContainerStatusResponse)
def container_status(
    db: Session = Depends(get_database),
    current_user: CurrentUser = Depends(require_permission("integrity:run")),
) -> ContainerStatusResponse:
    result = ContainerStatusService(db).entity_container_status()
    return ContainerStatusResponse(**result)


@router.post("/rebuild", response_model=RebuildContainerResponse)
def rebuild_container(
    request: RebuildContainerRequest,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
    current_user: CurrentUser = Depends(require_permission("containers:rebuild")),
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
        user_id=current_user.subject,
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


@router.post("/versions/{container_version_id}/validate", response_model=ContainerValidationResponse)
def validate_container_version(
    container_version_id: str,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
    current_user: CurrentUser = Depends(require_permission("integrity:run")),
) -> ContainerValidationResponse:
    try:
        result = ContainerIntegrityValidator(db).validate_container_version(container_version_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    audit_logger.log(
        INTEGRITY_VALIDATION_RUN,
        user_id=current_user.subject,
        status="success" if result["overall_status"] == "valid" else "error",
        entity_ids=[result["entity_id"]],
        metadata={
            "container_version_id": container_version_id,
            "storage_uri": result["storage_uri"],
            "overall_status": result["overall_status"],
            "container_hash_matches": result["container_hash_matches"],
            "payload_count": len(result["payload_results"]),
        },
    )
    return ContainerValidationResponse(**result)


@router.post("/admin/normalise-legacy-placeholders", response_model=ContainerNormalisationResponse)
def normalise_legacy_placeholders(
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
    current_user: CurrentUser = Depends(require_permission("containers:rebuild")),
) -> ContainerNormalisationResponse:
    result = ContainerVersionNormaliser(db).normalise_legacy_placeholders()
    audit_logger.log(
        INTEGRITY_VALIDATION_RUN,
        user_id=current_user.subject,
        metadata={
            "operation": "normalise_legacy_placeholder_containers",
            "updated_count": result["updated_count"],
            "skipped_count": result["skipped_count"],
        },
    )
    return ContainerNormalisationResponse(**result)


@router.post("/admin/rebuild-missing-current-fits", response_model=RebuildMissingFitsResponse)
def rebuild_missing_current_fits(
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
    current_user: CurrentUser = Depends(require_permission("containers:rebuild")),
) -> RebuildMissingFitsResponse:
    result = ContainerStatusService(db).rebuild_missing_current_fits()
    audit_logger.log(
        CONTAINER_REBUILT,
        user_id=current_user.subject,
        metadata={
            "operation": "rebuild_missing_current_fits",
            "rebuilt_count": result["rebuilt_count"],
            "skipped_count": result["skipped_count"],
            "rebuilt_entity_ids": [item["entity_id"] for item in result["rebuilt"]],
        },
    )
    return RebuildMissingFitsResponse(**result)
