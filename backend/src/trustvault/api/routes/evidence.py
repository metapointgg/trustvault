from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.audit.events import EVIDENCE_PREVIEWED, SEARCH_EXECUTED
from trustvault.audit.logger import AuditLogger
from trustvault.api.dependencies import get_audit_logger, get_database
from trustvault.auth.dependencies import require_permission
from trustvault.auth.models import CurrentUser
from trustvault.core.container_builder import EntityContainerBuilder
from trustvault.core.document_classification import DocumentClassificationService
from trustvault.core.evidence_preview import EvidencePreviewService
from trustvault.core.fits_reader import FitsContainerReader
from trustvault.core.search import EvidenceSearchService
from trustvault.db.models import Entity, EvidenceObject

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


class EvidenceClassificationRow(BaseModel):
    evidence_object_id: str
    entity_id: str
    entity_external_id: str
    entity_display_name: str
    filename: str | None
    source_path: str | None
    object_type: str
    source_system: str
    document_type: str | None
    category: str | None
    classification_status: str | None
    classification_source: str | None
    classification_confidence: float | None
    matched_pattern: str | None = None


class EvidenceClassificationUpdateRequest(BaseModel):
    evidence_object_ids: list[str] = Field(min_length=1)
    document_type: str = Field(min_length=1)
    rebuild_container: bool = True
    rebuild_index: bool = True


class EvidenceClassificationUpdateResponse(BaseModel):
    updated_count: int
    document_type: str
    category: str | None
    updated_object_ids: list[str]
    rebuilt_entities: list[str]


def _evidence_row(evidence: EvidenceObject, entity: Entity) -> EvidenceClassificationRow:
    metadata = evidence.metadata_json or {}
    return EvidenceClassificationRow(
        evidence_object_id=str(evidence.id),
        entity_id=str(entity.id),
        entity_external_id=entity.external_id,
        entity_display_name=entity.display_name,
        filename=metadata.get("filename") or metadata.get("source_path", "").split("/")[-1] or None,
        source_path=metadata.get("source_path"),
        object_type=evidence.object_type,
        source_system=evidence.source_system,
        document_type=metadata.get("document_type"),
        category=metadata.get("category"),
        classification_status=metadata.get("classification_status"),
        classification_source=metadata.get("classification_source"),
        classification_confidence=metadata.get("classification_confidence"),
        matched_pattern=metadata.get("classification_matched_pattern"),
    )


@router.get("/uncategorised", response_model=list[EvidenceClassificationRow])
def list_uncategorised_evidence(
    limit: int = 500,
    db: Session = Depends(get_database),
    current_user: CurrentUser = Depends(require_permission("evidence:read")),
) -> list[EvidenceClassificationRow]:
    classifier = DocumentClassificationService(db)
    rows = db.execute(select(EvidenceObject, Entity).join(Entity, EvidenceObject.entity_id == Entity.id)).all()
    result: list[EvidenceClassificationRow] = []
    for evidence, entity in rows:
        if classifier.is_uncategorised(evidence.metadata_json):
            result.append(_evidence_row(evidence, entity))
        if len(result) >= limit:
            break
    return result


@router.patch("/classification", response_model=EvidenceClassificationUpdateResponse)
def update_evidence_classification(
    request: EvidenceClassificationUpdateRequest,
    db: Session = Depends(get_database),
    current_user: CurrentUser = Depends(require_permission("evidence:classify")),
) -> EvidenceClassificationUpdateResponse:
    classifier = DocumentClassificationService(db)
    category = classifier.category_for_document_type(request.document_type)
    if category is None:
        raise HTTPException(status_code=400, detail=f"Unknown document type: {request.document_type}")

    updated_object_ids: list[str] = []
    entity_external_ids: set[str] = set()
    for evidence_object_id in request.evidence_object_ids:
        evidence = db.get(EvidenceObject, evidence_object_id)
        if evidence is None:
            continue
        entity = db.get(Entity, evidence.entity_id)
        if entity is None:
            continue
        evidence.metadata_json = classifier.mark_confirmed(
            evidence.metadata_json,
            document_type=request.document_type,
            updated_by=current_user.subject,
        )
        evidence.object_type = request.document_type
        updated_object_ids.append(str(evidence.id))
        entity_external_ids.add(entity.external_id)

    db.commit()

    rebuilt_entities: list[str] = []
    for entity_external_id in sorted(entity_external_ids):
        if request.rebuild_container:
            EntityContainerBuilder(db).rebuild(entity_external_id)
        if request.rebuild_index:
            FitsContainerReader(db).rebuild_index_from_current_fits(entity_external_id)
        rebuilt_entities.append(entity_external_id)

    return EvidenceClassificationUpdateResponse(
        updated_count=len(updated_object_ids),
        document_type=request.document_type,
        category=category,
        updated_object_ids=updated_object_ids,
        rebuilt_entities=rebuilt_entities,
    )


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
