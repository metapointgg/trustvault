import io
import json
import mimetypes
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.core.document_classification import DocumentClassificationService
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
    duplicate_count: int = 0
    duplicate_items: list[dict[str, Any]] = field(default_factory=list)
    assurance_gaps: list[dict[str, Any]] = field(default_factory=list)


class SourceFolderIngestionService:
    """Ingests a customer evidence source folder ZIP.

    Ingestion is idempotent by source path/SHA and by evidence payload SHA for a
    given entity. Re-running the same source folder, or dropping the same evidence
    under a different file name, skips unchanged evidence rather than appending
    duplicate records and creating a larger FITS archive.

    Folder names are retained as provenance, but document classification now uses
    filename-driven document type mappings configured in Settings.
    """

    IGNORED_PREFIXES = ("__MACOSX/",)

    def __init__(self, db: Session):
        self.db = db
        settings = get_settings()
        self.storage = LocalFilesystemStorage(settings.local_storage_root)
        self.classifier = DocumentClassificationService(db)

    def ingest_zip_bytes(self, zip_bytes: bytes, *, source_system_default: str = "source_folder") -> SourceFolderIngestionResult:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), mode="r") as archive:
            names = [name for name in archive.namelist() if self._include_zip_entry(name)]
            root = self._detect_root(names)
            customer = self._read_customer_metadata(archive, root)
            metadata_missing = not bool(customer)
            entity_external_id = customer.get("entity_id") or root.rstrip("/") or f"entity-{uuid.uuid4()}"
            entity_display_name = customer.get("display_name") or entity_external_id
            assurance_gaps = self._customer_assurance_gaps(metadata_missing, customer)
            entity = self._get_or_create_entity(entity_external_id, entity_display_name, customer, assurance_gaps)
            existing_source_hashes, existing_content_hashes = self._existing_evidence_fingerprints(entity)

            search_text_by_stem = self._read_search_texts(archive, names)
            evidence_ids: list[str] = []
            skipped_count = 0
            duplicate_count = 0
            duplicate_items: list[dict[str, Any]] = []
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

                content_hash = sha256_bytes(content)
                source_key = (relative, content_hash)
                if source_key in existing_source_hashes:
                    duplicate_count += 1
                    skipped_count += 1
                    duplicate_items.append(
                        {
                            "source_path": relative,
                            "sha256": content_hash,
                            "reason": "same_source_path_and_payload_already_ingested",
                        }
                    )
                    continue
                if content_hash in existing_content_hashes:
                    duplicate_count += 1
                    skipped_count += 1
                    duplicate_items.append(
                        {
                            "source_path": relative,
                            "sha256": content_hash,
                            "reason": "same_payload_already_ingested_for_entity",
                        }
                    )
                    continue

                filename = PurePosixPath(relative).name
                object_type = self._object_type_from_path(relative)
                source_system = self._source_system_from_path(relative, customer, source_system_default)
                source_systems.add(source_system)
                content_type = mimetypes.guess_type(relative)[0] or "application/octet-stream"
                search_text = search_text_by_stem.get(self._search_key(name, root))
                metadata = self.classifier.build_metadata(
                    filename=filename,
                    source_path=relative,
                    existing_metadata={
                        "source_path": relative,
                        "source_folder_root": root.rstrip("/"),
                        "folder_category_hint": self._legacy_category_from_path(relative, object_type),
                        "jurisdiction": customer.get("jurisdiction"),
                        "risk_rating": customer.get("risk_rating"),
                        "retention_class": "customer_evidence",
                        "legal_hold_status": "none",
                        "deletion_eligible": False,
                        "sensitivity": "confidential",
                    },
                )
                if metadata.get("category"):
                    metadata["retention_class"] = metadata["category"]
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
                    metadata["category"] = "Audit"
                    metadata["document_type"] = "Audit Events"
                    metadata["classification_status"] = "classified"
                    metadata["classification_source"] = "system_metadata"
                    metadata["classification_confidence"] = 1.0
                    metadata["retention_class"] = "Audit"
                    metadata["search_text"] = content.decode("utf-8", errors="replace")
                    metadata["search_text_source"] = "json_payload"

                evidence = self._store_evidence(
                    entity=entity,
                    content=content,
                    content_hash=content_hash,
                    filename=filename,
                    object_type=metadata.get("document_type") or object_type,
                    source_system=source_system,
                    content_type=content_type,
                    metadata=metadata,
                )
                evidence_ids.append(str(evidence.id))
                existing_source_hashes.add(source_key)
                existing_content_hashes.add(content_hash)

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
                duplicate_count=duplicate_count,
                duplicate_items=duplicate_items,
                evidence_object_ids=evidence_ids,
                assurance_gaps=assurance_gaps,
            )

    def _existing_evidence_fingerprints(self, entity: Entity) -> tuple[set[tuple[str, str]], set[str]]:
        rows = self.db.scalars(select(EvidenceObject).where(EvidenceObject.entity_id == entity.id)).all()
        source_hashes: set[tuple[str, str]] = set()
        content_hashes: set[str] = set()
        for row in rows:
            if row.sha256:
                content_hashes.add(row.sha256)
            source_path = (row.metadata_json or {}).get("source_path")
            if source_path and row.sha256:
                source_hashes.add((source_path, row.sha256))
        return source_hashes, content_hashes

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
        candidate_paths = [f"{root}metadata/customer.json", f"{root}customer.json"]
        for path in candidate_paths:
            try:
                return json.loads(archive.read(path).decode("utf-8"))
            except KeyError:
                continue
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

    def _legacy_category_from_path(self, relative: str, object_type: str) -> str:
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

    def _customer_assurance_gaps(self, metadata_missing: bool, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        gaps: list[dict[str, Any]] = []
        required_fields = ["display_name", "entity_type", "jurisdiction", "risk_rating"]
        missing_fields = required_fields if metadata_missing else [field for field in required_fields if not metadata.get(field)]
        if missing_fields:
            gaps.append(
                {
                    "gap_key": "customer_information_missing",
                    "title": "Customer Information assurance gap",
                    "status": "open",
                    "severity": "medium",
                    "missing_fields": missing_fields,
                    "description": "Customer metadata was not supplied or is incomplete. Complete the customer information manually to resolve this assurance gap.",
                }
            )
        return gaps

    def _get_or_create_entity(self, external_id: str, display_name: str, metadata: dict[str, Any], assurance_gaps: list[dict[str, Any]]) -> Entity:
        entity_metadata = dict(metadata)
        entity_metadata["customer_information_status"] = "incomplete" if assurance_gaps else "complete"
        entity_metadata["assurance_gaps"] = assurance_gaps
        entity_metadata["customer_json_supplied"] = bool(metadata)

        entity = self.db.scalars(select(Entity).where(Entity.external_id == external_id)).first()
        if entity is not None:
            entity.display_name = display_name
            entity.entity_type = str(metadata.get("entity_type", entity.entity_type or "customer")).lower()
            existing = entity.metadata_json or {}
            existing_gaps = existing.get("assurance_gaps") if isinstance(existing.get("assurance_gaps"), list) else []
            unresolved_existing = [gap for gap in existing_gaps if gap.get("status") != "resolved" and gap.get("gap_key") != "customer_information_missing"]
            entity.metadata_json = {**existing, **entity_metadata, "assurance_gaps": [*unresolved_existing, *assurance_gaps]}
            self.db.flush()
            return entity
        entity = Entity(
            external_id=external_id,
            display_name=display_name,
            entity_type=str(metadata.get("entity_type", "customer")).lower(),
            status="active",
            metadata_json=entity_metadata,
        )
        self.db.add(entity)
        self.db.flush()
        return entity

    def _store_evidence(
        self,
        *,
        entity: Entity,
        content: bytes,
        content_hash: str,
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
            sha256=content_hash,
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
