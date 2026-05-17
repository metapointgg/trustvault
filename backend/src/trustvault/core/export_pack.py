import io
import json
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any

import numpy as np
from astropy.io import fits
from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.core.hashing import sha256_bytes
from trustvault.core.storage_uri import parse_storage_uri
from trustvault.db.models import Entity, EntityContainerVersion, ExportPack
from trustvault.settings import get_settings
from trustvault.storage.local import LocalFilesystemStorage


class RegulatorEvidencePackExporter:
    """Creates a regulator-ready export pack derived from the current FITS container."""

    def __init__(self, db: Session):
        self.db = db
        settings = get_settings()
        self.storage = LocalFilesystemStorage(settings.local_storage_root)

    def export_entity_pack(
        self,
        entity_id_or_external_id: str,
        *,
        created_by_job_id: str | None = None,
        created_by_user_id: str | None = None,
    ) -> dict[str, Any]:
        entity = self._get_entity(entity_id_or_external_id)
        container = self._get_current_fits_version(entity.id)
        fits_bytes = self._read_container_bytes(container)
        pack_id = str(uuid.uuid4())
        exported_at = datetime.now(timezone.utc).isoformat()

        with fits.open(io.BytesIO(fits_bytes), checksum=True) as hdul:
            summary = self._read_json_hdu(hdul, "SUMMARY") or {}
            entity_metadata = self._read_json_hdu(hdul, "ENTITY_METADATA") or {}
            manifest = self._read_json_hdu(hdul, "MANIFEST") or []
            hash_report = self._read_json_hdu(hdul, "HASH_REPORT") or {}
            ocr_text = self._read_json_hdu(hdul, "OCR_TEXT") or []
            export_manifest = self._build_export_manifest(
                pack_id=pack_id,
                exported_at=exported_at,
                entity=entity,
                container=container,
                summary=summary,
                manifest=manifest,
                hash_report=hash_report,
            )
            pack_bytes = self._build_zip_pack(
                hdul=hdul,
                fits_bytes=fits_bytes,
                entity=entity,
                container=container,
                export_manifest=export_manifest,
                summary=summary,
                entity_metadata=entity_metadata,
                manifest=manifest,
                hash_report=hash_report,
                ocr_text=ocr_text,
            )

        pack_sha256 = sha256_bytes(pack_bytes)
        key = f"{entity.external_id}/{pack_id}/regulator-evidence-pack.zip"
        stored = self.storage.put_bytes(
            bucket="export-packs",
            key=key,
            data=pack_bytes,
            content_type="application/zip",
        )

        export_pack = ExportPack(
            id=uuid.UUID(pack_id),
            entity_id=entity.id,
            container_version_id=container.id,
            export_type="regulator_evidence_pack",
            status="created",
            storage_uri=stored.uri,
            sha256=pack_sha256,
            size_bytes=len(pack_bytes),
            evidence_object_count=len(manifest),
            manifest_json=export_manifest,
            created_by_job_id=uuid.UUID(created_by_job_id) if created_by_job_id else None,
            created_by_user_id=created_by_user_id,
        )
        self.db.add(export_pack)
        self.db.commit()
        self.db.refresh(export_pack)

        return self._serialise_export_pack(export_pack, entity, container)

    def list_entity_packs(self, entity_id_or_external_id: str) -> list[dict[str, Any]]:
        entity = self._get_entity(entity_id_or_external_id)
        packs = self.db.scalars(
            select(ExportPack)
            .where(ExportPack.entity_id == entity.id)
            .order_by(ExportPack.created_at.desc())
        ).all()
        return [self._serialise_export_pack(pack, entity, None) for pack in packs]

    def _build_export_manifest(
        self,
        *,
        pack_id: str,
        exported_at: str,
        entity: Entity,
        container: EntityContainerVersion,
        summary: dict[str, Any],
        manifest: list[dict[str, Any]],
        hash_report: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "product": "TrustVault",
            "export_type": "regulator_evidence_pack",
            "export_pack_id": pack_id,
            "exported_at": exported_at,
            "source_of_truth": "Current TrustVault FITS evidence container",
            "entity": {
                "id": str(entity.id),
                "external_id": entity.external_id,
                "display_name": entity.display_name,
                "entity_type": entity.entity_type,
                "status": entity.status,
            },
            "container": {
                "container_version_id": str(container.id),
                "version_number": container.version_number,
                "storage_uri": container.storage_uri,
                "sha256": container.sha256,
                "size_bytes": container.size_bytes,
                "evidence_object_count": container.evidence_object_count,
            },
            "summary": summary,
            "evidence_object_count": len(manifest),
            "evidence_objects": manifest,
            "hash_report": hash_report,
            "pack_contents": [
                "README.md",
                "export_manifest.json",
                "container_summary.json",
                "entity_metadata.json",
                "evidence_manifest.json",
                "hash_report.json",
                "ocr_text.json",
                "source_fits/current_container.fits",
                "payloads/<source_system>/<object_type>/<hdu_name>/<filename>",
            ],
        }

    def _build_zip_pack(
        self,
        *,
        hdul: fits.HDUList,
        fits_bytes: bytes,
        entity: Entity,
        container: EntityContainerVersion,
        export_manifest: dict[str, Any],
        summary: dict[str, Any],
        entity_metadata: dict[str, Any],
        manifest: list[dict[str, Any]],
        hash_report: dict[str, Any],
        ocr_text: list[dict[str, Any]],
    ) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "README.md",
                self._readme(entity=entity, container=container, export_manifest=export_manifest),
            )
            self._write_json(archive, "export_manifest.json", export_manifest)
            self._write_json(archive, "container_summary.json", summary)
            self._write_json(archive, "entity_metadata.json", entity_metadata)
            self._write_json(archive, "evidence_manifest.json", manifest)
            self._write_json(archive, "hash_report.json", hash_report)
            self._write_json(archive, "ocr_text.json", ocr_text)
            archive.writestr("source_fits/current_container.fits", fits_bytes)

            hdu_by_name = {hdu.name: hdu for hdu in hdul}
            for evidence in [item for item in manifest if isinstance(item, dict)]:
                hdu_name = evidence.get("hdu_name")
                if not hdu_name or hdu_name not in hdu_by_name:
                    continue
                payload = self._hdu_bytes(hdu_by_name[hdu_name])
                filename = evidence.get("filename") or f"{hdu_name}.bin"
                object_type = evidence.get("object_type") or "unknown_object_type"
                source_system = evidence.get("source_system") or "unknown_source_system"
                path = f"payloads/{source_system}/{object_type}/{hdu_name}/{filename}"
                archive.writestr(path, payload)
        return buffer.getvalue()

    def _readme(
        self,
        *,
        entity: Entity,
        container: EntityContainerVersion,
        export_manifest: dict[str, Any],
    ) -> str:
        return (
            "# TrustVault Regulator Evidence Pack\n\n"
            f"Entity: {entity.display_name} ({entity.external_id})\n\n"
            f"Export pack ID: {export_manifest['export_pack_id']}\n\n"
            f"Exported at: {export_manifest['exported_at']}\n\n"
            f"Source FITS container version: {container.version_number}\n\n"
            f"Source FITS SHA-256: {container.sha256}\n\n"
            "This export pack was generated from the current TrustVault FITS evidence container. "
            "The FITS file is included under source_fits/current_container.fits and remains the durable source of truth.\n"
        )

    def _serialise_export_pack(
        self,
        pack: ExportPack,
        entity: Entity | None,
        container: EntityContainerVersion | None,
    ) -> dict[str, Any]:
        return {
            "id": str(pack.id),
            "entity_id": str(pack.entity_id),
            "entity_external_id": entity.external_id if entity else None,
            "container_version_id": str(pack.container_version_id),
            "container_version_number": container.version_number if container else None,
            "export_type": pack.export_type,
            "status": pack.status,
            "storage_uri": pack.storage_uri,
            "sha256": pack.sha256,
            "size_bytes": pack.size_bytes,
            "evidence_object_count": pack.evidence_object_count,
            "manifest_json": pack.manifest_json,
            "created_by_job_id": str(pack.created_by_job_id) if pack.created_by_job_id else None,
            "created_by_user_id": pack.created_by_user_id,
            "created_at": pack.created_at,
        }

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

    def _read_container_bytes(self, container: EntityContainerVersion) -> bytes:
        parsed = parse_storage_uri(container.storage_uri)
        if parsed.provider != "local":
            raise ValueError(f"Export is not yet implemented for provider: {parsed.provider}")
        return self.storage.get_bytes(parsed.bucket, parsed.key)

    def _read_json_hdu(self, hdul: fits.HDUList, name: str) -> Any:
        hdu_by_name = {hdu.name: hdu for hdu in hdul}
        if name not in hdu_by_name:
            return None
        return json.loads(self._hdu_bytes(hdu_by_name[name]).decode("utf-8"))

    def _write_json(self, archive: zipfile.ZipFile, path: str, payload: Any) -> None:
        archive.writestr(path, json.dumps(payload, indent=2, sort_keys=True, default=str))

    def _hdu_bytes(self, hdu: fits.ImageHDU) -> bytes:
        if hdu.data is None:
            return b""
        return np.asarray(hdu.data, dtype=np.uint8).tobytes()
