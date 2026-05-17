from fastapi import APIRouter
from sqlalchemy import text

from trustvault.db.session import engine
from trustvault.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    database_status = "unknown"

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception as exc:  # pragma: no cover - defensive health check
        database_status = f"error: {exc.__class__.__name__}"

    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "database": database_status,
        "storage_provider": settings.storage_provider,
        "queue_provider": settings.queue_provider,
        "ai_provider": settings.ai_provider,
        "ocr_provider": settings.ocr_provider,
    }
