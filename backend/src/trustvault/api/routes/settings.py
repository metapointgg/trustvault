from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_database
from trustvault.auth.dependencies import require_permission
from trustvault.auth.models import CurrentUser
from trustvault.core.app_settings import AppSettingsService

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class SettingsUpdateRequest(BaseModel):
    updates: dict[str, Any] = Field(default_factory=dict)


@router.get("")
def list_settings(
    db: Session = Depends(get_database),
    current_user: CurrentUser = Depends(require_permission("settings:read")),
) -> dict[str, Any]:
    return AppSettingsService(db).list_settings()


@router.patch("")
def update_settings(
    request: SettingsUpdateRequest,
    db: Session = Depends(get_database),
    current_user: CurrentUser = Depends(require_permission("settings:manage")),
) -> dict[str, Any]:
    return AppSettingsService(db).update_settings(request.updates, updated_by_user_id=current_user.subject)
