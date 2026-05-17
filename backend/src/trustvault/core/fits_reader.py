import io
import json
import uuid
from typing import Any

import numpy as np
from astropy.io import fits
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from trustvault.core.hashing import sha256_bytes
from trustvault.core.storage_uri import parse_storage_uri
from trustvault.db.models import Entity, EntityContainerVersion, FitsIndexEntry
from trustvault.settings import get_settings
from trustvault.storage.local import LocalFilesystemStorage


class FitsContainerReader:
    def __init__(self, db: Session):
        self.db = db
        settings = get_settings()
        self.storage = LocalFilesystemStorage(settings.local_storage_root)

    def inspect_current_for_entity(self, entity_id_or_external_id: str) -> dict[str, Any]:
        entity = self._get_entity(entity_id_or_external_id)
        version = self._get_current_fits_version(entity.id)
        return self.inspect_version(str(version.id))

    def inspect_version(self, container_version_id: str) -> dict[str, Any]:
        version = self.db.get(EntityContainerVersion, uuid.UUID(container_version_id))
        if version is None:
            raise ValueError("Container version not found")

        data = self._read_container_bytes(version)
        with fits.open(io.BytesIO(data), checksum=True) as hdul:
            hdu_summaries = []
            for index, hdu in enumerate(hdul):
                hdu_summaries.append(
                    {
                        "index": index,
                        "name": hdu.name,
                        "class_name": hdu.__class__.__name__,
                        "shape": list(hdu.data.shape) if getattr(hdu, "data", None) is not None else None,
                        "header": {
                            key: str(value)
                            for key, value in hdu.header.items()
                            if key not in {"COMMENT", "HISTORY"}
                        },
                    }
                )

            return {
                "container_version_id": str(version.id),
                "entity_id": str(version.entity_id),
                "version_number": version.version_number,
                "status": version.status,
                "storage_uri": version.storage_uri,
                "sha256": version.sha256,
                "size_bytes": len(data),
                "hdu_count": len(hdul),
                "hdu_names": [hdu.name for hdu in hdul],
                "summary": self._try_read_json_hdu(hdul, "SUMMARY"),
                "entity_metadata": self._try_read_json_hdu(hdul, "ENTITY_METADATA"),
                "manifest": self._try_read_json_hdu(hdul, "MANIFEST"),
                "ocr_text": self._try_read_json_hdu(hdul, "OCR_TEXT"),
                "hash_report": self._try_read_json_hdu(hdul, "HASH_REPORT"),
                "hdus": hdu_summaries,
            }

    def direct_search(self, entity_id_or_external_id: str, query: str, limit: int = 50) -> dict[str, Any]:
        entity = self._get_entity(entity_id_or_external_id)
        version = self._get_current_fits_version(entity.id)
        normalised_query = query.strip().lower()
        if not normalised_query:
            return self._empty_search_result(query, entity, version)

        data = self._read_container_bytes(version)
        results: list[dict[str, Any]] = []
        with fits.open(io.BytesIO(data), checksum=True) as hdul:
            manifest = self._try_read_json_hdu(hdul, "MANIFEST") or []
            ocr_rows = self._try_read_json_hdu(hdul, "OCR_TEXT") or []
            ocr_by_object = {row.get("object_id"): row for row in ocr_rows if isinstance(row, dict)}
            hdu_by_name = {hdu.name: hdu for hdu in hdul}

            for manifest_row in [row for row in manifest if isinstance(row, dict)]:
                hdu_name = manifest_row.get("hdu_name")
                payload_hdu = hdu_by_name.get(hdu_name)
                payload_text = self._payload_text(payload_hdu, manifest_row) if payload_hdu is not None else ""
                ocr_text = ocr_by_object.get(manifest_row.get("id"), {}).get("extracted_text", "")
                searchable = self._build_searchable_text(manifest_row, payload_text, ocr_text)
                if normalised_query in searchable.lower():
                    results.append(
                        {
                            "entity_id": str(entity.id),
                            "entity_external_id": entity.external_id,
                            "entity_display_name": entity.display_name,
                            "container_version_id": str(version.id),
                            "evidence_object_id": manifest_row.get("id"),
                            "hdu_name": hdu_name,
                            "filename": manifest_row.get("filename"),
                            "object_type": manifest_row.get("object_type"),
                            "source_system": manifest_row.get("source_system"),
                            "sha256": manifest_row.get("sha256"),
                            "snippet": self._snippet(searchable, normalised_query),
                        }
                    )
                if len(results) >= limit:
                    break

        return {
            "query": query,
            "entity_id": str(entity.id),
            "entity_external_id": entity.external_id,
            "container_version_id": str(version.id),
            "result_count": len(results),
            "results": results,
        }

    def index_search(self, query: str, entity_id_or_external_id: str | None = None, limit: int = 50) -> dict[str, Any]:
        normalised_query = query.strip().lower()
        if not normalised_query:
            return {"query": query, "result_count": 0, "results": []}

        entity: Entity | None = None
        statement = select(FitsIndexEntry).order_by(FitsIndexEntry.created_at.desc()).limit(500)
        if entity_id_or_external_id:
            entity = self._get_entity(entity_id_or_external_id)
            statement = (
                select(FitsIndexEntry)
                .where(FitsIndexEntry.entity_id == entity.id)
                .order_by(FitsIndexEntry.created_at.desc())
                .limit(500)
            )

        rows = self.db.scalars(statement).all()
        results: list[dict[str, Any]] = []
        for row in rows:
            searchable = "\n".join(
                [
                    row.filename or "",
                    row.object_type or "",
                    row.source_system or "",
                    row.text_content or "",
                    json.dumps(row.metadata_json or {}, default=str),
                ]
            )
            if normalised_query not in searchable.lower():
                continue
            row_entity = entity or self.db.get(Entity, row.entity_id)
            results.append(
                {
                    "entity_id": str(row.entity_id),
                    "entity_external_id": row_entity.external_id if row_entity else None,
                    "entity_display_name": row_entity.display_name if row_entity else None,
                    "container_version_id": str(row.container_version_id),
                    "evidence_object_id": row.evidence_object_id,
                    "hdu_name": row.hdu_name,
                    "filename": row.filename,
                    "object_type": row.object_type,
                    "source_system": row.source_system,
                    "sha256": row.sha256,
                    "snippet": self._snippet(searchable, normalised_query),
                }
            )
            if len(results) >= limit:
                break

        return {
            "query": query,
            "entity_id": str(entity.id) if entity else None,
            "entity_external_id": entity.external_id if entity else None,
            "result_count": len(results),
            "results": results,
        }

    def rebuild_index_from_current_fits(self, entity_id_or_external_id: str | None = None) -> dict[str, Any]:
        if entity_id_or_external_id:
            entities = [self._get_entity(entity_id_or_external_id)]
        else:
            entities = self.db.scalars(select(Entity).order_by(Entity.external_id.asc())).all()

        indexed: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for entity in entities:
            try:
                version = self._get_current_fits_version(entity.id)
            except ValueError:
                skipped.append(
                    {
                        "entity_id": str(entity.id),
                        "entity_external_id": entity.external_id,
                        "reason": "no_current_fits_container",
                    }
                )
                continue

            count = self._index_version(entity, version)
            indexed.append(
                {
                    "entity_id": str(entity.id),
                    "entity_external_id": entity.external_id,
                    "container_version_id": str(version.id),
                    "indexed_entry_count": count,
                }
            )

        self.db.commit()
        return {
            "indexed_entity_count": len(indexed),
            "skipped_entity_count": len(skipped),
            "indexed": indexed,
            "skipped": skipped,
        }

    def _index_version(self, entity: Entity, version: EntityContainerVersion) -> int:
        self.db.execute(delete(FitsIndexEntry).where(FitsIndexEntry.entity_id == entity.id))
        data = self._read_container_bytes(version)
        count = 0
        with fits.open(io.BytesIO(data), checksum=True) as hdul:
            manifest = self._try_read_json_hdu(hdul, "MANIFEST") or []
            ocr_rows = self._try_read_json_hdu(hdul, "OCR_TEXT") or []
            ocr_by_object = {row.get("object_id"): row for row in ocr_rows if isinstance(row, dict)}
            hdu_by_name = {hdu.name: hdu for hdu in hdul}
            for manifest_row in [row for row in manifest if isinstance(row, dict)]:
                hdu_name = manifest_row.get("hdu_name")
                payload_hdu = hdu_by_name.get(hdu_name)
                payload_text = self._payload_text(payload_hdu, manifest_row) if payload_hdu is not None else ""
                ocr_text = ocr_by_object.get(manifest_row.get("id"), {}).get("extracted_text", "")
                text_content = self._build_searchable_text(manifest_row, payload_text, ocr_text)
                self.db.add(
                    FitsIndexEntry(
                        entity_id=entity.id,
                        container_version_id=version.id,
                        evidence_object_id=manifest_row.get("id"),
                        hdu_name=str(hdu_name or ""),
                        filename=manifest_row.get("filename"),
                        object_type=manifest_row.get("object_type"),
                        source_system=manifest_row.get("source_system"),
                        sha256=manifest_row.get("sha256"),
                        text_content=text_content,
                        metadata_json=manifest_row,
                    )
                )
                count += 1
        return count

    def _empty_search_result(self, query: str, entity: Entity, version: EntityContainerVersion) -> dict[str, Any]:
        return {
            "query": query,
            "entity_id": str(entity.id),
            "entity_external_id": entity.external_id,
            "container_version_id": str(version.id),
            "result_count": 0,
            "results": [],
        }

    def _build_searchable_text(self, manifest_row: dict[str, Any], payload_text: str, ocr_text: str) -> str:
        return "\n".join(
            [
                str(manifest_row.get("filename", "")),
                str(manifest_row.get("object_type", "")),
                str(manifest_row.get("source_system", "")),
                json.dumps(manifest_row.get("metadata", {}), default=str),
                payload_text or "",
                ocr_text or "",
            ]
        ).strip()

    def _get_entity(self, entity_id_or_external_id: str) -> Entity:
        try:
            parsed_id = uuid.UUID(entity_id_or_external_id)
            entity = self.db.get(Entity, parsed_id)
            if entity is not None:
                return entity
        except ValueError:
            pass
        entity = self.db.scalars(select(Entity).where(Entity.external_id == entity_id_or_external_id)).first()
        if entity is None:
            raise ValueError("Entity not found")
        return entity

    def _get_current_fits_version(self, entity_id: uuid.UUID) -> EntityContainerVersion:
        version = self.db.scalars(
            select(EntityContainerVersion)
            .where(EntityContainerVersion.entity_id == entity_id)
            .where(EntityContainerVersion.status == "current")
            .where(EntityContainerVersion.storage_uri.ilike("%.fits"))
            .order_by(EntityContainerVersion.version_number.desc())
            .limit(1)
        ).first()
        if version is None:
            raise ValueError("Entity has no current FITS container")
        return version

    def _read_container_bytes(self, version: EntityContainerVersion) -> bytes:
        parsed = parse_storage_uri(version.storage_uri)
        if parsed.provider != "local":
            raise ValueError(f"FITS read is not yet implemented for provider: {parsed.provider}")
        return self.storage.get_bytes(parsed.bucket, parsed.key)

    def _try_read_json_hdu(self, hdul: fits.HDUList, name: str) -> Any:
        hdu_by_name = {hdu.name: hdu for hdu in hdul}
        if name not in hdu_by_name:
            return None
        raw = self._hdu_bytes(hdu_by_name[name])
        return json.loads(raw.decode("utf-8"))

    def _payload_text(self, hdu: fits.ImageHDU, manifest_row: dict[str, Any]) -> str:
        content_type = str(manifest_row.get("content_type") or hdu.header.get("MIMETYPE") or "")
        if not content_type.startswith("text/"):
            return ""
        return self._hdu_bytes(hdu).decode("utf-8", errors="replace")

    def _hdu_bytes(self, hdu: fits.ImageHDU) -> bytes:
        if hdu.data is None:
            return b""
        return np.asarray(hdu.data, dtype=np.uint8).tobytes()

    def _snippet(self, text: str, normalised_query: str, window: int = 120) -> str:
        lower_text = text.lower()
        index = lower_text.find(normalised_query)
        if index < 0:
            return text[: window * 2]
        start = max(index - window, 0)
        end = min(index + len(normalised_query) + window, len(text))
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(text) else ""
        return f"{prefix}{text[start:end]}{suffix}"
