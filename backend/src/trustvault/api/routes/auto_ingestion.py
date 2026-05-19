from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_current_user, get_database, require_admin
from trustvault.core.auto_ingestion import DropFolderIngestionService
from trustvault.db.models import User

router = APIRouter(prefix="/api/v1/auto-ingestion", tags=["auto-ingestion"])


@router.get("/status")
def status(
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return DropFolderIngestionService(db).status()


@router.post("/scan")
def scan_once(
    db: Session = Depends(get_database),
    current_user: User = Depends(require_admin),
) -> dict[str, Any]:
    return DropFolderIngestionService(db).scan_once()
