from dataclasses import dataclass

from sqlalchemy.orm import Session

from trustvault.core.storage_uri import parse_storage_uri
from trustvault.db.models import EvidenceObject
from trustvault.settings import get_settings
from trustvault.storage.local import LocalFilesystemStorage


@dataclass(frozen=True)
class EvidencePreview:
    evidence_object_id: str
    entity_id: str
    object_type: str
    source_system: str
    storage_uri: str
    sha256: str
    content_type: str | None
    text_preview: str | None
    size_bytes: int


class EvidencePreviewService:
    def __init__(self, db: Session):
        self.db = db
        settings = get_settings()
        self.local_storage = LocalFilesystemStorage(settings.local_storage_root)

    def preview(self, evidence_object_id: str, max_chars: int = 4000) -> EvidencePreview:
        evidence = self.db.get(EvidenceObject, evidence_object_id)
        if evidence is None:
            raise ValueError("Evidence object not found")

        parsed = parse_storage_uri(evidence.storage_uri)
        if parsed.provider != "local":
            raise ValueError(f"Preview is not yet implemented for provider: {parsed.provider}")

        data = self.local_storage.get_bytes(parsed.bucket, parsed.key)
        text_preview = None
        if (evidence.content_type or "").startswith("text/"):
            text_preview = data.decode("utf-8", errors="replace")[:max_chars]

        return EvidencePreview(
            evidence_object_id=str(evidence.id),
            entity_id=str(evidence.entity_id),
            object_type=evidence.object_type,
            source_system=evidence.source_system,
            storage_uri=evidence.storage_uri,
            sha256=evidence.sha256,
            content_type=evidence.content_type,
            text_preview=text_preview,
            size_bytes=len(data),
        )
