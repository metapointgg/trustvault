from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_database
from trustvault.db.models import AuditEvent, Entity, EvidenceObject, Job

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_database)) -> dict:
    entity_count = db.scalar(select(func.count()).select_from(Entity)) or 0
    evidence_count = db.scalar(select(func.count()).select_from(EvidenceObject)) or 0
    queued_jobs = db.scalar(select(func.count()).select_from(Job).where(Job.status == "queued")) or 0
    running_jobs = db.scalar(select(func.count()).select_from(Job).where(Job.status == "running")) or 0
    audit_events = db.scalar(select(func.count()).select_from(AuditEvent)) or 0

    return {
        "product": "TrustVault",
        "tagline": "Secure evidence assurance for regulated customer records",
        "entity_count": entity_count,
        "evidence_object_count": evidence_count,
        "queued_jobs": queued_jobs,
        "running_jobs": running_jobs,
        "audit_event_count": audit_events,
        "licence_state": "not_checked",
    }
