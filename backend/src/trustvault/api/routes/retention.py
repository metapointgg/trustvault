from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_database
from trustvault.core.feature_services import TrustVaultFeatureService

router = APIRouter(prefix="/api/v1/retention", tags=["retention"])


@router.get("/report")
def retention_report(db: Session = Depends(get_database)) -> dict[str, Any]:
    return TrustVaultFeatureService(db).retention_report()


@router.get("/entities/{entity_id}")
def entity_retention_report(entity_id: str, db: Session = Depends(get_database)) -> dict[str, Any]:
    try:
        return TrustVaultFeatureService(db).retention_report(entity_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
