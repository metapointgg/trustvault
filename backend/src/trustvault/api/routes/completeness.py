from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from trustvault.audit.events import COMPLETENESS_REVIEW_RUN
from trustvault.audit.logger import AuditLogger
from trustvault.api.dependencies import get_audit_logger, get_database
from trustvault.core.feature_services import TrustVaultFeatureService

router = APIRouter(prefix="/api/v1/completeness", tags=["completeness"])


class CompletenessRequest(BaseModel):
    ruleset_id: str | None = None


@router.post("/entities/{entity_id}/evaluate")
def evaluate_completeness(
    entity_id: str,
    request: CompletenessRequest,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> dict[str, Any]:
    try:
        result = TrustVaultFeatureService(db).evaluate_completeness(entity_id, request.ruleset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit_logger.log(
        COMPLETENESS_REVIEW_RUN,
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
