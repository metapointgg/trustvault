from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from pathlib import PurePosixPath

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
    filename: str | None
    preview_kind: str
    text_preview: str | None
    safe_preview: str | None
    size_bytes: int
    view_url: str
    download_url: str
    metadata: dict


@dataclass(frozen=True)
class EvidencePayload:
    evidence_object_id: str
    filename: str
    content_type: str
    data: bytes


class EvidencePreviewService:
    def __init__(self, db: Session):
        self.db = db
        settings = get_settings()
        self.local_storage = LocalFilesystemStorage(settings.local_storage_root)

    def preview(self, evidence_object_id: str, max_chars: int = 4000) -> EvidencePreview:
        evidence, data, filename, content_type = self._load_payload(evidence_object_id)
        preview_kind = self._preview_kind(filename, content_type)
        text_preview = self._text_preview(data, preview_kind, content_type, max_chars)
        metadata = dict(evidence.metadata_json or {})
        if preview_kind == "eml":
            metadata = {**metadata, **self._email_metadata(data)}

        return EvidencePreview(
            evidence_object_id=str(evidence.id),
            entity_id=str(evidence.entity_id),
            object_type=evidence.object_type,
            source_system=evidence.source_system,
            storage_uri=evidence.storage_uri,
            sha256=evidence.sha256,
            content_type=content_type,
            filename=filename,
            preview_kind=preview_kind,
            text_preview=text_preview,
            safe_preview=text_preview,
            size_bytes=len(data),
            view_url=f"/api/v1/evidence/{evidence.id}/file",
            download_url=f"/api/v1/evidence/{evidence.id}/download",
            metadata=metadata,
        )

    def payload(self, evidence_object_id: str) -> EvidencePayload:
        evidence, data, filename, content_type = self._load_payload(evidence_object_id)
        return EvidencePayload(
            evidence_object_id=str(evidence.id),
            filename=filename,
            content_type=content_type,
            data=data,
        )

    def _load_payload(self, evidence_object_id: str) -> tuple[EvidenceObject, bytes, str, str]:
        evidence = self.db.get(EvidenceObject, evidence_object_id)
        if evidence is None:
            raise ValueError("Evidence object not found")

        parsed = parse_storage_uri(evidence.storage_uri)
        if parsed.provider != "local":
            raise ValueError(f"Preview is not yet implemented for provider: {parsed.provider}")

        data = self.local_storage.get_bytes(parsed.bucket, parsed.key)
        filename = str((evidence.metadata_json or {}).get("filename") or PurePosixPath(parsed.key).name or evidence.id)
        content_type = evidence.content_type or self._guess_content_type(filename)
        return evidence, data, filename, content_type

    def _preview_kind(self, filename: str, content_type: str | None) -> str:
        lower_name = filename.lower()
        lower_type = (content_type or "").lower()
        if lower_type == "application/pdf" or lower_name.endswith(".pdf"):
            return "pdf"
        if lower_type.startswith("image/") or lower_name.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
            return "image"
        if lower_type in {"message/rfc822", "application/eml"} or lower_name.endswith(".eml"):
            return "eml"
        if lower_type.startswith("text/") or lower_name.endswith((".txt", ".csv", ".json", ".md", ".xml")):
            return "text"
        return "binary"

    def _guess_content_type(self, filename: str) -> str:
        lower = filename.lower()
        if lower.endswith(".pdf"):
            return "application/pdf"
        if lower.endswith((".jpg", ".jpeg")):
            return "image/jpeg"
        if lower.endswith(".png"):
            return "image/png"
        if lower.endswith(".gif"):
            return "image/gif"
        if lower.endswith(".webp"):
            return "image/webp"
        if lower.endswith(".eml"):
            return "message/rfc822"
        if lower.endswith(".json"):
            return "application/json"
        return "text/plain" if lower.endswith((".txt", ".md", ".csv")) else "application/octet-stream"

    def _text_preview(self, data: bytes, preview_kind: str, content_type: str | None, max_chars: int) -> str | None:
        if preview_kind == "eml":
            return self._email_text_preview(data, max_chars)
        if preview_kind == "text" or (content_type or "").startswith("text/"):
            return data.decode("utf-8", errors="replace")[:max_chars]
        return None

    def _email_metadata(self, data: bytes) -> dict:
        try:
            message = BytesParser(policy=policy.default).parsebytes(data)
            return {
                "email_subject": message.get("subject"),
                "email_from": message.get("from"),
                "email_to": message.get("to"),
                "email_date": message.get("date"),
            }
        except Exception:
            return {}

    def _email_text_preview(self, data: bytes, max_chars: int) -> str:
        try:
            message = BytesParser(policy=policy.default).parsebytes(data)
            parts = [
                f"Subject: {message.get('subject', '')}",
                f"From: {message.get('from', '')}",
                f"To: {message.get('to', '')}",
                f"Date: {message.get('date', '')}",
                "",
            ]
            body = ""
            if message.is_multipart():
                for part in message.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_content()
                        break
            elif message.get_content_type() == "text/plain":
                body = message.get_content()
            else:
                body = data.decode("utf-8", errors="replace")
            parts.append(str(body))
            return "\n".join(parts)[:max_chars]
        except Exception:
            return data.decode("utf-8", errors="replace")[:max_chars]
