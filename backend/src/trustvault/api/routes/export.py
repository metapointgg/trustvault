import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from trustvault.audit.events import EVIDENCE_PACK_EXPORTED, EVIDENCE_PREVIEWED
from trustvault.audit.logger import AuditLogger
from trustvault.api.dependencies import get_audit_logger, get_database
from trustvault.core.fits_reader import FitsContainerReader
from trustvault.core.storage_uri import parse_storage_uri
from trustvault.db.models import EntityContainerVersion
from trustvault.settings import get_settings
from trustvault.storage.local import LocalFilesystemStorage

router = APIRouter(prefix="/api/v1/export", tags=["export"])


def _container(db: Session, container_version_id: str) -> EntityContainerVersion:
    try:
        parsed_id = uuid.UUID(container_version_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid container version id") from exc
    container = db.get(EntityContainerVersion, parsed_id)
    if container is None:
        raise HTTPException(status_code=404, detail="Container version not found")
    if not container.storage_uri.lower().endswith(".fits"):
        raise HTTPException(status_code=400, detail="Container version is not a FITS archive")
    return container


def _container_bytes(container: EntityContainerVersion) -> bytes:
    parsed = parse_storage_uri(container.storage_uri)
    if parsed.provider != "local":
        raise HTTPException(status_code=501, detail=f"Download not implemented for provider: {parsed.provider}")
    return LocalFilesystemStorage(get_settings().local_storage_root).get_bytes(parsed.bucket, parsed.key)


@router.get("/containers/{container_version_id}/fits")
def download_fits_archive(
    container_version_id: str,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> Response:
    container = _container(db, container_version_id)
    data = _container_bytes(container)
    audit_logger.log(
        EVIDENCE_PACK_EXPORTED,
        entity_ids=[str(container.entity_id)],
        export_path=container.storage_uri,
        metadata={
            "export_type": "fits_archive_download",
            "container_version_id": str(container.id),
            "sha256": container.sha256,
            "size_bytes": container.size_bytes,
            "source_of_truth": "FITS archive",
        },
    )
    filename = container.storage_uri.split("/")[-1]
    return Response(
        content=data,
        media_type="application/fits",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-TrustVault-SHA256": container.sha256,
        },
    )


@router.get("/containers/{container_version_id}/manifest")
def get_fits_manifest(container_version_id: str, db: Session = Depends(get_database)) -> dict[str, Any]:
    container = _container(db, container_version_id)
    return container.manifest_json


@router.get("/containers/{container_version_id}/hash-report")
def get_fits_hash_report(container_version_id: str, db: Session = Depends(get_database)) -> dict[str, Any]:
    container = _container(db, container_version_id)
    return container.hash_report_json


@router.get("/containers/{container_version_id}/inspect")
def inspect_fits_archive(
    container_version_id: str,
    db: Session = Depends(get_database),
    audit_logger: AuditLogger = Depends(get_audit_logger),
) -> dict[str, Any]:
    _container(db, container_version_id)
    result = FitsContainerReader(db).inspect_version(container_version_id)
    audit_logger.log(
        EVIDENCE_PREVIEWED,
        entity_ids=[result["entity_id"]],
        export_path=result["storage_uri"],
        metadata={"operation": "inspect_fits_archive", "container_version_id": container_version_id},
    )
    return result


@router.get("/status")
def export_status() -> dict[str, Any]:
    return {
        "export_model": "fits_native",
        "primary_export": "current_or_versioned_FITS_archive",
        "source_of_truth": "FITS container",
        "secondary_report_packs": "not_enabled_in_this_build",
    }
