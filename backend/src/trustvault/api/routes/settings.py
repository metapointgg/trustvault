from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_current_user, get_database, require_admin
from trustvault.core.app_settings import AppSettingsService
from trustvault.core.document_classification import DocumentClassificationService
from trustvault.core.industry_pack_config import IndustryPackConfigService
from trustvault.core.industry_rulesets import IndustryRulesetService
from trustvault.core.query_vocabulary import QueryVocabularyService
from trustvault.db.models import User

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class SettingsUpdateRequest(BaseModel):
    updates: dict[str, Any] = Field(default_factory=dict)


class DocumentClassificationSettingsRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


class IndustryPackUpdateRequest(BaseModel):
    pack: dict[str, Any] = Field(default_factory=dict)


class IndustryRulesetUpdateRequest(BaseModel):
    ruleset: dict[str, Any] = Field(default_factory=dict)


@router.get("")
def list_settings(
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return AppSettingsService(db).list_settings()


@router.patch("")
def update_settings(
    request: SettingsUpdateRequest,
    db: Session = Depends(get_database),
    current_user: User = Depends(require_admin),
) -> dict[str, Any]:
    return AppSettingsService(db).update_settings(request.updates, updated_by_user_id=str(current_user.id))


@router.get("/industry-packs")
def get_industry_packs(
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return IndustryPackConfigService(db).list_packs()


@router.get("/industry-packs/active")
def get_active_industry_pack(
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return QueryVocabularyService(db).active_pack()


@router.get("/industry-packs/{industry_key}")
def get_industry_pack_by_key(
    industry_key: str,
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return IndustryPackConfigService(db).get_pack(industry_key)


@router.put("/industry-packs/{industry_key}")
def update_industry_pack_by_key(
    industry_key: str,
    request: IndustryPackUpdateRequest,
    db: Session = Depends(get_database),
    current_user: User = Depends(require_admin),
) -> dict[str, Any]:
    try:
        return IndustryPackConfigService(db).save_pack(industry_key, request.pack, updated_by_user_id=str(current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/industry-packs/{industry_key}/override")
def reset_industry_pack_by_key(
    industry_key: str,
    db: Session = Depends(get_database),
    current_user: User = Depends(require_admin),
) -> dict[str, Any]:
    return IndustryPackConfigService(db).reset_pack(industry_key)


@router.get("/industry-rulesets")
def get_industry_rulesets(
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return IndustryRulesetService(db).list_configs()


@router.get("/industry-rulesets/{industry_key}")
def get_industry_ruleset(
    industry_key: str,
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return IndustryRulesetService(db).ruleset_config(industry_key)


@router.put("/industry-rulesets/{industry_key}")
def update_industry_ruleset(
    industry_key: str,
    request: IndustryRulesetUpdateRequest,
    db: Session = Depends(get_database),
    current_user: User = Depends(require_admin),
) -> dict[str, Any]:
    try:
        return IndustryRulesetService(db).save_ruleset_config(industry_key, request.ruleset, updated_by_user_id=str(current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/industry-rulesets/{industry_key}/override")
def reset_industry_ruleset(
    industry_key: str,
    db: Session = Depends(get_database),
    current_user: User = Depends(require_admin),
) -> dict[str, Any]:
    return IndustryRulesetService(db).reset_ruleset_config(industry_key)


@router.get("/document-classification")
def get_document_classification_settings(
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    config = DocumentClassificationService(db).get_config()
    return {"config": config, "document_types": config.get("document_types", [])}


@router.put("/document-classification")
def update_document_classification_settings(
    request: DocumentClassificationSettingsRequest,
    db: Session = Depends(get_database),
    current_user: User = Depends(require_admin),
) -> dict[str, Any]:
    config = DocumentClassificationService(db).save_config(request.config, updated_by_user_id=str(current_user.id))
    return {"config": config, "document_types": config.get("document_types", [])}
