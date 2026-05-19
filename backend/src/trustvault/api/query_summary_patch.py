"""Runtime-safe query summary refinements.

This module keeps small summary behaviour changes out of the large query route
file. It is applied during API startup before the query router is registered.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any, Callable


SummaryRowFunc = Callable[[dict[str, Any]], dict[str, Any]]


def apply(query_module: ModuleType) -> None:
    """Enable AI narrative summaries for completeness-style query results.

    Missing-evidence queries now correctly execute as ``completeness_rules``.
    Those results are suitable for a short AI narrative, so they should not be
    forced down the deterministic summary path.
    """

    non_ai_sources = getattr(query_module, "NON_AI_SUMMARY_SOURCES", set())
    if isinstance(non_ai_sources, set):
        non_ai_sources.discard("completeness_rules")

    original_safe_summary_row = getattr(query_module, "_safe_summary_row", None)
    if not callable(original_safe_summary_row):
        return

    def _safe_summary_row_with_completeness(row: dict[str, Any]) -> dict[str, Any]:
        base = original_safe_summary_row(row)
        base.update(
            {
                "status": row.get("status"),
                "summary_type": row.get("summary_type"),
                "rule_key": row.get("rule_key"),
                "missing_evidence_type": row.get("missing_evidence_type"),
                "completeness_score": row.get("completeness_score"),
                "required_count": row.get("required_count"),
                "present_count": row.get("present_count"),
                "missing_count": row.get("missing_count"),
                "matched_evidence_object_id": row.get("matched_evidence_object_id"),
                "matched_filename": row.get("matched_filename"),
                "text_preview": row.get("snippet") or base.get("text_preview"),
            }
        )
        return {key: value for key, value in base.items() if value not in (None, "", [], {})}

    setattr(query_module, "_safe_summary_row", _safe_summary_row_with_completeness)
