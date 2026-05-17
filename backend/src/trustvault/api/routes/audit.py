from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_database
from trustvault.db.models import AuditEvent

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


class AuditEventResponse(BaseModel):
    id: str
    event_type: str
    status: str
    user_id: str | None
    correlation_id: str | None
    metadata_json: dict
    created_at: datetime


def serialise_event(event: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse(
        id=str(event.id),
        event_type=event.event_type,
        status=event.status,
        user_id=event.user_id,
        correlation_id=event.correlation_id,
        metadata_json=event.metadata_json,
        created_at=event.created_at,
    )


@router.get("/events", response_model=list[AuditEventResponse])
def list_audit_events(db: Session = Depends(get_database), limit: int = 100) -> list[AuditEventResponse]:
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    return [serialise_event(event) for event in events]
