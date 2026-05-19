from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_database
from trustvault.auth.dependencies import require_permission
from trustvault.db.models import AuditEvent

router = APIRouter(
    prefix="/api/v1/audit",
    tags=["audit"],
    dependencies=[Depends(require_permission("audit:read"))],
)


class AuditEventResponse(BaseModel):
    id: str
    event_type: str
    status: str
    user_id: str | None
    session_id: str | None = None
    tenant_id: str | None = None
    raw_query: str | None = None
    structured_query: dict | None = None
    result_count: int | None = None
    entity_ids: list | None = None
    object_ids: list | None = None
    search_source: str | None = None
    ai_used: bool = False
    ai_provider: str | None = None
    ai_model: str | None = None
    export_path: str | None = None
    job_id: str | None = None
    request_id: str | None = None
    correlation_id: str | None
    error_message: str | None = None
    metadata_json: dict
    created_at: datetime


def serialise_event(event: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse(
        id=str(event.id),
        event_type=event.event_type,
        status=event.status,
        user_id=event.user_id,
        session_id=event.session_id,
        tenant_id=event.tenant_id,
        raw_query=event.raw_query,
        structured_query=event.structured_query,
        result_count=event.result_count,
        entity_ids=event.entity_ids,
        object_ids=event.object_ids,
        search_source=event.search_source,
        ai_used=event.ai_used,
        ai_provider=event.ai_provider,
        ai_model=event.ai_model,
        export_path=event.export_path,
        job_id=str(event.job_id) if event.job_id else None,
        request_id=event.request_id,
        correlation_id=event.correlation_id,
        error_message=event.error_message,
        metadata_json=event.metadata_json,
        created_at=event.created_at,
    )


@router.get("/events", response_model=list[AuditEventResponse])
def list_audit_events(db: Session = Depends(get_database), limit: int = 250) -> list[AuditEventResponse]:
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    return [serialise_event(event) for event in events]
