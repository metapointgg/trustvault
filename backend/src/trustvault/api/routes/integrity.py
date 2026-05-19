from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from trustvault.audit.events import INTEGRITY_VALIDATION_RUN
from trustvault.audit.logger import AuditLogger
from trustvault.api.dependencies import get_audit_logger, get_database
from trustvault.auth.dependencies import require_permission
from trustvault.auth.models import CurrentUser
from trustvault.core.feature_services import TrustVaultFeatureService
from trustvault.core.integrity import ContainerIntegrityValidator

router = APIRouter(
    prefix="/api/v1/integrity",
    tags=["integrity"],
    dependencies=[Depends(require_permission("integrity:run"))],
)


@router.get("/summary")
def integrity_summary(
    full: bool = Query(default=False, description="When true, open and validate every current FITS container. The default metadata summary is fast for grids and dashboards."),
    db: Session = Depends(get_database),
) -> dict[str, Any]:
    return TrustVaultFeatureService(db).integrity_summary(full=full)


@router.get("/entities/{entity_id}")
def entity_integrity(entity_id: str, db: Session = Depends(get_database)) -> dict[str, Any]:
    try:
        return TrustVaultFeatureService(db).integrity_summary(entity_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/containers/{container_version_id}/validate")
def validate_container(
    container_version_id: str,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
    current_user: CurrentUser = Depends(require_permission("integrity:run")),
) -> dict[str, Any]:
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
            "overall_status": result["overall_status"],
        },
    )
    return result
