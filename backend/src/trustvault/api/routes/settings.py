from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_current_user, get_database, require_admin
from trustvault.core.app_settings import AppSettingsService
from trustvault.core.document_classification import DocumentClassificationService
from trustvault.core.industry_packs import get_industry_pack, list_industry_packs
from trustvault.core.query_vocabulary import QueryVocabularyService
from trustvault.db.models import User

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class SettingsUpdateRequest(BaseModel):
    updates: dict[str, Any] = Field(default_factory=dict)


class DocumentClassificationSettingsRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


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
    values = AppSettingsService(db).effective_values()
    active_key = str(values.get("client_industry") or "financial_services")
    return {"active_industry": active_key, "industry_packs": list_industry_packs()}


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
    return get_industry_pack(industry_key).to_dict()


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
