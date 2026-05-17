import io
import json
import mimetypes
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.core.hashing import sha256_bytes
from trustvault.db.models import Entity, EvidenceObject, SourceSystem
from trustvault.settings import get_settings
from trustvault.storage.local import LocalFilesystemStorage


@dataclass(frozen=True)
class SourceFolderIngestionResult:
    entity_id: str
    entity_external_id: str
    entity_display_name: str
    evidence_object_count: int
    source_system_count: int
    skipped_count: int
    evidence_object_ids: list[str]


class SourceFolderIngestionService:
    """Ingests a customer evidence source folder ZIP.

    Expected shape mirrors the original Entity Evidence Container POC fixtures and the
    production-style sample folder:

    CUST-000001/
      metadata/customer.json
      metadata/audit_events.json
      documents/*.pdf
      documents/*.search.txt
      statements/*.pdf
      statements/*.search.txt
      emails/*.eml
      scans/*.jpg
      extracts/*.csv
      large_evidence/*.bin
    """

    IGNORED_PREFIXES = ("__MACOSX/",)

    def __init__(self, db: Session):
        self.db = db
        settings = get_settings()
        self.storage = LocalFilesystemStorage(settings.local_storage_root)

    def ingest_zip_bytes(self, zip_bytes: bytes, *, source_system_default: str = "source_folder") -> SourceFolderIngestionResult:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), mode="r") as archive:
            names = [name for name in archive.namelist() if self._include_zip_entry(name)]
            root = self._detect_root(names)
            customer = self._read_customer_metadata(archive, root)
            entity_external_id = customer.get("entity_id") or root.rstrip("/") or f"entity-{uuid.uuid4()}"
            entity_display_name = customer.get("display_name") or entity_external_id
            entity = self._get_or_create_entity(entity_external_id, entity_display_name, customer)

            search_text_by_stem = self._read_search_texts(archive, names)
            evidence_ids: list[str] = []
            skipped_count = 0
            source_systems: set[str] = set()

            for name in names:
                if name.endswith("/") or name.endswith(".search.txt"):
                    continue
                relative = self._relative_path(name, root)
                if relative.startswith("metadata/") and relative != "metadata/audit_events.json":
                    skipped_count += 1
                    continue

                content = archive.read(name)
                if not content:
                    skipped_count += 1
                    continue

                object_type = self._object_type_from_path(relative)
                category = self._category_from_path(relative, object_type)
                source_system = self._source_system_from_path(relative, customer, source_system_default)
                source_systems.add(source_system)
                content_type = mimetypes.guess_type(relative)[0] or "application/octet-stream"
                search_text = search_text_by_stem.get(self._search_key(name, root))
                metadata = {
                    "source_path": relative,
                    "category": category,
                    "document_type": object_type,
                    "source_folder_root": root.rstrip("/"),
                    "jurisdiction": customer.get("jurisdiction"),
                    "risk_rating": customer.get("risk_rating"),
                    "retention_class": "customer_evidence",
                    "legal_hold_status": "none",
                    "deletion_eligible": False,
                    "sensitivity": "confidential",
                }
                if search_text:
                    metadata.update(
                        {
                            "search_text": search_text,
                            "search_text_source": "sidecar_search_text",
                            "extraction_provider": "source_folder_sidecar",
                            "extraction_confidence": 1.0,
                        }
                    )
                if relative == "metadata/audit_events.json":
                    metadata["category"] = "audit"
                    metadata["document_type"] = "audit_events"
                    metadata["search_text"] = content.decode("utf-8", errors="replace")
                    metadata["search_text_source"] = "json_payload"

                evidence = self._store_evidence(
                    entity=entity,
                    content=content,
                    filename=PurePosixPath(relative).name,
                    object_type=object_type,
                    source_system=source_system,
                    content_type=content_type,
                    metadata=metadata,
                )
                evidence_ids.append(str(evidence.id))

            for source_system in sorted(source_systems):
                self._upsert_source_system(source_system)

            self.db.commit()
            return SourceFolderIngestionResult(
                entity_id=str(entity.id),
                entity_external_id=entity.external_id,
                entity_display_name=entity.display_name,
                evidence_object_count=len(evidence_ids),
                source_system_count=len(source_systems),
                skipped_count=skipped_count,
                evidence_object_ids=evidence_ids,
            )

    def _include_zip_entry(self, name: str) -> bool:
        if any(name.startswith(prefix) for prefix in self.IGNORED_PREFIXES):
            return False
        if "/._" in name or name.startswith("._"):
            return False
        return True

    def _detect_root(self, names: list[str]) -> str:
        first_parts = [name.split("/", 1)[0] for name in names if "/" in name]
        if not first_parts:
            return ""
        root = first_parts[0]
        return f"{root}/" if all(part == root for part in first_parts) else ""

    def _relative_path(self, name: str, root: str) -> str:
        return name[len(root) :] if root and name.startswith(root) else name

    def _read_customer_metadata(self, archive: zipfile.ZipFile, root: str) -> dict[str, Any]:
        path = f"{root}metadata/customer.json"
        try:
            return json.loads(archive.read(path).decode("utf-8"))
        except KeyError:
            return {}

    def _read_search_texts(self, archive: zipfile.ZipFile, names: list[str]) -> dict[str, str]:
        result: dict[str, str] = {}
        root = self._detect_root(names)
        for name in names:
            if not name.endswith(".search.txt"):
                continue
            result[self._search_key(name, root)] = archive.read(name).decode("utf-8", errors="replace")
        return result

    def _search_key(self, name: str, root: str) -> str:
        relative = self._relative_path(name, root)
        if relative.endswith(".search.txt"):
            relative = relative.removesuffix(".search.txt")
        path = PurePosixPath(relative)
        # Match sidecars like documents/passport_scan_certified.search.txt to
        # payloads like documents/passport_scan_certified.pdf.
        return str(path.with_suffix(""))

    def _object_type_from_path(self, relative: str) -> str:
        path = PurePosixPath(relative)
        stem = path.stem.lower().replace("-", "_").replace(" ", "_")
        if path.parent.name == "emails":
            return "email"
        if path.parent.name == "statements":
            return "statement"
        if path.parent.name == "extracts":
            return "structured_extract"
        if path.parent.name == "scans":
            return stem
        if path.parent.name == "large_evidence":
            return "bulk_archive_attachment"
        if path.parent.name == "metadata" and path.name == "audit_events.json":
            return "audit_events"
        return stem or "document"

    def _category_from_path(self, relative: str, object_type: str) -> str:
        first = PurePosixPath(relative).parts[0] if PurePosixPath(relative).parts else ""
        if first in {"documents", "scans"}:
            if "passport" in object_type:
                return "identity"
            if "address" in object_type:
                return "proof_of_address"
            if "wealth" in object_type:
                return "source_of_wealth"
            if "risk" in object_type or "cdd" in object_type:
                return "cdd_review"
            return "customer_documents"
        if first == "statements":
            return "statements"
        if first == "emails":
            return "communications"
        if first == "extracts":
            return "structured_extracts"
        if first == "metadata":
            return "audit"
        if first == "large_evidence":
            return "large_evidence"
        return "general_evidence"

    def _source_system_from_path(self, relative: str, customer: dict[str, Any], default: str) -> str:
        first = PurePosixPath(relative).parts[0] if PurePosixPath(relative).parts else ""
        mapping = {
            "documents": "Document Store",
            "scans": "Document Store",
            "emails": "Email Archive",
            "statements": "Statement Engine",
            "extracts": "Core Banking",
            "metadata": "TrustVault Import Metadata",
            "large_evidence": "Legacy Archive",
        }
        return mapping.get(first, default)

    def _get_or_create_entity(self, external_id: str, display_name: str, metadata: dict[str, Any]) -> Entity:
        entity = self.db.scalars(select(Entity).where(Entity.external_id == external_id)).first()
        if entity is not None:
            entity.display_name = display_name
            entity.entity_type = str(metadata.get("entity_type", "customer")).lower()
            entity.metadata_json = {**(entity.metadata_json or {}), **metadata}
            self.db.flush()
            return entity
        entity = Entity(
            external_id=external_id,
            display_name=display_name,
            entity_type=str(metadata.get("entity_type", "customer")).lower(),
            status="active",
            metadata_json=metadata,
        )
        self.db.add(entity)
        self.db.flush()
        return entity

    def _store_evidence(
        self,
        *,
        entity: Entity,
        content: bytes,
        filename: str,
        object_type: str,
        source_system: str,
        content_type: str,
        metadata: dict[str, Any],
    ) -> EvidenceObject:
        object_id = uuid.uuid4()
        key = f"{entity.external_id}/{object_id}/{filename}"
        stored = self.storage.put_bytes(
            bucket="source-imports",
            key=key,
            data=content,
            content_type=content_type,
        )
        evidence = EvidenceObject(
            id=object_id,
            entity_id=entity.id,
            object_type=object_type,
            source_system=source_system,
            storage_uri=stored.uri,
            sha256=sha256_bytes(content),
            content_type=content_type,
            metadata_json=metadata,
        )
        self.db.add(evidence)
        self.db.flush()
        return evidence

    def _upsert_source_system(self, name: str) -> None:
        existing = self.db.scalars(select(SourceSystem).where(SourceSystem.name == name)).first()
        if existing is None:
            self.db.add(SourceSystem(name=name, system_type="imported_source", status="active"))
