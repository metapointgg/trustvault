import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from trustvault.db.base import Base


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(300), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, default="customer")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EvidenceObject(Base):
    __tablename__ = "evidence_objects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    object_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_system: Mapped[str] = mapped_column(String(150), nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EntityContainerVersion(Base):
    __tablename__ = "entity_container_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="current")
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_object_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    manifest_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    hash_report_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), index=True, nullable=False, default="queued")
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="success")
    user_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    raw_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_query: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entity_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    object_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    search_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(150), nullable=True)
    export_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LicenceStatus(Base):
    __tablename__ = "licence_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    licence_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    state: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    modules: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    valid_until: Mapped[str | None] = mapped_column(String(30), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
