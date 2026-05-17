from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_database
from trustvault.core.feature_services import TrustVaultFeatureService
from trustvault.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_database)) -> dict[str, Any]:
    settings = get_settings()
    result = TrustVaultFeatureService(db).health()
    return {
        **result,
        "app": settings.app_name,
        "environment": settings.environment,
        "storage_provider": settings.storage_provider,
        "queue_provider": settings.queue_provider,
        "ai_provider": settings.ai_provider,
        "ocr_provider": settings.ocr_provider,
    }


@router.get("/api/v1/health")
def api_health(db: Session = Depends(get_database)) -> dict[str, Any]:
    return health(db)
