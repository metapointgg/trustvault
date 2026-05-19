import base64
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.core.document_classification import DocumentClassificationService
from trustvault.core.hashing import sha256_bytes
from trustvault.db.models import Entity, EvidenceObject
from trustvault.settings import get_settings
from trustvault.storage.local import LocalFilesystemStorage


@dataclass(frozen=True)
class EvidenceIngestionResult:
    entity_id: str
    entity_external_id: str
    evidence_object_id: str
    storage_uri: str
    sha256: str


class LocalEvidenceIngestionService:
    """Local/API ingestion service.

    Evidence metadata is normalised through the document classification service so
    direct uploads and source-folder uploads follow the same filename-driven
    document type -> category model.
    """

    def __init__(self, db: Session):
        self.db = db
        settings = get_settings()
        self.storage = LocalFilesystemStorage(settings.local_storage_root)
        self.classifier = DocumentClassificationService(db)

    def ingest_text_evidence(
        self,
        *,
        entity_external_id: str,
        entity_display_name: str,
        object_type: str,
        source_system: str,
        filename: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceIngestionResult:
        content = text.encode("utf-8")
        digest = sha256_bytes(content)
        entity = self._get_or_create_entity(entity_external_id, entity_display_name)
        object_id = uuid.uuid4()
        key = f"{entity.external_id}/{object_id}/{filename}"
        stored = self.storage.put_bytes(
            bucket="source-imports",
            key=key,
            data=content,
            content_type="text/plain",
        )
        classified_metadata = self.classifier.build_metadata(
            filename=filename,
            source_path=metadata.get("source_path") if metadata else None,
            existing_metadata=metadata,
        )
        classified_metadata.setdefault("search_text", text)
        classified_metadata.setdefault("search_text_source", "api_text")

        evidence = EvidenceObject(
            id=object_id,
            entity_id=entity.id,
            object_type=classified_metadata.get("document_type") or object_type,
            source_system=source_system,
            storage_uri=stored.uri,
            sha256=digest,
            content_type="text/plain",
            metadata_json=classified_metadata,
        )
        self.db.add(evidence)
        self.db.commit()
        self.db.refresh(evidence)

        return EvidenceIngestionResult(
            entity_id=str(entity.id),
            entity_external_id=entity.external_id,
            evidence_object_id=str(evidence.id),
            storage_uri=evidence.storage_uri,
            sha256=evidence.sha256,
        )

    def ingest_base64_evidence(
        self,
        *,
        entity_external_id: str,
        entity_display_name: str,
        object_type: str,
        source_system: str,
        filename: str,
        content_base64: str,
        content_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceIngestionResult:
        content = base64.b64decode(content_base64)
        digest = sha256_bytes(content)
        entity = self._get_or_create_entity(entity_external_id, entity_display_name)
        object_id = uuid.uuid4()
        key = f"{entity.external_id}/{object_id}/{filename}"
        stored = self.storage.put_bytes(
            bucket="source-imports",
            key=key,
            data=content,
            content_type=content_type,
        )
        classified_metadata = self.classifier.build_metadata(
            filename=filename,
            source_path=metadata.get("source_path") if metadata else None,
            existing_metadata=metadata,
        )

        evidence = EvidenceObject(
            id=object_id,
            entity_id=entity.id,
            object_type=classified_metadata.get("document_type") or object_type,
            source_system=source_system,
            storage_uri=stored.uri,
            sha256=digest,
            content_type=content_type,
            metadata_json=classified_metadata,
        )
        self.db.add(evidence)
        self.db.commit()
        self.db.refresh(evidence)

        return EvidenceIngestionResult(
            entity_id=str(entity.id),
            entity_external_id=entity.external_id,
            evidence_object_id=str(evidence.id),
            storage_uri=evidence.storage_uri,
            sha256=evidence.sha256,
        )

    def _get_or_create_entity(self, external_id: str, display_name: str) -> Entity:
        entity = self.db.scalars(select(Entity).where(Entity.external_id == external_id)).first()
        if entity is not None:
            if entity.display_name != display_name:
                entity.display_name = display_name
                self.db.commit()
                self.db.refresh(entity)
            return entity

        entity = Entity(
            external_id=external_id,
            display_name=display_name,
            entity_type="customer",
            status="active",
            metadata_json={},
        )
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity
