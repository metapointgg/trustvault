from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_database
from trustvault.core.feature_services import TrustVaultFeatureService
from trustvault.db.models import Entity, FitsIndexEntry

router = APIRouter(prefix="/api/v1/extraction", tags=["extraction"])


@router.get("/summary")
def extraction_summary(db: Session = Depends(get_database)) -> dict[str, Any]:
    """Return archive-wide extraction coverage from the search index.

    This deliberately avoids opening every FITS container on first page load.
    Entity-level detail remains available via /entities/{entity_id}/report.
    """

    entities = db.scalars(select(Entity).order_by(Entity.external_id.asc())).all()
    indexed_counts = {
        str(entity_id): count
        for entity_id, count in db.execute(
            select(FitsIndexEntry.entity_id, func.count(FitsIndexEntry.id)).group_by(FitsIndexEntry.entity_id)
        ).all()
    }
    text_counts = {
        str(entity_id): count
        for entity_id, count in db.execute(
            select(FitsIndexEntry.entity_id, func.count(FitsIndexEntry.id))
            .where(FitsIndexEntry.text_content != "")
            .group_by(FitsIndexEntry.entity_id)
        ).all()
    }
    character_counts = {
        str(entity_id): count
        for entity_id, count in db.execute(
            select(FitsIndexEntry.entity_id, func.coalesce(func.sum(func.length(FitsIndexEntry.text_content)), 0))
            .group_by(FitsIndexEntry.entity_id)
        ).all()
    }
    rows = []
    for entity in entities:
        entity_id = str(entity.id)
        indexed = int(indexed_counts.get(entity_id, 0) or 0)
        text_rows = int(text_counts.get(entity_id, 0) or 0)
        characters = int(character_counts.get(entity_id, 0) or 0)
        status = "ok" if text_rows > 0 else "no_text"
        rows.append(
            {
                "id": entity_id,
                "external_id": entity.external_id,
                "display_name": entity.display_name,
                "entity_type": entity.entity_type,
                "status": status,
                "risk_rating": (entity.metadata_json or {}).get("risk_rating"),
                "jurisdiction": (entity.metadata_json or {}).get("jurisdiction"),
                "score": 100 if text_rows > 0 else 0,
                "issue_count": 0 if text_rows > 0 else 1,
                "indexed_entry_count": indexed,
                "text_row_count": text_rows,
                "character_count": characters,
                "summary": f"{text_rows} text rows · {characters} characters",
            }
        )
    return {
        "entity_count": len(rows),
        "entities_with_text": sum(1 for row in rows if row["text_row_count"] > 0),
        "entities_without_text": sum(1 for row in rows if row["text_row_count"] == 0),
        "indexed_entry_count": sum(row["indexed_entry_count"] for row in rows),
        "text_row_count": sum(row["text_row_count"] for row in rows),
        "character_count": sum(row["character_count"] for row in rows),
        "results": rows,
    }


@router.get("/entities/{entity_id}/report")
def extraction_report(entity_id: str, db: Session = Depends(get_database)) -> dict[str, Any]:
    try:
        return TrustVaultFeatureService(db).extraction_report(entity_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc