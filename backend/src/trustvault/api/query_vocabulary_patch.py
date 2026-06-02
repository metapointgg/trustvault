from __future__ import annotations

from typing import Any

from trustvault.core.query_vocabulary import QueryVocabularyService


_PATCHED = False


def apply(query_module: Any) -> None:
    """Apply validated industry vocabulary matches to legacy query output.

    This is a bridge while TrustVault moves from the current legacy structured
    query shape to a fully generic filters/requirement query object. It avoids
    adding more hardcoded jurisdictions, departments, clinician names or document
    types to the deterministic interpreter.
    """

    global _PATCHED
    if _PATCHED:
        return

    original_interpret = query_module._interpret

    def patched_interpret(request: Any, db: Any) -> tuple[Any, dict[str, Any]]:
        structured, meta = original_interpret(request, db)
        service = QueryVocabularyService(db)
        resolved = service.legacy_structured_overrides(request.query)
        overrides = resolved.get("overrides") or {}
        meta["resolved_vocabulary"] = resolved.get("resolved_vocabulary")
        meta["vocabulary_overrides"] = overrides
        if not overrides:
            return structured, meta

        data = structured.to_dict()
        data.update({key: value for key, value in overrides.items() if value is not None})
        if data.get("entity_external_id"):
            data["scope"] = "entity"
        else:
            data["scope"] = "archive"
        if data.get("capability") == "completeness_check":
            data["execute_with"] = "fits_index"
        structured = query_module.StructuredQuery(**data)
        meta["structured_query_after_vocabulary"] = structured.to_dict()
        return structured, meta

    query_module._interpret = patched_interpret
    _PATCHED = True
