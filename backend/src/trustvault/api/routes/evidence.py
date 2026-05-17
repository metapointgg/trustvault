from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from trustvault.audit.events import EVIDENCE_PREVIEWED, SEARCH_EXECUTED
from trustvault.audit.logger import AuditLogger
from trustvault.api.dependencies import get_audit_logger, get_database
from trustvault.core.evidence_preview import EvidencePreviewService
from trustvault.core.search import EvidenceSearchService

router = APIRouter(prefix="/api/v1/evidence", tags=["evidence"])


class EvidencePreviewResponse(BaseModel):
    evidence_object_id: str
    entity_id: str
    object_type: str
    source_system: str
    storage_uri: str
    sha256: str
    content_type: str | None
    filename: str | None
    preview_kind: str
    text_preview: str | None
    safe_preview: str | None
    size_bytes: int
    view_url: str
    download_url: str
    metadata: dict


class SearchRequest(BaseModel):
    query: str
    limit: int = 50


class SearchResultResponse(BaseModel):
    entity_id: str
    entity_external_id: str
    entity_display_name: str
    evidence_object_id: str
    object_type: str
    source_system: str
    storage_uri: str
    sha256: str
    content_type: str | None
    snippet: str | None
    match_source: str | None = None
    hdu_name: str | None = None
    filename: str | None = None


class SearchResponse(BaseModel):
    query: str
    result_count: int
    results: list[SearchResultResponse]


@router.get("/{evidence_object_id}/preview", response_model=EvidencePreviewResponse)
def preview_evidence(
    evidence_object_id: str,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> EvidencePreviewResponse:
    try:
        preview = EvidencePreviewService(db).preview(evidence_object_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    audit_logger.log(
        EVIDENCE_PREVIEWED,
        entity_ids=[preview.entity_id],
        object_ids=[preview.evidence_object_id],
        metadata={
            "object_type": preview.object_type,
            "source_system": preview.source_system,
            "preview_kind": preview.preview_kind,
            "filename": preview.filename,
        },
    )
    return EvidencePreviewResponse(**preview.__dict__)


@router.get("/{evidence_object_id}/file")
def view_evidence_file(
    evidence_object_id: str,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> Response:
    try:
        payload = EvidencePreviewService(db).payload(evidence_object_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit_logger.log(EVIDENCE_PREVIEWED, object_ids=[payload.evidence_object_id], metadata={"filename": payload.filename, "mode": "view"})
    return Response(
        content=payload.data,
        media_type=payload.content_type,
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(payload.filename)}"},
    )


@router.get("/{evidence_object_id}/download")
def download_evidence_file(
    evidence_object_id: str,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> Response:
    try:
        payload = EvidencePreviewService(db).payload(evidence_object_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    audit_logger.log(EVIDENCE_PREVIEWED, object_ids=[payload.evidence_object_id], metadata={"filename": payload.filename, "mode": "download"})
    return Response(
        content=payload.data,
        media_type=payload.content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(payload.filename)}"},
    )


@router.post("/search", response_model=SearchResponse)
def search_evidence(
    request: SearchRequest,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> SearchResponse:
    results = EvidenceSearchService(db).search(request.query, request.limit)
    audit_logger.log(
        SEARCH_EXECUTED,
        raw_query=request.query,
        result_count=len(results),
        search_source="local_storage_text_scan",
        entity_ids=[result.entity_id for result in results],
        object_ids=[result.evidence_object_id for result in results],
        metadata={"limit": request.limit},
    )
    return SearchResponse(
        query=request.query,
        result_count=len(results),
        results=[SearchResultResponse(**result.__dict__) for result in results],
    )
