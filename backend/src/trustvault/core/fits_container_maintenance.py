from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.core.storage_uri import parse_storage_uri
from trustvault.db.models import Entity, EntityContainerVersion
from trustvault.settings import get_settings
from trustvault.storage.local import LocalFilesystemStorage


class FitsContainerMaintenanceService:
    """Maintenance helpers for FITS container references.

    These helpers deliberately avoid deleting container records. Stale current
    pointers are marked as missing_storage so they stop being selected by normal
    current-container logic while preserving an audit-friendly record of what was
    wrong.
    """

    def __init__(self, db: Session):
        self.db = db
        settings = get_settings()
        self.local_storage = LocalFilesystemStorage(settings.local_storage_root)

    def find_stale_current_fits_versions(self, *, entity_reference: str | None = None) -> dict[str, Any]:
        rows = self._candidate_versions(entity_reference=entity_reference)
        stale: list[dict[str, Any]] = []
        valid_count = 0
        unsupported_count = 0

        for entity, version in rows:
            status = self._storage_status(version)
            if status["storage_exists"] is True:
                valid_count += 1
                continue
            if status["provider_supported"] is False:
                unsupported_count += 1
                continue
            stale.append(self._version_row(entity, version, status))

        return {
            "checked_count": len(rows),
            "valid_count": valid_count,
            "unsupported_provider_count": unsupported_count,
            "stale_count": len(stale),
            "stale": stale,
        }

    def mark_stale_current_fits_versions(self, *, entity_reference: str | None = None) -> dict[str, Any]:
        diagnostic = self.find_stale_current_fits_versions(entity_reference=entity_reference)
        marked: list[dict[str, Any]] = []
        stale_ids = {item["container_version_id"] for item in diagnostic["stale"]}

        if not stale_ids:
            return {**diagnostic, "marked_count": 0, "marked": []}

        rows = self._candidate_versions(entity_reference=entity_reference)
        for entity, version in rows:
            if str(version.id) not in stale_ids:
                continue
            version.status = "missing_storage"
            marked.append(
                {
                    "entity_id": str(entity.id),
                    "entity_external_id": entity.external_id,
                    "container_version_id": str(version.id),
                    "version_number": version.version_number,
                    "storage_uri": version.storage_uri,
                    "new_status": version.status,
                }
            )

        self.db.commit()
        return {**diagnostic, "marked_count": len(marked), "marked": marked}

    def _candidate_versions(self, *, entity_reference: str | None) -> list[tuple[Entity, EntityContainerVersion]]:
        statement = (
            select(Entity, EntityContainerVersion)
            .join(EntityContainerVersion, EntityContainerVersion.entity_id == Entity.id)
            .where(EntityContainerVersion.status == "current")
            .where(EntityContainerVersion.storage_uri.ilike("%.fits"))
            .order_by(Entity.external_id.asc(), EntityContainerVersion.version_number.desc())
        )
        if entity_reference:
            entity = self._get_entity(entity_reference)
            statement = statement.where(Entity.id == entity.id)
        return list(self.db.execute(statement).all())

    def _storage_status(self, version: EntityContainerVersion) -> dict[str, Any]:
        try:
            parsed = parse_storage_uri(version.storage_uri)
        except ValueError as exc:
            return {
                "provider_supported": False,
                "storage_exists": None,
                "reason": "invalid_storage_uri",
                "detail": str(exc),
            }
        if parsed.provider != "local":
            return {
                "provider_supported": False,
                "storage_exists": None,
                "reason": "unsupported_storage_provider",
                "detail": f"Provider {parsed.provider} is not checked by local maintenance.",
            }
        exists = self.local_storage.exists(parsed.bucket, parsed.key)
        return {
            "provider_supported": True,
            "storage_exists": exists,
            "reason": None if exists else "current_fits_storage_file_missing",
            "bucket": parsed.bucket,
            "key": parsed.key,
        }

    def _version_row(self, entity: Entity, version: EntityContainerVersion, status: dict[str, Any]) -> dict[str, Any]:
        return {
            "entity_id": str(entity.id),
            "entity_external_id": entity.external_id,
            "entity_display_name": entity.display_name,
            "container_version_id": str(version.id),
            "version_number": version.version_number,
            "status": version.status,
            "storage_uri": version.storage_uri,
            "sha256": version.sha256,
            "size_bytes": version.size_bytes,
            "reason": status.get("reason"),
            "detail": status.get("detail"),
            "bucket": status.get("bucket"),
            "key": status.get("key"),
        }

    def _get_entity(self, entity_reference: str) -> Entity:
        from uuid import UUID

        try:
            parsed_id = UUID(entity_reference)
            entity = self.db.get(Entity, parsed_id)
            if entity is not None:
                return entity
        except ValueError:
            pass
        entity = self.db.scalars(select(Entity).where(Entity.external_id == entity_reference)).first()
        if entity is None:
            raise ValueError("Entity not found")
        return entity
