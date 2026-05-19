from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_database
from trustvault.auth.dependencies import require_permission
from trustvault.auth.models import CurrentUser
from trustvault.core.container_builder import EntityContainerBuilder
from trustvault.core.feature_services import TrustVaultFeatureService
from trustvault.core.fits_reader import FitsContainerReader
from trustvault.db.models import Entity

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


class CustomerInformationUpdateRequest(BaseModel):
    display_name: str = Field(min_length=1)
    entity_type: str = Field(default="customer", min_length=1)
    jurisdiction: str | None = None
    risk_rating: str | None = None
    status: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    rebuild_container: bool = True
    rebuild_index: bool = True


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


@router.patch("/{customer_id}/information")
def update_customer_information(
    customer_id: str,
    request: CustomerInformationUpdateRequest,
    db: Session = Depends(get_database),
    current_user: CurrentUser = Depends(require_permission("customers:update")),
) -> dict[str, Any]:
    entity = db.scalars(select(Entity).where((Entity.id == customer_id) | (Entity.external_id == customer_id))).first()
    if entity is None:
        raise HTTPException(status_code=404, detail="Customer/entity not found")

    existing_metadata = entity.metadata_json or {}
    assurance_gaps = existing_metadata.get("assurance_gaps") if isinstance(existing_metadata.get("assurance_gaps"), list) else []
    resolved_gaps = []
    for gap in assurance_gaps:
        if gap.get("gap_key") == "customer_information_missing":
            resolved_gap = dict(gap)
            resolved_gap["status"] = "resolved"
            resolved_gap["resolved_by"] = current_user.subject
            resolved_gaps.append(resolved_gap)
        else:
            resolved_gaps.append(gap)

    next_metadata = {
        **existing_metadata,
        **request.metadata,
        "jurisdiction": request.jurisdiction,
        "risk_rating": request.risk_rating,
        "customer_information_status": "complete",
        "customer_json_supplied": existing_metadata.get("customer_json_supplied", False),
        "assurance_gaps": resolved_gaps,
        "customer_information_updated_by": current_user.subject,
    }

    entity.display_name = request.display_name
    entity.entity_type = request.entity_type.lower()
    if request.status:
        entity.status = request.status
    entity.metadata_json = next_metadata
    db.commit()
    db.refresh(entity)

    container: dict[str, Any] | None = None
    index: dict[str, Any] | None = None
    if request.rebuild_container:
        container = EntityContainerBuilder(db).rebuild(entity.external_id)
    if request.rebuild_index:
        index = FitsContainerReader(db).rebuild_index_from_current_fits(entity.external_id)

    return {
        "entity_id": str(entity.id),
        "entity_external_id": entity.external_id,
        "display_name": entity.display_name,
        "entity_type": entity.entity_type,
        "status": entity.status,
        "metadata": entity.metadata_json,
        "container": container,
        "index": index,
    }
