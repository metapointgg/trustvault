import json
import re
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.ai.lm_studio import LmStudioAiProvider
from trustvault.audit.events import AI_SUMMARY_GENERATED, SEARCH_EXECUTED
from trustvault.audit.logger import AuditLogger
from trustvault.api.dependencies import get_audit_logger, get_current_user, get_database
from trustvault.core.app_settings import AppSettingsService
from trustvault.core.feature_services import TrustVaultFeatureService
from trustvault.core.fits_reader import FitsContainerReader
from trustvault.core.query_examples import ENRICHED_QUERY_SCENARIOS, QUERY_REGRESSION_TEST_CASES
from trustvault.core.query_interpreter import StructuredQuery, TrustVaultQueryInterpreter
from trustvault.db.models import Entity, EntityContainerVersion, FitsIndexEntry, User

router = APIRouter(prefix="/api/v1/query", tags=["query"])


class InterpretRequest(BaseModel):
    query: str = Field(min_length=1)
    entity_external_id: str | None = None
    mode: str = Field(default="auto", pattern="^(deterministic|ai|auto)$")


class ExecuteRequest(BaseModel):
    query: str = Field(min_length=1)
    entity_external_id: str | None = None
    limit: int = Field(default=50, ge=1, le=500)
    mode: str = Field(default="auto", pattern="^(deterministic|ai|auto)$")
    include_ai_summary: bool = False


SCENARIOS: list[dict[str, Any]] = ENRICHED_QUERY_SCENARIOS

STOP_WORDS = {
    "show", "me", "all", "the", "for", "of", "and", "or", "in", "to", "a", "an", "use", "trustvault",
    "evidence", "documentation", "documents", "document", "client", "clients", "customer", "customers", "entity", "entities", "who", "are", "is", "with",
}
ONBOARDING_CATEGORIES = {"customer_documents", "identity", "proof_of_address", "source_of_wealth", "cdd_review", "communications"}
NON_AI_SUMMARY_SOURCES = {"entity_metadata", "archive_status", "payload_metadata", "completeness_rules"}
DETERMINISTIC_AUTO_CAPABILITIES = {"archive_status", "entity_discovery", "entity_summary", "payload_metadata", "completeness_check"}
MISSING_INTENT_PHRASES = (
    "missing",
    "without",
    "do not have",
    "does not have",
    "don't have",
    "has no",
    "have no",
    "not have",
    "not present",
    "not provided",
    "outstanding",
    "incomplete",
)
EVIDENCE_TYPE_ALIASES: dict[str, tuple[str, ...]] = {
    "proof_of_address": ("proof of address", "poa", "address evidence", "address verification", "utility bill"),
    "source_of_wealth": ("source of wealth", "sow", "wealth evidence"),
    "source_of_funds": ("source of funds", "sof", "funds evidence"),
    "passport": ("passport", "identity document", "identity evidence", "id evidence"),
    "screening": ("screening", "pep", "sanctions", "adverse media"),
}


# The remainder of this module is intentionally imported from the repository copy.
# This file header is maintained by GitHub automation; do not edit below this line without preserving existing route logic.
