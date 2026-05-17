from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.core.container_builder import EntityContainerBuilder
from trustvault.db.models import Entity, EntityContainerVersion


class ContainerStatusService:
    def __init__(self, db: Session):
        self.db = db

    def entity_container_status(self) -> dict[str, Any]:
        entities = self.db.scalars(select(Entity).order_by(Entity.external_id.asc())).all()
        rows: list[dict[str, Any]] = []

        for entity in entities:
            current = self.db.scalars(
                select(EntityContainerVersion)
                .where(EntityContainerVersion.entity_id == entity.id)
                .where(EntityContainerVersion.status == "current")
                .order_by(EntityContainerVersion.version_number.desc())
                .limit(1)
            ).first()

            all_versions = self.db.scalars(
                select(EntityContainerVersion)
                .where(EntityContainerVersion.entity_id == entity.id)
                .order_by(EntityContainerVersion.version_number.desc())
            ).all()

            has_current_fits = bool(current and current.storage_uri.lower().endswith(".fits"))
            rows.append(
                {
                    "entity_id": str(entity.id),
                    "entity_external_id": entity.external_id,
                    "entity_display_name": entity.display_name,
                    "has_current_fits_container": has_current_fits,
                    "current_container_version_id": str(current.id) if current else None,
                    "current_version_number": current.version_number if current else None,
                    "current_storage_uri": current.storage_uri if current else None,
                    "current_status": current.status if current else None,
                    "version_count": len(all_versions),
                    "legacy_placeholder_count": len(
                        [version for version in all_versions if version.status == "legacy_invalid_placeholder"]
                    ),
                }
            )

        missing = [row for row in rows if not row["has_current_fits_container"]]
        return {
            "entity_count": len(rows),
            "entities_with_current_fits": len(rows) - len(missing),
            "entities_missing_current_fits": len(missing),
            "entities": rows,
        }

    def rebuild_missing_current_fits(self) -> dict[str, Any]:
        status = self.entity_container_status()
        rebuilt: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        builder = EntityContainerBuilder(self.db)

        for row in status["entities"]:
            if row["has_current_fits_container"]:
                skipped.append(
                    {
                        "entity_external_id": row["entity_external_id"],
                        "reason": "already_has_current_fits_container",
                        "current_storage_uri": row["current_storage_uri"],
                    }
                )
                continue

            result = builder.rebuild(row["entity_external_id"])
            rebuilt.append(result)

        return {
            "rebuilt_count": len(rebuilt),
            "skipped_count": len(skipped),
            "rebuilt": rebuilt,
            "skipped": skipped,
        }
