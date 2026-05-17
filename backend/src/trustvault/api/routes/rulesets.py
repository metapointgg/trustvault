from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_database
from trustvault.core.feature_services import TrustVaultFeatureService

router = APIRouter(prefix="/api/v1/rulesets", tags=["rulesets"])


@router.get("")
def list_rulesets(db: Session = Depends(get_database)) -> list[dict[str, Any]]:
    return TrustVaultFeatureService(db).rulesets()


@router.get("/{ruleset_id}")
def get_ruleset(ruleset_id: str, db: Session = Depends(get_database)) -> dict[str, Any]:
    try:
        return TrustVaultFeatureService(db).ruleset_detail(ruleset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/default/ensure")
def ensure_default_ruleset(db: Session = Depends(get_database)) -> dict[str, Any]:
    service = TrustVaultFeatureService(db)
    return service.ruleset_detail(str(service.ensure_default_ruleset().id))
