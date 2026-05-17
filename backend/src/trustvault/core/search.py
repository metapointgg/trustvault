from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.core.storage_uri import parse_storage_uri
from trustvault.db.models import Entity, EvidenceObject
from trustvault.settings import get_settings
from trustvault.storage.local import LocalFilesystemStorage


@dataclass(frozen=True)
class EvidenceSearchResult:
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
    match_source: str


class EvidenceSearchService:
    def __init__(self, db: Session):
        self.db = db
        settings = get_settings()
        self.local_storage = LocalFilesystemStorage(settings.local_storage_root)

    def search(self, query: str, limit: int = 50) -> list[EvidenceSearchResult]:
        normalised_query = query.strip().lower()
        if not normalised_query:
            return []

        rows = self.db.execute(
            select(EvidenceObject, Entity)
            .join(Entity, EvidenceObject.entity_id == Entity.id)
            .order_by(EvidenceObject.created_at.desc())
            .limit(500)
        ).all()

        results: list[EvidenceSearchResult] = []
        for evidence, entity in rows:
            searchable_parts = [
                entity.external_id,
                entity.display_name,
                evidence.object_type,
                evidence.source_system,
                evidence.storage_uri,
                str(evidence.metadata_json),
            ]
            match_source = "metadata"
            snippet = None

            text = self._try_read_text(evidence)
            if text:
                searchable_parts.append(text)
                if normalised_query in text.lower():
                    match_source = "content"
                    snippet = self._build_snippet(text, normalised_query)

            haystack = "\n".join(searchable_parts).lower()
            if normalised_query in haystack:
                results.append(
                    EvidenceSearchResult(
                        entity_id=str(entity.id),
                        entity_external_id=entity.external_id,
                        entity_display_name=entity.display_name,
                        evidence_object_id=str(evidence.id),
                        object_type=evidence.object_type,
                        source_system=evidence.source_system,
                        storage_uri=evidence.storage_uri,
                        sha256=evidence.sha256,
                        content_type=evidence.content_type,
                        snippet=snippet,
                        match_source=match_source,
                    )
                )

            if len(results) >= limit:
                break

        return results

    def _try_read_text(self, evidence: EvidenceObject) -> str | None:
        if not (evidence.content_type or "").startswith("text/"):
            return None

        parsed = parse_storage_uri(evidence.storage_uri)
        if parsed.provider != "local":
            return None

        try:
            return self.local_storage.get_bytes(parsed.bucket, parsed.key).decode("utf-8", errors="replace")
        except FileNotFoundError:
            return None

    def _build_snippet(self, text: str, normalised_query: str, window: int = 120) -> str:
        lower_text = text.lower()
        index = lower_text.find(normalised_query)
        if index < 0:
            return text[: window * 2]

        start = max(index - window, 0)
        end = min(index + len(normalised_query) + window, len(text))
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(text) else ""
        return f"{prefix}{text[start:end]}{suffix}"
