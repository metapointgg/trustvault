from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_database
from trustvault.auth.dependencies import require_permission
from trustvault.auth.models import CurrentUser
from trustvault.core.auto_ingestion import DropFolderIngestionService

router = APIRouter(prefix="/api/v1/auto-ingestion", tags=["auto-ingestion"])


@router.get("/status")
def status(
    db: Session = Depends(get_database),
    current_user: CurrentUser = Depends(require_permission("ingestion:submit")),
) -> dict[str, Any]:
    return DropFolderIngestionService(db).status()


@router.post("/scan")
def scan_once(
    db: Session = Depends(get_database),
    current_user: CurrentUser = Depends(require_permission("ingestion:submit")),
) -> dict[str, Any]:
    return DropFolderIngestionService(db).scan_once()
