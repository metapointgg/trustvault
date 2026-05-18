import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_database, require_admin
from trustvault.core.feature_services import TrustVaultFeatureService
from trustvault.db.models import Ruleset, RulesetRule, User

router = APIRouter(prefix="/api/v1/rulesets", tags=["rulesets"])


class RulesetCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    version: int = Field(default=1, ge=1)
    status: str = Field(default="draft", pattern="^(draft|active|inactive|archived)$")
    description: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class RulesetUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    version: int | None = Field(default=None, ge=1)
    status: str | None = Field(default=None, pattern="^(draft|active|inactive|archived)$")
    description: str | None = None
    metadata_json: dict[str, Any] | None = None


class RuleCreateRequest(BaseModel):
    rule_key: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    document_type: str = Field(min_length=1, max_length=150)
    required: bool = True
    applies_when_json: dict[str, Any] = Field(default_factory=dict)
    max_age_days: int | None = Field(default=None, ge=1)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class RuleUpdateRequest(BaseModel):
    rule_key: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    document_type: str | None = Field(default=None, min_length=1, max_length=150)
    required: bool | None = None
    applies_when_json: dict[str, Any] | None = None
    max_age_days: int | None = Field(default=None, ge=1)
    metadata_json: dict[str, Any] | None = None


@router.get("")
def list_rulesets(db: Session = Depends(get_database)) -> list[dict[str, Any]]:
    return TrustVaultFeatureService(db).rulesets()


@router.post("")
def create_ruleset(request: RulesetCreateRequest, db: Session = Depends(get_database), _: User = Depends(require_admin)) -> dict[str, Any]:
    ruleset = Ruleset(
        name=request.name,
        version=request.version,
        status=request.status,
        description=request.description,
        metadata_json=request.metadata_json,
    )
    db.add(ruleset)
    db.commit()
    db.refresh(ruleset)
    return TrustVaultFeatureService(db).ruleset_detail(str(ruleset.id))


@router.get("/{ruleset_id}")
def get_ruleset(ruleset_id: str, db: Session = Depends(get_database)) -> dict[str, Any]:
    try:
        return TrustVaultFeatureService(db).ruleset_detail(ruleset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{ruleset_id}")
def update_ruleset(ruleset_id: str, request: RulesetUpdateRequest, db: Session = Depends(get_database), _: User = Depends(require_admin)) -> dict[str, Any]:
    ruleset = db.get(Ruleset, uuid.UUID(ruleset_id))
    if ruleset is None:
        raise HTTPException(status_code=404, detail="Ruleset not found")
    updates = request.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(ruleset, key, value)
    db.commit()
    return TrustVaultFeatureService(db).ruleset_detail(ruleset_id)


@router.delete("/{ruleset_id}")
def delete_ruleset(ruleset_id: str, db: Session = Depends(get_database), _: User = Depends(require_admin)) -> dict[str, Any]:
    ruleset = db.get(Ruleset, uuid.UUID(ruleset_id))
    if ruleset is None:
        raise HTTPException(status_code=404, detail="Ruleset not found")
    db.query(RulesetRule).filter(RulesetRule.ruleset_id == ruleset.id).delete()
    db.delete(ruleset)
    db.commit()
    return {"deleted": True, "ruleset_id": ruleset_id}


@router.post("/{ruleset_id}/rules")
def create_rule(ruleset_id: str, request: RuleCreateRequest, db: Session = Depends(get_database), _: User = Depends(require_admin)) -> dict[str, Any]:
    ruleset = db.get(Ruleset, uuid.UUID(ruleset_id))
    if ruleset is None:
        raise HTTPException(status_code=404, detail="Ruleset not found")
    rule = RulesetRule(ruleset_id=ruleset.id, **request.model_dump())
    db.add(rule)
    db.commit()
    return TrustVaultFeatureService(db).ruleset_detail(ruleset_id)


@router.patch("/{ruleset_id}/rules/{rule_id}")
def update_rule(ruleset_id: str, rule_id: str, request: RuleUpdateRequest, db: Session = Depends(get_database), _: User = Depends(require_admin)) -> dict[str, Any]:
    rule = db.scalars(
        select(RulesetRule).where(RulesetRule.id == uuid.UUID(rule_id)).where(RulesetRule.ruleset_id == uuid.UUID(ruleset_id))
    ).first()
    if rule is None:
        raise HTTPException(status_code=404, detail="Ruleset rule not found")
    updates = request.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(rule, key, value)
    db.commit()
    return TrustVaultFeatureService(db).ruleset_detail(ruleset_id)


@router.delete("/{ruleset_id}/rules/{rule_id}")
def delete_rule(ruleset_id: str, rule_id: str, db: Session = Depends(get_database), _: User = Depends(require_admin)) -> dict[str, Any]:
    rule = db.scalars(
        select(RulesetRule).where(RulesetRule.id == uuid.UUID(rule_id)).where(RulesetRule.ruleset_id == uuid.UUID(ruleset_id))
    ).first()
    if rule is None:
        raise HTTPException(status_code=404, detail="Ruleset rule not found")
    db.delete(rule)
    db.commit()
    return TrustVaultFeatureService(db).ruleset_detail(ruleset_id)


@router.post("/default/ensure")
def ensure_default_ruleset(db: Session = Depends(get_database)) -> dict[str, Any]:
    service = TrustVaultFeatureService(db)
    return service.ruleset_detail(str(service.ensure_default_ruleset().id))
