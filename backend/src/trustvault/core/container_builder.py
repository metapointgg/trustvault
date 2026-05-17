import io
import json
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from trustvault.core.hashing import sha256_bytes
from trustvault.core.storage_uri import parse_storage_uri
from trustvault.db.models import Entity, EntityContainerVersion, EvidenceObject
from trustvault.settings import get_settings
from trustvault.storage.local import LocalFilesystemStorage


class EntityContainerBuilder:
    """Builds a deterministic TrustVault archive container for one entity.

    This is the first production container implementation. It is intentionally a
    regulator-readable archive containing manifest, hash report and originals. The
    FITS-specific container writer can later replace the ZIP serialisation behind
    this service boundary without changing API or worker behaviour.
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

        manifest = self._build_manifest(
            entity=entity,
            evidence_objects=evidence_objects,
            version_number=version_number,
            container_id=container_id,
            built_at=built_at,
        )
        hash_report = self._build_hash_report(evidence_objects)
        container_bytes = self._build_zip_container(manifest, hash_report, evidence_objects)
        container_hash = sha256_bytes(container_bytes)

        key = f"{entity.external_id}/v{version_number:06d}/trustvault-container.zip"
        stored = self.storage.put_bytes(
            bucket="entity-containers",
            key=key,
            data=container_bytes,
            content_type="application/zip",
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
        evidence_objects: list[EvidenceObject],
        version_number: int,
        container_id: str,
        built_at: str,
    ) -> dict[str, Any]:
        return {
            "product": "TrustVault",
            "container_format": "trustvault-archive-v1",
            "container_id": container_id,
            "version_number": version_number,
            "built_at": built_at,
            "source_of_truth": "preserved original evidence files and manifest hashes",
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
                    "container_path": self._evidence_container_path(evidence),
                }
                for evidence in evidence_objects
            ],
        }

    def _build_hash_report(self, evidence_objects: list[EvidenceObject]) -> dict[str, Any]:
        return {
            "algorithm": "SHA-256",
            "evidence_count": len(evidence_objects),
            "objects": [
                {
                    "evidence_object_id": str(evidence.id),
                    "storage_uri": evidence.storage_uri,
                    "sha256": evidence.sha256,
                    "container_path": self._evidence_container_path(evidence),
                }
                for evidence in evidence_objects
            ],
        }

    def _build_zip_container(
        self,
        manifest: dict[str, Any],
        hash_report: dict[str, Any],
        evidence_objects: list[EvidenceObject],
    ) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            self._write_json(archive, "MANIFEST.json", manifest)
            self._write_json(archive, "HASH_REPORT.json", hash_report)
            archive.writestr(
                "README.md",
                "# TrustVault Evidence Container\n\n"
                "This archive contains preserved evidence files, manifest metadata and hash reports.\n"
                "The original evidence and recorded hashes remain the source of truth.\n",
            )
            for evidence in evidence_objects:
                data = self._read_evidence_bytes(evidence)
                archive.writestr(self._evidence_container_path(evidence), data)
        return buffer.getvalue()

    def _write_json(self, archive: zipfile.ZipFile, path: str, payload: dict[str, Any]) -> None:
        archive.writestr(path, json.dumps(payload, indent=2, sort_keys=True, default=str))

    def _read_evidence_bytes(self, evidence: EvidenceObject) -> bytes:
        parsed = parse_storage_uri(evidence.storage_uri)
        if parsed.provider != "local":
            raise ValueError(f"Container build is not yet implemented for provider: {parsed.provider}")
        return self.storage.get_bytes(parsed.bucket, parsed.key)

    def _evidence_container_path(self, evidence: EvidenceObject) -> str:
        parsed = parse_storage_uri(evidence.storage_uri)
        filename = parsed.key.split("/")[-1]
        return f"files/{evidence.source_system}/{evidence.object_type}/{evidence.id}/{filename}"
