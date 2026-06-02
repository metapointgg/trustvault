from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_database, require_admin
from trustvault.core.demo_archives import DemoArchiveService
from trustvault.db.models import User

router = APIRouter(prefix="/api/v1/demo-archives", tags=["demo-archives"])


@router.get("")
def list_demo_archives(
    db: Session = Depends(get_database),
    current_user: User = Depends(require_admin),
) -> dict[str, Any]:
    return {"archives": DemoArchiveService(db).available_archives()}


@router.post("/{archive_key}/generate")
def generate_demo_archive(
    archive_key: str,
    db: Session = Depends(get_database),
    current_user: User = Depends(require_admin),
) -> dict[str, Any]:
    try:
        return DemoArchiveService(db).generate(archive_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
