import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.audit.events import JOB_SUBMITTED
from trustvault.audit.logger import AuditLogger
from trustvault.api.dependencies import get_audit_logger, get_database
from trustvault.db.models import Job

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


class JobCreateRequest(BaseModel):
    job_type: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_by_user_id: str | None = None


class JobResponse(BaseModel):
    id: str
    job_type: str
    status: str
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error_message: str | None
    correlation_id: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


def serialise_job(job: Job) -> JobResponse:
    return JobResponse(
        id=str(job.id),
        job_type=job.job_type,
        status=job.status,
        payload=job.payload,
        result=job.result,
        error_message=job.error_message,
        correlation_id=job.correlation_id,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.post("", response_model=JobResponse)
def create_job(
    request: JobCreateRequest,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> JobResponse:
    correlation_id = str(uuid.uuid4())
    job = Job(
        job_type=request.job_type,
        status="queued",
        payload=request.payload,
        created_by_user_id=request.created_by_user_id,
        correlation_id=correlation_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    audit_logger.log(
        JOB_SUBMITTED,
        user_id=request.created_by_user_id,
        correlation_id=correlation_id,
        job_id=job.id,
        metadata={"job_type": request.job_type},
    )
    return serialise_job(job)


@router.get("", response_model=list[JobResponse])
def list_jobs(db: Session = Depends(get_database), limit: int = 50) -> list[JobResponse]:
    jobs = db.scalars(select(Job).order_by(Job.created_at.desc()).limit(limit)).all()
    return [serialise_job(job) for job in jobs]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_database)) -> JobResponse:
    try:
        parsed_id = uuid.UUID(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid job id") from exc

    job = db.get(Job, parsed_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return serialise_job(job)


@router.post("/{job_id}/complete", response_model=JobResponse)
def complete_job(job_id: str, db: Session = Depends(get_database)) -> JobResponse:
    job = db.get(Job, uuid.UUID(job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = "succeeded"
    job.completed_at = datetime.now(timezone.utc)
    job.result = {"message": "Manually completed"}
    db.commit()
    db.refresh(job)
    return serialise_job(job)
