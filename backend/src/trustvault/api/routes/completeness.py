import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.audit.events import COMPLETENESS_REVIEW_RUN
from trustvault.audit.logger import AuditLogger
from trustvault.api.dependencies import get_audit_logger, get_database
from trustvault.auth.dependencies import require_permission
from trustvault.auth.models import CurrentUser
from trustvault.core.feature_services import TrustVaultFeatureService
from trustvault.db.models import Entity, EntityContainerVersion, Ruleset, RulesetRule

router = APIRouter(prefix="/api/v1/completeness", tags=["completeness"])


class CompletenessRequest(BaseModel):
    ruleset_id: str | None = None


@router.get("/summary")
def completeness_summary(
    risk_rating: str | None = Query(default=None),
    jurisdiction: str | None = Query(default=None),
    entity_external_id: str | None = Query(default=None),
    ruleset_id: str | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_database),
    current_user: CurrentUser = Depends(require_permission("customers:read")),
) -> dict[str, Any]:
    service = TrustVaultFeatureService(db)
    if ruleset_id is None:
        ruleset = service.ensure_default_ruleset()
    else:
        try:
            ruleset = db.get(Ruleset, uuid.UUID(ruleset_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid ruleset id") from exc
    if ruleset is None:
        raise HTTPException(status_code=404, detail="Ruleset not found")
    rules = db.scalars(select(RulesetRule).where(RulesetRule.ruleset_id == ruleset.id)).all()
    entities = db.scalars(select(Entity).order_by(Entity.external_id.asc()).limit(limit)).all()
    rows: list[dict[str, Any]] = []
    for entity in entities:
        metadata = entity.metadata_json or {}
        if entity_external_id and entity.external_id != entity_external_id:
            continue
        if risk_rating and service._normalise(metadata.get("risk_rating")) != service._normalise(risk_rating):
            continue
        if jurisdiction and service._normalise(metadata.get("jurisdiction")) != service._normalise(jurisdiction):
            continue

        current = db.scalars(
            select(EntityContainerVersion)
            .where(EntityContainerVersion.entity_id == entity.id)
            .where(EntityContainerVersion.status == "current")
            .where(EntityContainerVersion.storage_uri.ilike("%.fits"))
            .order_by(EntityContainerVersion.version_number.desc())
            .limit(1)
        ).first()
        manifest = current.manifest_json.get("evidence_objects", []) if current else []
        present = 0
        rule_rows = []
        for rule in rules:
            if not service._rule_applies_to_entity(rule, entity):
                continue
            match = service._match_rule(rule, manifest)
            if match:
                present += 1
            rule_rows.append(
                {
                    "entity_id": str(entity.id),
                    "entity_external_id": entity.external_id,
                    "entity_display_name": entity.display_name,
                    "entity_type": entity.entity_type,
                    "risk_rating": metadata.get("risk_rating"),
                    "jurisdiction": metadata.get("jurisdiction"),
                    "container_version_id": str(current.id) if current else None,
                    "ruleset_id": str(ruleset.id),
                    "ruleset_name": ruleset.name,
                    "ruleset_version": ruleset.version,
                    "rule_key": rule.rule_key,
                    "category": rule.category,
                    "document_type": rule.document_type,
                    "applies_to_entity_types": service._rule_entity_types(rule),
                    "rule_status": "present" if match else "missing",
                    "status": "present" if match else "missing",
                    "matched_evidence_object_id": match.get("id") if match else None,
                    "matched_filename": match.get("filename") if match else None,
                }
            )
        required = len(rules)
        missing = required - present
        score = int((present / required) * 100) if required else 100
        for row in rule_rows:
            row.update(
                {
                    "completeness_score": score,
                    "required_count": required,
                    "present_count": present,
                    "missing_count": missing,
                }
            )
        rows.extend(rule_rows)

    entity_ids = {row["entity_id"] for row in rows}
    incomplete_entity_ids = {row["entity_id"] for row in rows if row["missing_count"] > 0}
    complete_entity_count = len(entity_ids - incomplete_entity_ids)
    incomplete_entity_count = len(incomplete_entity_ids)
    missing_evidence_item_count = sum(1 for row in rows if row["status"] == "missing")
    return {
        "ruleset_id": str(ruleset.id),
        "ruleset_name": ruleset.name,
        "ruleset_version": ruleset.version,
        "entity_count": len(entity_ids),
        "entities_evaluated": len(entity_ids),
        "complete_entity_count": complete_entity_count,
        "complete_count": complete_entity_count,
        "incomplete_entity_count": incomplete_entity_count,
        "incomplete_count": incomplete_entity_count,
        "missing_evidence_item_count": missing_evidence_item_count,
        "missing_evidence_items": missing_evidence_item_count,
        "result_count": len(rows),
        "results": rows,
        "rows": rows,
    }


@router.post("/entities/{entity_id}/evaluate")
def evaluate_completeness(
    entity_id: str,
    request: CompletenessRequest,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
    current_user: CurrentUser = Depends(require_permission("completeness:run")),
) -> dict[str, Any]:
    try:
        result = TrustVaultFeatureService(db).evaluate_completeness(entity_id, request.ruleset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit_logger.log(
        COMPLETENESS_REVIEW_RUN,
        user_id=current_user.subject,
        entity_ids=[result["entity_id"]],
        result_count=result["missing_count"],
        metadata={
            "run_id": result["run_id"],
            "ruleset_id": result["ruleset_id"],
            "score": result["score"],
            "missing_count": result["missing_count"],
        },
    )
    return result
