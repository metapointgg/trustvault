#!/usr/bin/env python3
"""Reclassify existing TrustVault evidence metadata using industry pack vocabulary.

Examples:
  python scripts/reclassify_evidence_metadata.py --dry-run --limit 20
  python scripts/reclassify_evidence_metadata.py --industry healthcare --apply
  python scripts/reclassify_evidence_metadata.py --all --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "backend" / "src", ROOT / "src", Path("/app/src")):
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from sqlalchemy import select  # noqa: E402

from trustvault.core.evidence_classifier import EvidenceClassifier  # noqa: E402
from trustvault.db.models import Entity, EvidenceObject, FitsIndexEntry  # noqa: E402
from trustvault.db.session import SessionLocal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Reclassify TrustVault evidence metadata from industry pack vocabulary")
    parser.add_argument("--industry", default="", help="Restrict to an industry key, e.g. healthcare or supplier_due_diligence")
    parser.add_argument("--entity", default="", help="Restrict to one entity external ID")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of FITS index entries to inspect")
    parser.add_argument("--apply", action="store_true", help="Write metadata changes to the database")
    parser.add_argument("--all", action="store_true", help="Inspect all industries; otherwise active/entity industry is used")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        classifier = EvidenceClassifier(db)
        entity_by_id = {entity.id: entity for entity in db.scalars(select(Entity)).all()}
        evidence_by_id = {str(item.id): item for item in db.scalars(select(EvidenceObject)).all()}
        entries = db.scalars(select(FitsIndexEntry).order_by(FitsIndexEntry.created_at.desc())).all()
        if args.entity:
            entries = [entry for entry in entries if entity_by_id.get(entry.entity_id) and entity_by_id[entry.entity_id].external_id == args.entity]
        if args.industry and not args.all:
            entries = [entry for entry in entries if _entity_industry(entity_by_id.get(entry.entity_id)) == _normalise_industry(args.industry)]
        if args.limit:
            entries = entries[: args.limit]

        updates: list[dict[str, Any]] = []
        for entry in entries:
            entity = entity_by_id.get(entry.entity_id)
            metadata = dict(entry.metadata_json or {})
            nested = dict(metadata.get("metadata") or {}) if isinstance(metadata.get("metadata"), dict) else {}
            industry = _normalise_industry(args.industry) if args.industry else _entity_industry(entity)
            classification = classifier.classify(
                filename=entry.filename or nested.get("filename") or metadata.get("filename"),
                object_type=entry.object_type or nested.get("object_type") or metadata.get("object_type"),
                source_system=entry.source_system or nested.get("source_system") or metadata.get("source_system"),
                text_content=entry.text_content or nested.get("search_text") or metadata.get("search_text"),
                metadata={**nested, **metadata},
                entity=entity,
                industry_key=industry,
            )
            if classification is None:
                continue
            classified = classification.to_metadata()
            before = {
                "category": metadata.get("category") or nested.get("category"),
                "document_type": metadata.get("document_type") or nested.get("document_type"),
                "classification_status": metadata.get("classification_status") or nested.get("classification_status"),
                "industry_pack": metadata.get("industry_pack") or nested.get("industry_pack"),
            }
            after = {**before, **classified}
            if _same(before, after):
                continue
            updates.append({
                "entity_external_id": entity.external_id if entity else None,
                "evidence_object_id": entry.evidence_object_id,
                "filename": entry.filename,
                "before": before,
                "after": after,
            })
            if args.apply:
                _apply_entry_metadata(entry, classified)
                if entry.evidence_object_id and entry.evidence_object_id in evidence_by_id:
                    _apply_evidence_metadata(evidence_by_id[entry.evidence_object_id], classified)

        if args.apply:
            db.commit()
        print(json.dumps({
            "applied": args.apply,
            "inspected_count": len(entries),
            "update_count": len(updates),
            "updates": updates[:100],
            "truncated_updates": max(len(updates) - 100, 0),
        }, indent=2, default=str))
        return 0
    finally:
        db.close()


def _apply_entry_metadata(entry: FitsIndexEntry, classified: dict[str, Any]) -> None:
    metadata = dict(entry.metadata_json or {})
    nested = dict(metadata.get("metadata") or {}) if isinstance(metadata.get("metadata"), dict) else {}
    nested.update(classified)
    metadata.update(classified)
    metadata["metadata"] = nested
    entry.metadata_json = metadata


def _apply_evidence_metadata(evidence: EvidenceObject, classified: dict[str, Any]) -> None:
    metadata = dict(evidence.metadata_json or {})
    metadata.update(classified)
    evidence.metadata_json = metadata
    if classified.get("document_type"):
        evidence.object_type = str(classified["document_type"])


def _same(before: dict[str, Any], after: dict[str, Any]) -> bool:
    return all(str(before.get(key) or "") == str(after.get(key) or "") for key in ("category", "document_type", "classification_status", "industry_pack"))


def _entity_industry(entity: Entity | None) -> str:
    metadata = entity.metadata_json if entity is not None and isinstance(entity.metadata_json, dict) else {}
    return _normalise_industry(metadata.get("industry_pack") or metadata.get("industry") or metadata.get("demo_archive_key") or "financial_services")


def _normalise_industry(value: Any) -> str:
    return str(value or "financial_services").strip().lower().replace("-", "_")


if __name__ == "__main__":
    raise SystemExit(main())
