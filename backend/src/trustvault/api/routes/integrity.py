from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from trustvault.audit.events import INTEGRITY_VALIDATION_RUN
from trustvault.audit.logger import AuditLogger
from trustvault.api.dependencies import get_audit_logger, get_database
from trustvault.core.feature_services import TrustVaultFeatureService
from trustvault.core.integrity import ContainerIntegrityValidator

router = APIRouter(prefix="/api/v1/integrity", tags=["integrity"])


@router.get("/summary")
def integrity_summary(db: Session = Depends(get_database)) -> dict[str, Any]:
    return TrustVaultFeatureService(db).integrity_summary()


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
) -> dict[str, Any]:
    try:
        result = ContainerIntegrityValidator(db).validate_container_version(container_version_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit_logger.log(
        INTEGRITY_VALIDATION_RUN,
        status="success" if result["overall_status"] == "valid" else "error",
        entity_ids=[result["entity_id"]],
        metadata={
            "container_version_id": container_version_id,
            "overall_status": result["overall_status"],
        },
    )
    return result
