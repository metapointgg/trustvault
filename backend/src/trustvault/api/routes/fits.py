from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from trustvault.audit.events import INDEX_REBUILT, SEARCH_EXECUTED
from trustvault.audit.logger import AuditLogger
from trustvault.api.dependencies import get_audit_logger, get_database
from trustvault.core.fits_reader import FitsContainerReader

router = APIRouter(prefix="/api/v1/fits", tags=["fits"])


class FitsInspectResponse(BaseModel):
    container_version_id: str
    entity_id: str
    version_number: int
    status: str
    storage_uri: str
    sha256: str
    size_bytes: int
    hdu_count: int
    hdu_names: list[str]
    summary: dict[str, Any] | None
    entity_metadata: dict[str, Any] | None
    manifest: list[dict[str, Any]] | None
    ocr_text: list[dict[str, Any]] | None
    hash_report: dict[str, Any] | None
    hdus: list[dict[str, Any]]


class FitsSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = 50


class FitsSearchResponse(BaseModel):
    query: str
    entity_id: str | None = None
    entity_external_id: str | None = None
    container_version_id: str | None = None
    result_count: int
    results: list[dict[str, Any]]


class FitsIndexSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    entity_id: str | None = None
    entity_external_id: str | None = None
    limit: int = 50


class FitsIndexRebuildRequest(BaseModel):
    entity_id: str | None = None
    entity_external_id: str | None = None


class FitsIndexRebuildResponse(BaseModel):
    indexed_entity_count: int
    skipped_entity_count: int
    indexed: list[dict[str, Any]]
    skipped: list[dict[str, Any]]


@router.get("/entities/{entity_id}/inspect", response_model=FitsInspectResponse)
def inspect_current_entity_fits(
    entity_id: str,
    db: Session = Depends(get_database),
) -> FitsInspectResponse:
    try:
        result = FitsContainerReader(db).inspect_current_for_entity(entity_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FitsInspectResponse(**result)


@router.get("/versions/{container_version_id}/inspect", response_model=FitsInspectResponse)
def inspect_fits_version(
    container_version_id: str,
    db: Session = Depends(get_database),
) -> FitsInspectResponse:
    try:
        result = FitsContainerReader(db).inspect_version(container_version_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FitsInspectResponse(**result)


@router.post("/entities/{entity_id}/search", response_model=FitsSearchResponse)
def search_entity_fits(
    entity_id: str,
    request: FitsSearchRequest,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> FitsSearchResponse:
    try:
        result = FitsContainerReader(db).direct_search(entity_id, request.query, request.limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    audit_logger.log(
        SEARCH_EXECUTED,
        raw_query=request.query,
        result_count=result["result_count"],
        search_source="direct_fits_container",
        entity_ids=[result["entity_id"]],
        object_ids=[item.get("evidence_object_id") for item in result["results"]],
        metadata={
            "container_version_id": result["container_version_id"],
            "entity_external_id": result["entity_external_id"],
        },
    )
    return FitsSearchResponse(**result)


@router.post("/index/search", response_model=FitsSearchResponse)
def search_fits_index(
    request: FitsIndexSearchRequest,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> FitsSearchResponse:
    entity_reference = request.entity_id or request.entity_external_id
    try:
        result = FitsContainerReader(db).index_search(request.query, entity_reference, request.limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    audit_logger.log(
        SEARCH_EXECUTED,
        raw_query=request.query,
        result_count=result["result_count"],
        search_source="fits_index",
        entity_ids=[result["entity_id"]] if result.get("entity_id") else [],
        object_ids=[item.get("evidence_object_id") for item in result["results"]],
        metadata={
            "entity_external_id": result.get("entity_external_id"),
            "entity_reference": entity_reference,
        },
    )
    return FitsSearchResponse(**result)


@router.post("/index/rebuild", response_model=FitsIndexRebuildResponse)
def rebuild_fits_index(
    request: FitsIndexRebuildRequest,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> FitsIndexRebuildResponse:
    entity_reference = request.entity_id or request.entity_external_id
    try:
        result = FitsContainerReader(db).rebuild_index_from_current_fits(entity_reference)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    audit_logger.log(
        INDEX_REBUILT,
        metadata={
            "source": "current_fits_containers",
            "entity_reference": entity_reference,
            "indexed_entity_count": result["indexed_entity_count"],
            "skipped_entity_count": result["skipped_entity_count"],
        },
    )
    return FitsIndexRebuildResponse(**result)
