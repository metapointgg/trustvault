from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_database
from trustvault.core.feature_services import TrustVaultFeatureService

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


@router.get("")
def list_customers(
    risk_rating: str | None = Query(default=None),
    jurisdiction: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=1000),
    db: Session = Depends(get_database),
) -> list[dict[str, Any]]:
    return TrustVaultFeatureService(db).customers(
        risk_rating=risk_rating,
        jurisdiction=jurisdiction,
        limit=limit,
    )


@router.get("/{customer_id}")
def get_customer(customer_id: str, db: Session = Depends(get_database)) -> dict[str, Any]:
    try:
        return TrustVaultFeatureService(db).customer_summary(customer_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{customer_id}/summary")
def get_customer_evidence_summary(customer_id: str, db: Session = Depends(get_database)) -> dict[str, Any]:
    try:
        return TrustVaultFeatureService(db).entity_evidence_summary(customer_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
