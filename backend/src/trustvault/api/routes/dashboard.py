from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_database
from trustvault.auth.dependencies import require_permission
from trustvault.core.feature_services import TrustVaultFeatureService

router = APIRouter(
    prefix="/api/v1/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(require_permission("customers:read"))],
)


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_database)) -> dict[str, Any]:
    return TrustVaultFeatureService(db).dashboard()
