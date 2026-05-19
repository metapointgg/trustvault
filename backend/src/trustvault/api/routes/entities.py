import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_database
from trustvault.auth.dependencies import require_permission
from trustvault.db.models import Entity, EvidenceObject

router = APIRouter(
    prefix="/api/v1/entities",
    tags=["entities"],
    dependencies=[Depends(require_permission("evidence:read"))],
)


class EntityResponse(BaseModel):
    id: str
    external_id: str
    display_name: str
    entity_type: str
    status: str
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class EvidenceObjectResponse(BaseModel):
    id: str
    entity_id: str
    object_type: str
    source_system: str
    storage_uri: str
    sha256: str
    content_type: str | None
    metadata_json: dict
    created_at: datetime


def serialise_entity(entity: Entity) -> EntityResponse:
    return EntityResponse(
        id=str(entity.id),
        external_id=entity.external_id,
        display_name=entity.display_name,
        entity_type=entity.entity_type,
        status=entity.status,
        metadata_json=entity.metadata_json,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def serialise_evidence_object(evidence: EvidenceObject) -> EvidenceObjectResponse:
    return EvidenceObjectResponse(
        id=str(evidence.id),
        entity_id=str(evidence.entity_id),
        object_type=evidence.object_type,
        source_system=evidence.source_system,
        storage_uri=evidence.storage_uri,
        sha256=evidence.sha256,
        content_type=evidence.content_type,
        metadata_json=evidence.metadata_json,
        created_at=evidence.created_at,
    )


@router.get("", response_model=list[EntityResponse])
def list_entities(db: Session = Depends(get_database), limit: int = 100) -> list[EntityResponse]:
    entities = db.scalars(select(Entity).order_by(Entity.created_at.desc()).limit(limit)).all()
    return [serialise_entity(entity) for entity in entities]


@router.get("/{entity_id}", response_model=EntityResponse)
def get_entity(entity_id: str, db: Session = Depends(get_database)) -> EntityResponse:
    entity = _get_entity_by_any_id(db, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return serialise_entity(entity)


@router.get("/{entity_id}/evidence", response_model=list[EvidenceObjectResponse])
def list_entity_evidence(
    entity_id: str,
    db: Session = Depends(get_database),
    limit: int = 200,
) -> list[EvidenceObjectResponse]:
    entity = _get_entity_by_any_id(db, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    evidence_objects = db.scalars(
        select(EvidenceObject)
        .where(EvidenceObject.entity_id == entity.id)
        .order_by(EvidenceObject.created_at.desc())
        .limit(limit)
    ).all()
    return [serialise_evidence_object(evidence) for evidence in evidence_objects]


def _get_entity_by_any_id(db: Session, entity_id: str) -> Entity | None:
    try:
        parsed_id = uuid.UUID(entity_id)
        entity = db.get(Entity, parsed_id)
        if entity is not None:
            return entity
    except ValueError:
        pass

    return db.scalars(select(Entity).where(Entity.external_id == entity_id)).first()
