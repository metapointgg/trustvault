import io
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import numpy as np
from astropy.io import fits
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from trustvault.core.hashing import sha256_bytes
from trustvault.core.storage_uri import parse_storage_uri
from trustvault.db.models import Entity, EntityContainerVersion, EvidenceObject
from trustvault.settings import get_settings
from trustvault.storage.local import LocalFilesystemStorage


def _json_hdu(name: str, value: Any) -> fits.ImageHDU:
    data = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str).encode("utf-8")
    arr = np.frombuffer(data, dtype=np.uint8)
    hdu = fits.ImageHDU(data=arr, name=name)
    hdu.header["MIMETYPE"] = "application/json"
    hdu.header["ENCODING"] = "utf-8"
    hdu.header["SHA256"] = sha256_bytes(data)
    return hdu


def _payload_hdu(name: str, data: bytes, evidence: EvidenceObject, filename: str) -> fits.ImageHDU:
    arr = np.frombuffer(data, dtype=np.uint8)
    hdu = fits.ImageHDU(data=arr, name=name)
    hdu.header["OBJID"] = str(evidence.id)[:68]
    hdu.header["MIMETYPE"] = (evidence.content_type or "application/octet-stream")[:68]
    hdu.header["SHA256"] = evidence.sha256
    hdu.header["SIZE"] = len(data)
    hdu.header["FILENAME"] = filename[:68]
    hdu.header["SOURCE"] = evidence.source_system[:68]
    hdu.header["OBJTYPE"] = evidence.object_type[:68]
    hdu.header["SNAPSHOT"] = "ENTITY_ARCHIVE"
    return hdu


class EntityContainerBuilder:
    """Builds a TrustVault FITS evidence container for one entity.

    This follows the Entity Evidence Container Demo pattern: a FITS primary HDU,
    JSON metadata HDUs and uint8 payload HDUs containing the preserved original
    evidence bytes. FITS remains the durable source of truth; database/index state
    is rebuildable from the container.
    """

    def __init__(self, db: Session):
        self.db = db
        settings = get_settings()
        self.storage = LocalFilesystemStorage(settings.local_storage_root)

    def rebuild(self, entity_id_or_external_id: str, created_by_job_id: str | None = None) -> dict[str, Any]:
        entity = self._get_entity(entity_id_or_external_id)
        evidence_objects = self.db.scalars(
            select(EvidenceObject)
            .where(EvidenceObject.entity_id == entity.id)
            .order_by(EvidenceObject.created_at.asc())
        ).all()

        version_number = self._next_version_number(entity.id)
        container_id = str(uuid.uuid4())
        built_at = datetime.now(timezone.utc).isoformat()

        evidence_payloads = [
            (evidence, self._read_evidence_bytes(evidence), self._evidence_filename(evidence))
            for evidence in evidence_objects
        ]
        manifest = self._build_manifest(
            entity=entity,
            evidence_payloads=evidence_payloads,
            version_number=version_number,
            container_id=container_id,
            built_at=built_at,
        )
        hash_report = self._build_hash_report(evidence_payloads)
        summary = self._build_summary(entity, evidence_payloads, version_number, container_id, built_at)
        container_bytes = self._build_fits_container(
            entity=entity,
            manifest=manifest,
            hash_report=hash_report,
            summary=summary,
            evidence_payloads=evidence_payloads,
            version_number=version_number,
            container_id=container_id,
            built_at=built_at,
        )
        container_hash = sha256_bytes(container_bytes)

        key = f"{entity.external_id}/v{version_number:06d}/{entity.external_id}.fits"
        stored = self.storage.put_bytes(
            bucket="fits-containers",
            key=key,
            data=container_bytes,
            content_type="application/fits",
        )

        self.db.execute(
            update(EntityContainerVersion)
            .where(EntityContainerVersion.entity_id == entity.id)
            .values(status="superseded")
        )

        version = EntityContainerVersion(
            entity_id=entity.id,
            version_number=version_number,
            status="current",
            storage_uri=stored.uri,
            sha256=container_hash,
            size_bytes=len(container_bytes),
            evidence_object_count=len(evidence_objects),
            manifest_json=manifest,
            hash_report_json=hash_report,
            created_by_job_id=uuid.UUID(created_by_job_id) if created_by_job_id else None,
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)

        return {
            "container_version_id": str(version.id),
            "entity_id": str(entity.id),
            "entity_external_id": entity.external_id,
            "version_number": version.version_number,
            "status": version.status,
            "storage_uri": version.storage_uri,
            "sha256": version.sha256,
            "size_bytes": version.size_bytes,
            "evidence_object_count": version.evidence_object_count,
            "container_format": "FITS",
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

    def _next_version_number(self, entity_id: uuid.UUID) -> int:
        latest = self.db.scalar(
            select(func.max(EntityContainerVersion.version_number)).where(
                EntityContainerVersion.entity_id == entity_id
            )
        )
        return int(latest or 0) + 1

    def _build_manifest(
        self,
        *,
        entity: Entity,
        evidence_payloads: list[tuple[EvidenceObject, bytes, str]],
        version_number: int,
        container_id: str,
        built_at: str,
    ) -> dict[str, Any]:
        return {
            "product": "TrustVault",
            "container_format": "FITS",
            "container_model": "FITS with JSON metadata HDUs and uint8 payload HDUs",
            "container_id": container_id,
            "snapshot_id": "ENTITY_ARCHIVE",
            "snapshot_type": "Full Entity Archive",
            "version_number": version_number,
            "built_at": built_at,
            "source_of_truth": "FITS container payload HDUs and recorded SHA-256 hashes",
            "entity": {
                "id": str(entity.id),
                "external_id": entity.external_id,
                "display_name": entity.display_name,
                "entity_type": entity.entity_type,
                "status": entity.status,
                "metadata": entity.metadata_json,
            },
            "evidence_objects": [
                {
                    "id": str(evidence.id),
                    "object_type": evidence.object_type,
                    "source_system": evidence.source_system,
                    "storage_uri": evidence.storage_uri,
                    "sha256": evidence.sha256,
                    "content_type": evidence.content_type,
                    "metadata": evidence.metadata_json,
                    "created_at": evidence.created_at.isoformat() if evidence.created_at else None,
                    "hdu_name": f"PAYLOAD_{index:06d}",
                    "filename": filename,
                    "size_bytes": len(data),
                }
                for index, (evidence, data, filename) in enumerate(evidence_payloads, start=1)
            ],
        }

    def _build_hash_report(
        self, evidence_payloads: list[tuple[EvidenceObject, bytes, str]]
    ) -> dict[str, Any]:
        return {
            "algorithm": "SHA-256",
            "evidence_count": len(evidence_payloads),
            "objects": [
                {
                    "evidence_object_id": str(evidence.id),
                    "storage_uri": evidence.storage_uri,
                    "sha256": evidence.sha256,
                    "actual_sha256_at_build": sha256_bytes(data),
                    "hash_matches": evidence.sha256 == sha256_bytes(data),
                    "hdu_name": f"PAYLOAD_{index:06d}",
                    "filename": filename,
                    "size_bytes": len(data),
                }
                for index, (evidence, data, filename) in enumerate(evidence_payloads, start=1)
            ],
        }

    def _build_summary(
        self,
        entity: Entity,
        evidence_payloads: list[tuple[EvidenceObject, bytes, str]],
        version_number: int,
        container_id: str,
        built_at: str,
    ) -> dict[str, Any]:
        return {
            "entity_id": str(entity.id),
            "entity_external_id": entity.external_id,
            "display_name": entity.display_name,
            "payload_count": len(evidence_payloads),
            "total_payload_bytes": sum(len(data) for _, data, _ in evidence_payloads),
            "created_at": built_at,
            "container_id": container_id,
            "container_format": "FITS",
            "container_model": "FITS with JSON metadata HDUs and uint8 payload HDUs",
            "snapshot_id": "ENTITY_ARCHIVE",
            "snapshot_type": "Full Entity Archive",
            "container_version": version_number,
            "container_scope": "entity",
        }

    def _build_fits_container(
        self,
        *,
        entity: Entity,
        manifest: dict[str, Any],
        hash_report: dict[str, Any],
        summary: dict[str, Any],
        evidence_payloads: list[tuple[EvidenceObject, bytes, str]],
        version_number: int,
        container_id: str,
        built_at: str,
    ) -> bytes:
        primary = fits.PrimaryHDU()
        primary.header["TVVER"] = "0.1"
        primary.header["EECVER"] = "0.3"
        primary.header["ENTITY"] = entity.external_id[:68]
        primary.header["ENTUUID"] = str(entity.id)[:68]
        primary.header["ETYPE"] = entity.entity_type[:68]
        primary.header["NAME"] = entity.display_name[:68]
        primary.header["CREATED"] = built_at[:68]
        primary.header["SNAPSHOT"] = "ENTITY_ARCHIVE"
        primary.header["SNAPTYPE"] = "Full Entity Archive"
        primary.header["VERSION"] = int(version_number)
        primary.header["MODEL"] = "ENTITY_SINGLE"
        primary.header["PURPOSE"] = "TrustVault entity evidence preservation container"
        primary.header["CONTAINER"] = container_id[:68]

        provenance = [
            {
                "event_id": f"PROV-{entity.external_id}-ENTITY_ARCHIVE-{version_number:06d}",
                "entity_id": str(entity.id),
                "entity_external_id": entity.external_id,
                "event_type": "CONTAINER_CREATED",
                "source_system": "TrustVault",
                "actor": "system",
                "timestamp": built_at,
                "details": "Created FITS evidence container from preserved TrustVault evidence objects",
            }
        ]
        snapshots = [
            {
                "snapshot_id": "ENTITY_ARCHIVE",
                "snapshot_type": "Full Entity Archive",
                "object_count": len(evidence_payloads),
                "payload_bytes": sum(len(data) for _, data, _ in evidence_payloads),
            }
        ]
        ocr_text = [
            {
                "object_id": str(evidence.id),
                "filename": filename,
                "extracted_text": data.decode("utf-8", errors="replace") if (evidence.content_type or "").startswith("text/") else "",
                "extraction_method": "direct_text" if (evidence.content_type or "").startswith("text/") else "none",
                "extraction_confidence": 1.0 if (evidence.content_type or "").startswith("text/") else 0.0,
                "extracted_at": built_at,
                "character_count": len(data.decode("utf-8", errors="replace")) if (evidence.content_type or "").startswith("text/") else 0,
            }
            for evidence, data, filename in evidence_payloads
        ]

        hdus: list[fits.hdu.base.ExtensionHDU] = [
            _json_hdu("ENTITY_METADATA", manifest["entity"]),
            _json_hdu("SUMMARY", summary),
            _json_hdu("SNAPSHOTS", snapshots),
            _json_hdu("MANIFEST", manifest["evidence_objects"]),
            _json_hdu("PROVENANCE", provenance),
            _json_hdu("OCR_TEXT", ocr_text),
            _json_hdu("EXTRACTED_FIELDS", []),
            _json_hdu("EXTRACTION_EVENTS", []),
            _json_hdu("HASH_REPORT", hash_report),
            _json_hdu("CONTAINER_MANIFEST", manifest),
        ]

        for index, (evidence, data, filename) in enumerate(evidence_payloads, start=1):
            hdus.append(_payload_hdu(f"PAYLOAD_{index:06d}", data, evidence, filename))

        buffer = io.BytesIO()
        fits.HDUList([primary] + hdus).writeto(buffer, overwrite=True, checksum=True)
        return buffer.getvalue()

    def _read_evidence_bytes(self, evidence: EvidenceObject) -> bytes:
        parsed = parse_storage_uri(evidence.storage_uri)
        if parsed.provider != "local":
            raise ValueError(f"Container build is not yet implemented for provider: {parsed.provider}")
        return self.storage.get_bytes(parsed.bucket, parsed.key)

    def _evidence_filename(self, evidence: EvidenceObject) -> str:
        parsed = parse_storage_uri(evidence.storage_uri)
        return parsed.key.split("/")[-1]
