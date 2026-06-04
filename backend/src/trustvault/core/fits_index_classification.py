from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.core.evidence_classifier import EvidenceClassifier
from trustvault.db.models import Entity, FitsIndexEntry


class FitsIndexClassificationService:
    """Apply industry-pack evidence classification to FITS index rows.

    Source-folder ingestion now classifies evidence before it is stored. This
    service is a rebuild-time safety net for FITS index entries created from
    older containers or from containers whose manifest metadata is not yet
    canonical.
    """

    CLASSIFICATION_FIELDS = {
        "category",
        "document_type",
        "classification_status",
        "classification_confidence",
        "classification_matched_alias",
        "classification_source",
        "industry_pack",
    }

    def __init__(self, db: Session):
        self.db = db
        self.classifier = EvidenceClassifier(db)

    def classify_index_entries(self, *, entity_id: Any | None = None, limit: int | None = None) -> dict[str, Any]:
        statement = select(FitsIndexEntry, Entity).join(Entity, FitsIndexEntry.entity_id == Entity.id)
        if entity_id is not None:
            statement = statement.where(FitsIndexEntry.entity_id == entity_id)
        statement = statement.order_by(FitsIndexEntry.created_at.desc())
        if limit is not None:
            statement = statement.limit(limit)

        inspected_count = 0
        updated_count = 0
        classified_count = 0
        skipped_count = 0
        updates: list[dict[str, Any]] = []

        for index_entry, entity in self.db.execute(statement).all():
            inspected_count += 1
            before = self._snapshot(index_entry)
            metadata = self._metadata_for_classification(index_entry, entity)
            classification = self.classifier.classify(
                filename=index_entry.filename,
                object_type=index_entry.object_type or metadata.get("document_type") or metadata.get("object_type"),
                source_system=index_entry.source_system,
                text_content=index_entry.text_content,
                metadata=metadata,
                entity=entity,
            )
            if classification is None:
                skipped_count += 1
                continue

            classified_count += 1
            classification_metadata = classification.to_metadata()
            next_metadata = dict(index_entry.metadata_json or {})
            nested_metadata = dict(next_metadata.get("metadata") or {})
            nested_metadata.update(classification_metadata)
            next_metadata.update(classification_metadata)
            next_metadata["metadata"] = nested_metadata

            next_object_type = classification.document_type or index_entry.object_type
            changed = index_entry.object_type != next_object_type or any(
                (index_entry.metadata_json or {}).get(key) != value for key, value in classification_metadata.items()
            )
            if not changed:
                continue

            index_entry.object_type = next_object_type
            index_entry.metadata_json = next_metadata
            updated_count += 1
            if len(updates) < 25:
                updates.append(
                    {
                        "entity_external_id": entity.external_id,
                        "fits_index_entry_id": str(index_entry.id),
                        "evidence_object_id": index_entry.evidence_object_id,
                        "filename": index_entry.filename,
                        "before": before,
                        "after": self._snapshot(index_entry),
                    }
                )

        self.db.flush()
        return {
            "inspected_count": inspected_count,
            "classified_count": classified_count,
            "updated_count": updated_count,
            "skipped_count": skipped_count,
            "updates": updates,
            "truncated_updates": max(updated_count - len(updates), 0),
        }

    def _metadata_for_classification(self, index_entry: FitsIndexEntry, entity: Entity) -> dict[str, Any]:
        metadata = dict(index_entry.metadata_json or {})
        nested_metadata = metadata.get("metadata") if isinstance(metadata.get("metadata"), dict) else {}
        entity_metadata = entity.metadata_json if isinstance(entity.metadata_json, dict) else {}
        combined = {
            **nested_metadata,
            **metadata,
            "filename": index_entry.filename,
            "object_type": index_entry.object_type,
            "source_system": index_entry.source_system,
            "text_content": index_entry.text_content,
            "entity_external_id": entity.external_id,
            "entity_type": entity.entity_type,
            "entity_display_name": entity.display_name,
            "entity_metadata": entity_metadata,
        }
        for key in (
            "industry_pack",
            "industry",
            "demo_archive_key",
            "department",
            "responsible_person",
            "supplier_category",
            "criticality",
            "risk_rating",
            "jurisdiction",
        ):
            if combined.get(key) is None and entity_metadata.get(key) is not None:
                combined[key] = entity_metadata.get(key)
        return combined

    def _snapshot(self, index_entry: FitsIndexEntry) -> dict[str, Any]:
        metadata = index_entry.metadata_json or {}
        nested_metadata = metadata.get("metadata") if isinstance(metadata.get("metadata"), dict) else {}
        return {
            "object_type": index_entry.object_type,
            "category": metadata.get("category") or nested_metadata.get("category"),
            "document_type": metadata.get("document_type") or nested_metadata.get("document_type"),
            "classification_status": metadata.get("classification_status") or nested_metadata.get("classification_status"),
            "classification_source": metadata.get("classification_source") or nested_metadata.get("classification_source"),
            "industry_pack": metadata.get("industry_pack") or nested_metadata.get("industry_pack"),
        }
