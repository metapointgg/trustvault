from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_database
from trustvault.core.feature_services import TrustVaultFeatureService

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


@router.get("")
def list_customers(db: Session = Depends(get_database)) -> list[dict[str, Any]]:
    return TrustVaultFeatureService(db).customers()


@router.get("/{customer_id}")
def get_customer(customer_id: str, db: Session = Depends(get_database)) -> dict[str, Any]:
    try:
        return TrustVaultFeatureService(db).customer_summary(customer_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
