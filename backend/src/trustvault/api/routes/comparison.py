from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_database
from trustvault.auth.dependencies import require_permission
from trustvault.core.feature_services import TrustVaultFeatureService

router = APIRouter(
    prefix="/api/v1/comparison",
    tags=["comparison"],
    dependencies=[Depends(require_permission("integrity:run"))],
)


@router.get("/entities/{entity_id}/fits-vs-db")
def fits_vs_database(
    entity_id: str,
    query: str | None = Query(default=None),
    db: Session = Depends(get_database),
) -> dict[str, Any]:
    try:
        return TrustVaultFeatureService(db).comparison(entity_id, query=query)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
