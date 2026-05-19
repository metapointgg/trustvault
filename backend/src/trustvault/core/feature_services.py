from __future__ import annotations

import io
import json
import uuid
from typing import Any

import numpy as np
from astropy.io import fits
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trustvault.core.storage_uri import parse_storage_uri
from trustvault.db.models import (
    AuditEvent,
    CompletenessResult,
    CompletenessRun,
    Entity,
    EntityContainerVersion,
    EvidenceObject,
    FitsIndexEntry,
    Job,
    Ruleset,
    RulesetRule,
    SourceSystem,
)
from trustvault.settings import get_settings
from trustvault.storage.local import LocalFilesystemStorage


class TrustVaultFeatureService:
    """Production feature facade over FITS-native TrustVault state."""

    def __init__(self, db: Session):
        self.db = db
        self.storage = LocalFilesystemStorage(get_settings().local_storage_root)

    def dashboard(self) -> dict[str, Any]:
        entity_count = self.db.scalar(select(func.count()).select_from(Entity)) or 0
        evidence_count = self.db.scalar(select(func.count()).select_from(EvidenceObject)) or 0
        current_fits = self.db.scalar(
            select(func.count())
            .select_from(EntityContainerVersion)
            .where(EntityContainerVersion.status == "current")
            .where(EntityContainerVersion.storage_uri.ilike("%.fits"))
        ) or 0
        index_entries = self.db.scalar(select(func.count()).select_from(FitsIndexEntry)) or 0
        missing_current_fits = max(entity_count - current_fits, 0)
        uncategorised_count = self._uncategorised_evidence_count()
        return {
            "product": "TrustVault",
            "tagline": "Secure evidence assurance for regulated customer records",
            "source_of_truth": "FITS evidence containers",
            "entity_count": entity_count,
            "customer_count": entity_count,
            "evidence_object_count": evidence_count,
            "current_fits_container_count": current_fits,
            "entities_missing_current_fits": missing_current_fits,
            "fits_index_entry_count": index_entries,
            "queued_jobs": self.db.scalar(select(func.count()).select_from(Job).where(Job.status == "queued")) or 0,
            "running_jobs": self.db.scalar(select(func.count()).select_from(Job).where(Job.status == "running")) or 0,
            "failed_jobs": self.db.scalar(select(func.count()).select_from(Job).where(Job.status == "failed")) or 0,
            "audit_event_count": self.db.scalar(select(func.count()).select_from(AuditEvent)) or 0,
            "completeness_exception_count": self.db.scalar(
                select(func.count()).select_from(CompletenessResult).where(CompletenessResult.status == "missing")
            ) or 0,
            "extraction_index_entry_count": index_entries,
            "retention_issue_count": 0,
            "integrity_issue_count": missing_current_fits,
            "categorisation_uncategorised_count": uncategorised_count,
        }

    def _uncategorised_evidence_count(self) -> int:
        evidence_rows = self.db.scalars(select(EvidenceObject.metadata_json)).all()
        entity_rows = self.db.scalars(select(Entity.metadata_json)).all()
        evidence_count = sum(1 for metadata in evidence_rows if self._is_uncategorised_metadata(metadata or {}))
        customer_gap_count = sum(1 for metadata in entity_rows if self._has_customer_information_gap(metadata or {}))
        return evidence_count + customer_gap_count

    def _has_customer_information_gap(self, metadata: dict[str, Any]) -> bool:
        legacy_gaps = metadata.get("customer_information_gaps")
        if legacy_gaps:
            return True
        assurance_gaps = metadata.get("assurance_gaps")
        if not isinstance(assurance_gaps, list):
            return False
        return any(
            isinstance(gap, dict)
            and gap.get("gap_key") == "customer_information_missing"
            and gap.get("status") != "resolved"
            for gap in assurance_gaps
        )

    def _is_uncategorised_metadata(self, metadata: dict[str, Any]) -> bool:
        category = self._normalise(metadata.get("category"))
        document_type = self._normalise(metadata.get("document_type"))
        status = self._normalise(metadata.get("classification_status"))
        confidence_raw = metadata.get("classification_confidence")
        try:
            confidence = float(confidence_raw) if confidence_raw is not None else None
        except (TypeError, ValueError):
            confidence = None
        uncategorised = {"", "unknown", "uncategorised", "uncategorized", "general", "general_evidence", "document"}
        return (
            category in uncategorised
            or document_type in uncategorised
            or status in {"uncategorised", "uncategorized", "unmatched"}
            or (confidence is not None and confidence < 0.75)
        )

    def archive_status(self) -> dict[str, Any]:
        settings = get_settings()
        return {
            **self.dashboard(),
            "configuration": {
                "storage_provider": settings.storage_provider,
                "queue_provider": settings.queue_provider,
                "source_folder": "local-data/storage/source-imports" if settings.storage_provider == "local" else settings.s3_source_bucket,
                "containers_folder": "local-data/storage/fits-containers" if settings.storage_provider == "local" else settings.s3_fits_bucket,
                "index_path": "PostgreSQL table: fits_index_entries",
                "exports_folder": "local-data/storage/derived-reports" if settings.storage_provider == "local" else settings.s3_export_bucket,
            },
            "archive_checks": {
                "fits_source_of_truth": True,
                "index_rebuildable": True,
                "direct_fits_search_available": True,
                "cross_archive_index_available": True,
            },
        }

    def health(self) -> dict[str, Any]:
        storage_ok = True
        storage_error = None
        try:
            self.storage.list_keys("fits-containers", "")
        except Exception as exc:  # pragma: no cover - environment boundary
            storage_ok = False
            storage_error = str(exc)
        return {
            "status": "ok" if storage_ok else "degraded",
            "components": {
                "api": {"status": "ok"},
                "database": {"status": "ok"},
                "storage": {"status": "ok" if storage_ok else "error", "error": storage_error},
                "queue": {"status": "database-backed"},
                "worker": {"status": "polled", "heartbeat": "job-table"},
                "ai": {"status": "disabled_by_default"},
                "ocr": {"status": "sidecar_or_metadata_first"},
            },
        }

    def customers(
        self,
        *,
        risk_rating: str | None = None,
        jurisdiction: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        entities = self.db.scalars(select(Entity).order_by(Entity.external_id.asc())).all()
        rows = [self.customer_summary(entity) for entity in entities]
        if risk_rating:
            rows = [row for row in rows if self._normalise(row.get("metadata_json", {}).get("risk_rating")) == self._normalise(risk_rating)]
        if jurisdiction:
            rows = [row for row in rows if self._normalise(row.get("metadata_json", {}).get("jurisdiction")) == self._normalise(jurisdiction)]
        if limit is not None:
            rows = rows[:limit]
        return rows

    def customer_summary(self, entity: Entity | str) -> dict[str, Any]:
        entity_obj = self._entity(entity) if isinstance(entity, str) else entity
        current = self._current_fits(entity_obj.id, required=False)
        evidence_count = self.db.scalar(
            select(func.count()).select_from(EvidenceObject).where(EvidenceObject.entity_id == entity_obj.id)
        ) or 0
        return {
            "id": str(entity_obj.id),
            "external_id": entity_obj.external_id,
            "display_name": entity_obj.display_name,
            "entity_type": entity_obj.entity_type,
            "status": entity_obj.status,
            "metadata_json": entity_obj.metadata_json,
            "risk_rating": entity_obj.metadata_json.get("risk_rating") if entity_obj.metadata_json else None,
            "jurisdiction": entity_obj.metadata_json.get("jurisdiction") if entity_obj.metadata_json else None,
            "evidence_object_count": evidence_count,
            "has_current_fits_container": current is not None,
            "current_container_version_id": str(current.id) if current else None,
            "current_container_version_number": current.version_number if current else None,
            "current_container_storage_uri": current.storage_uri if current else None,
            "created_at": entity_obj.created_at,
            "updated_at": entity_obj.updated_at,
        }

    def entity_evidence_summary(self, entity_id: str) -> dict[str, Any]:
        entity = self._entity(entity_id)
        current = self._current_fits(entity.id, required=False)
        manifest = current.manifest_json.get("evidence_objects", []) if current else []
        by_category: dict[str, int] = {}
        by_document_type: dict[str, int] = {}
        for item in manifest:
            by_category[str(item.get("category") or item.get("object_type") or "unknown")] = by_category.get(str(item.get("category") or item.get("object_type") or "unknown"), 0) + 1
            by_document_type[str(item.get("document_type") or item.get("object_type") or "unknown")] = by_document_type.get(str(item.get("document_type") or item.get("object_type") or "unknown"), 0) + 1
        return {
            "entity": self.customer_summary(entity),
            "container_version_id": str(current.id) if current else None,
            "evidence_count": len(manifest),
            "counts_by_category": by_category,
            "counts_by_document_type": by_document_type,
        }

    def comparison(self, entity_id: str, query: str | None = None) -> dict[str, Any]:
        entity = self._entity(entity_id)
        current = self._current_fits(entity.id, required=False)
        db_evidence = self.db.scalars(select(EvidenceObject).where(EvidenceObject.entity_id == entity.id)).all()
        if current is None:
            return {
                "entity": self.customer_summary(entity),
                "has_current_fits": False,
                "checks": [{"name": "current_fits_exists", "status": "fail"}],
            }
        manifest = current.manifest_json.get("evidence_objects", [])
        db_ids = {str(item.id) for item in db_evidence}
        fits_ids = {str(item.get("id")) for item in manifest}
        checks = [
            {"name": "current_fits_exists", "status": "pass"},
            {"name": "manifest_count_matches_db", "status": "pass" if len(manifest) == len(db_evidence) else "fail", "fits": len(manifest), "database": len(db_evidence)},
            {"name": "manifest_ids_match_db", "status": "pass" if db_ids == fits_ids else "fail", "missing_from_fits": sorted(db_ids - fits_ids), "missing_from_db": sorted(fits_ids - db_ids)},
        ]
        if query:
            from trustvault.core.fits_reader import FitsContainerReader

            direct = FitsContainerReader(self.db).direct_search(entity.external_id, query)
            indexed = FitsContainerReader(self.db).index_search(query, entity.external_id)
            checks.append({
                "name": "direct_fits_search_matches_index_search",
                "status": "pass" if direct["result_count"] == indexed["result_count"] else "warning",
                "direct_result_count": direct["result_count"],
                "index_result_count": indexed["result_count"],
            })
        return {"entity": self.customer_summary(entity), "container_version_id": str(current.id), "checks": checks}

    def ensure_default_ruleset(self) -> Ruleset:
        ruleset = self.db.scalars(select(Ruleset).where(Ruleset.status == "active")).first()
        if ruleset is not None:
            return ruleset
        ruleset = Ruleset(
            name="Default Customer Evidence Ruleset",
            version=1,
            status="active",
            description="Default controlled-deployment evidence completeness rules.",
            metadata_json={"source": "system_default"},
        )
        self.db.add(ruleset)
        self.db.flush()
        defaults = [
            ("identity_passport", "identity", "passport", ["person"]),
            ("proof_of_address", "proof_of_address", "proof_of_address", ["person"]),
            ("source_of_wealth", "source_of_wealth", "source_of_wealth", ["person"]),
            ("cdd_risk_review", "cdd_review", "cdd_risk_review", ["person", "organisation"]),
            ("account_opening_application", "customer_documents", "account_opening_application", ["person", "organisation"]),
            ("screening_evidence", "customer_documents", "screening", ["person", "organisation"]),
            ("correspondence_due_diligence", "communications", "email", ["person", "organisation"]),
            ("organisation_chart", "ownership_and_control", "organisation_chart", ["organisation"]),
            ("shareholder_certificate", "ownership_and_control", "shareholder_certificate", ["organisation"]),
            ("certificate_of_incorporation", "organisation_identity", "certificate_of_incorporation", ["organisation"]),
        ]
        for key, category, document_type, applies_to in defaults:
            self.db.add(RulesetRule(
                ruleset_id=ruleset.id,
                rule_key=key,
                category=category,
                document_type=document_type,
                required=True,
                applies_when_json={"entity_types": applies_to},
                metadata_json={"source": "system_default", "applies_to_entity_types": applies_to},
            ))
        self.db.commit()
        self.db.refresh(ruleset)
        return ruleset

    def rulesets(self) -> list[dict[str, Any]]:
        self.ensure_default_ruleset()
        rulesets = self.db.scalars(select(Ruleset).order_by(Ruleset.created_at.desc())).all()
        return [self._ruleset_dict(item) for item in rulesets]

    def ruleset_detail(self, ruleset_id: str) -> dict[str, Any]:
        ruleset = self.db.get(Ruleset, uuid.UUID(ruleset_id))
        if ruleset is None:
            raise ValueError("Ruleset not found")
        return self._ruleset_dict(ruleset)

    def _ruleset_dict(self, ruleset: Ruleset) -> dict[str, Any]:
        rules = self.db.scalars(select(RulesetRule).where(RulesetRule.ruleset_id == ruleset.id)).all()
        return {
            "id": str(ruleset.id),
            "name": ruleset.name,
            "version": ruleset.version,
            "status": ruleset.status,
            "description": ruleset.description,
            "metadata_json": ruleset.metadata_json,
            "rule_count": len(rules),
            "required_rule_count": sum(1 for rule in rules if rule.required),
            "rules": [
                {
                    "id": str(rule.id),
                    "rule_key": rule.rule_key,
                    "category": rule.category,
                    "document_type": rule.document_type,
                    "required": rule.required,
                    "applies_when_json": rule.applies_when_json,
                    "max_age_days": rule.max_age_days,
                    "metadata_json": rule.metadata_json,
                    "applies_to_entity_types": self._rule_entity_types(rule),
                }
                for rule in rules
            ],
        }

    def evaluate_completeness(self, entity_id: str, ruleset_id: str | None = None) -> dict[str, Any]:
        entity = self._entity(entity_id)
        ruleset = self.db.get(Ruleset, uuid.UUID(ruleset_id)) if ruleset_id else self.ensure_default_ruleset()
        current = self._current_fits(entity.id, required=False)
        manifest = (current.manifest_json.get("evidence_objects", []) if current else [])
        rules = self.db.scalars(select(RulesetRule).where(RulesetRule.ruleset_id == ruleset.id)).all()
        results = []
        present_count = 0
        for rule in rules:
            if not self._rule_applies_to_entity(rule, entity):
                continue
            match = self._match_rule(rule, manifest)
            if match:
                present_count += 1
            results.append({
                "rule_key": rule.rule_key,
                "category": rule.category,
                "document_type": rule.document_type,
                "status": "present" if match else "missing",
                "matched_evidence_object_id": match.get("id") if match else None,
                "matched_filename": match.get("filename") if match else None,
            })
        required_count = len(rules)
        missing_count = required_count - present_count
        score = int((present_count / required_count) * 100) if required_count else 100
        run = CompletenessRun(
            entity_id=entity.id,
            ruleset_id=ruleset.id,
            container_version_id=current.id if current else None,
            status="completed",
            score=score,
            required_count=required_count,
            present_count=present_count,
            missing_count=missing_count,
            result_json={"results": results},
        )
        self.db.add(run)
        self.db.flush()
        for row in results:
            self.db.add(CompletenessResult(
                run_id=run.id,
                entity_id=entity.id,
                rule_key=row["rule_key"],
                category=row["category"],
                document_type=row["document_type"],
                status=row["status"],
                matched_evidence_object_id=row["matched_evidence_object_id"],
                details_json=row,
            ))
        self.db.commit()
        return {
            "run_id": str(run.id),
            "entity_id": str(entity.id),
            "entity_external_id": entity.external_id,
            "ruleset_id": str(ruleset.id),
            "container_version_id": str(current.id) if current else None,
            "score": score,
            "required_count": required_count,
            "present_count": present_count,
            "missing_count": missing_count,
            "results": results,
        }

    def _match_rule(self, rule: RulesetRule, manifest: list[dict[str, Any]]) -> dict[str, Any] | None:
        rule_category = self._normalise(rule.category)
        rule_document_type = self._normalise(rule.document_type)
        for item in manifest:
            category = self._normalise(item.get("category"))
            document_type = self._normalise(item.get("document_type"))
            object_type = self._normalise(item.get("object_type"))
            category_matches = not rule_category or category == rule_category
            document_type_matches = not rule_document_type or any(
                value == rule_document_type or value.startswith(f"{rule_document_type} ")
                for value in (document_type, object_type)
            )
            if category_matches and document_type_matches:
                return item
        return None

    def _rule_applies_to_entity(self, rule: RulesetRule, entity: Entity) -> bool:
        entity_types = self._rule_entity_types(rule)
        if not entity_types:
            return True
        return self._normalise(entity.entity_type) in {self._normalise(item) for item in entity_types}

    def _rule_entity_types(self, rule: RulesetRule) -> list[str]:
        applies_when = rule.applies_when_json or {}
        metadata = rule.metadata_json or {}
        raw = applies_when.get("entity_types") or metadata.get("applies_to_entity_types") or applies_when.get("entity_type")
        if raw in (None, "", "both", "all"):
            return []
        if isinstance(raw, str):
            return [raw]
        if isinstance(raw, list):
            return [str(item) for item in raw if str(item).strip()]
        return []

    def extraction_report(self, entity_id: str) -> dict[str, Any]:
        entity = self._entity(entity_id)
        current = self._current_fits(entity.id, required=False)
        if current is None:
            return {"entity": self.customer_summary(entity), "ocr_text": [], "extracted_fields": [], "extraction_events": []}
        hdus = self._read_json_hdus(current, ["OCR_TEXT", "EXTRACTED_FIELDS", "EXTRACTION_EVENTS"])
        return {"entity": self.customer_summary(entity), "container_version_id": str(current.id), **hdus}

    def retention_report(self, entity_id: str | None = None) -> dict[str, Any]:
        entities = [self._entity(entity_id)] if entity_id else self.db.scalars(select(Entity).order_by(Entity.external_id.asc())).all()
        rows = []
        for entity in entities:
            current = self._current_fits(entity.id, required=False)
            manifest = current.manifest_json.get("evidence_objects", []) if current else []
            rows.append({
                "entity_id": str(entity.id),
                "entity_external_id": entity.external_id,
                "container_version_id": str(current.id) if current else None,
                "evidence": [
                    {
                        "evidence_object_id": item.get("id"),
                        "filename": item.get("filename"),
                        "category": item.get("category"),
                        "document_type": item.get("document_type"),
                        "retention_class": item.get("retention_class"),
                        "retention_until": item.get("retention_until"),
                        "retention_basis": item.get("retention_basis"),
                        "legal_hold_status": item.get("legal_hold_status"),
                        "deletion_eligible": item.get("deletion_eligible"),
                        "sensitivity": item.get("sensitivity"),
                        "jurisdiction": item.get("jurisdiction"),
                    }
                    for item in manifest
                ],
            })
        return {"entity_count": len(rows), "entities": rows}

    def integrity_summary(self, entity_id: str | None = None, *, full: bool = False) -> dict[str, Any]:
        from trustvault.core.integrity import ContainerIntegrityValidator

        entities = [self._entity(entity_id)] if entity_id else self.db.scalars(select(Entity).order_by(Entity.external_id.asc())).all()
        rows = []
        validator = ContainerIntegrityValidator(self.db) if entity_id or full else None
        for entity in entities:
            current = self._current_fits(entity.id, required=False)
            if current is None:
                rows.append({
                    "entity_id": str(entity.id),
                    "entity_external_id": entity.external_id,
                    "entity_display_name": entity.display_name,
                    "overall_status": "missing_current_fits",
                    "summary_mode": "metadata",
                    "validated": False,
                    "evidence_object_count": 0,
                    "issue_count": 1,
                })
                continue
            if validator is not None:
                rows.append(validator.validate_container_version(str(current.id)))
                continue
            rows.append({
                "entity_id": str(entity.id),
                "entity_external_id": entity.external_id,
                "entity_display_name": entity.display_name,
                "container_version_id": str(current.id),
                "version_number": current.version_number,
                "status": current.status,
                "storage_uri": current.storage_uri,
                "expected_container_sha256": current.sha256,
                "expected_size_bytes": current.size_bytes,
                "evidence_object_count": current.evidence_object_count,
                "fits_opened": None,
                "container_hash_matches": None,
                "missing_required_hdus": [],
                "payload_results": [],
                "overall_status": "not_checked",
                "summary_mode": "metadata",
                "validated": False,
                "issue_count": 0,
            })
        return {"checked_count": len(rows), "summary_mode": "full" if full or entity_id else "metadata", "results": rows}

    def source_systems(self) -> list[dict[str, Any]]:
        rows = self.db.scalars(select(SourceSystem).order_by(SourceSystem.name.asc())).all()
        return [
            {"id": str(row.id), "name": row.name, "system_type": row.system_type, "status": row.status, "config_json": row.config_json}
            for row in rows
        ]

    def api_status(self) -> dict[str, Any]:
        return {
            "version": "v1",
            "archive_model": "one_current_fits_container_per_customer_entity",
            "features": [
                "dashboard", "health", "comparison", "customers", "search", "completeness", "rulesets",
                "ingestion", "extraction", "retention", "integrity", "export", "api", "audit", "jobs", "licence",
                "query_interpretation", "cross_archive_search", "direct_fits_search",
            ],
            "source_of_truth": "FITS containers",
            "query_modes": {
                "direct_fits_search": "Selected-customer evidence search reads the FITS archive directly.",
                "cross_archive_search": "Archive-wide and cohort searches use the rebuildable PostgreSQL index.",
                "natural_language_interpretation": "Deterministic interpreter normalises onboarding to snapshot_id=ONBOARDING, not document_type=ONBOARDING.",
            },
        }

    def _read_json_hdus(self, container: EntityContainerVersion, names: list[str]) -> dict[str, Any]:
        parsed = parse_storage_uri(container.storage_uri)
        data = self.storage.get_bytes(parsed.bucket, parsed.key)
        result = {}
        with fits.open(io.BytesIO(data), checksum=True) as hdul:
            hdu_map = {hdu.name: hdu for hdu in hdul}
            for name in names:
                key = name.lower()
                if name not in hdu_map:
                    result[key] = []
                    continue
                raw = np.asarray(hdu_map[name].data, dtype=np.uint8).tobytes()
                result[key] = json.loads(raw.decode("utf-8"))
        return result

    def _entity(self, entity_id_or_external_id: str) -> Entity:
        try:
            entity = self.db.get(Entity, uuid.UUID(entity_id_or_external_id))
            if entity is not None:
                return entity
        except ValueError:
            pass
        entity = self.db.scalars(select(Entity).where(Entity.external_id == entity_id_or_external_id)).first()
        if entity is None:
            raise ValueError("Entity not found")
        return entity

    def _current_fits(self, entity_id: uuid.UUID, required: bool = True) -> EntityContainerVersion | None:
        current = self.db.scalars(
            select(EntityContainerVersion)
            .where(EntityContainerVersion.entity_id == entity_id)
            .where(EntityContainerVersion.status == "current")
            .where(EntityContainerVersion.storage_uri.ilike("%.fits"))
            .order_by(EntityContainerVersion.version_number.desc())
            .limit(1)
        ).first()
        if current is None and required:
            raise ValueError("Entity has no current FITS container")
        return current

    def _normalise(self, value: Any) -> str:
        return str(value or "").strip().lower().replace("_", " ").replace("-", " ")
