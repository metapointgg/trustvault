import json
import urllib.error
import urllib.request
from typing import Any

from trustvault.ai.base import AiProvider, AiResult
from trustvault.settings import get_settings


class LmStudioAiProvider(AiProvider):
    def __init__(self, base_url: str, model: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model or get_settings().lm_studio_query_model

    def expand_query(self, query: str) -> AiResult:
        prompt = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Generate concise evidence archive search terms. Return JSON only."},
                {"role": "user", "content": json.dumps({"query": query, "schema": {"terms": ["string"]}})},
            ],
            "temperature": 0.1,
        }
        payload, warning = self._post_chat(prompt)
        if warning:
            return AiResult(text=query, provider="lm_studio", model=self.model, warnings=[warning])
        content = self._content(payload)
        data = self._extract_json(content) or {}
        terms = data.get("terms") if isinstance(data, dict) else None
        if isinstance(terms, list) and terms:
            return AiResult(text=" ".join(str(term) for term in terms[:12]), provider="lm_studio", model=payload.get("model", self.model), data={"terms": terms})
        return AiResult(text=query, provider="lm_studio", model=payload.get("model", self.model), warnings=["No valid terms returned"])

    def interpret_query(self, query: str, deterministic_query: dict[str, Any], context: dict[str, Any] | None = None) -> AiResult:
        prompt = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You convert regulated evidence archive questions into strict JSON. "
                        "Return JSON only. Never generate SQL. Never invent entity IDs, document types or categories. "
                        "FITS containers and indexes are the source of truth; your role is interpretation only."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "user_query": query,
                            "deterministic_interpretation": deterministic_query,
                            "context": context or {},
                            "controlled_vocabulary": {
                                "scopes": ["archive", "entity"],
                                "capabilities": ["evidence_search", "completeness_check", "entity_discovery", "archive_status", "payload_metadata"],
                                "execute_with": ["fits_index", "direct_fits"],
                                "risk_rating": ["High", "Medium", "Low"],
                                "jurisdiction": ["Guernsey", "Jersey", "United Kingdom", "Isle of Man", "Other"],
                                "categories": ["customer_documents", "identity", "proof_of_address", "source_of_wealth", "source_of_funds", "cdd_review", "communications", "screening"],
                                "document_types": ["passport", "identity_document", "proof_of_address", "source_of_wealth", "source_of_funds", "cdd_risk_review", "screening", "email", "account_opening_application"],
                            },
                            "hard_rules": [
                                "Onboarding is a lifecycle snapshot, not a document type.",
                                "For onboarding, set snapshot_id to ONBOARDING and do not set document_types to ONBOARDING.",
                                "If an entity ID is not present in the user query or selected context, keep entity_external_id null.",
                                "Selected-entity evidence search uses direct_fits; archive/cohort search uses fits_index.",
                            ],
                            "output_schema": {
                                "scope": "archive|entity",
                                "capability": "evidence_search|completeness_check|entity_discovery|archive_status|payload_metadata",
                                "entity_external_id": None,
                                "risk_rating": None,
                                "jurisdiction": None,
                                "snapshot_id": None,
                                "document_types": [],
                                "categories": [],
                                "search_terms": [],
                                "completeness_only": False,
                                "missing_evidence_type": None,
                                "execute_with": "fits_index|direct_fits",
                                "confidence": 0.0,
                                "reason": "brief explanation",
                            },
                        },
                        default=str,
                    ),
                },
            ],
            "temperature": 0.1,
        }
        payload, warning = self._post_chat(prompt)
        if warning:
            return AiResult(text="", provider="lm_studio", model=self.model, data=deterministic_query, warnings=[warning])
        content = self._content(payload)
        data = self._extract_json(content)
        if not isinstance(data, dict):
            return AiResult(text=content, provider="lm_studio", model=payload.get("model", self.model), data=deterministic_query, warnings=["AI did not return valid JSON; deterministic interpretation used"])
        return AiResult(text=content, provider="lm_studio", model=payload.get("model", self.model), data=data)

    def summarise_evidence(self, evidence: list[dict], question: str | None = None) -> AiResult:
        compact_evidence = self._compact_evidence(evidence, max_rows=8, max_text_chars=260)
        payload, warning = self._post_chat(self._summary_prompt(compact_evidence, question, terse=False))
        if warning and self._looks_like_context_error(warning):
            tiny_evidence = self._compact_evidence(evidence, max_rows=5, max_text_chars=160)
            payload, warning = self._post_chat(self._summary_prompt(tiny_evidence, question, terse=True))
        if warning:
            fallback = self._deterministic_summary(compact_evidence)
            return AiResult(text=fallback, provider="lm_studio", model=self.model, warnings=[warning, "Deterministic fallback summary returned because LM Studio rejected the prompt"])
        return AiResult(text=self._content(payload), provider="lm_studio", model=payload.get("model", self.model))

    def summarise_entity_profile(self, profile: dict[str, Any], question: str | None = None) -> AiResult:
        compact_profile = self._compact_entity_profile(profile)
        payload, warning = self._post_chat(self._entity_profile_prompt(compact_profile, question, terse=False))
        if warning and self._looks_like_context_error(warning):
            compact_profile = self._compact_entity_profile(profile, max_evidence=8, max_excerpt_chars=180)
            payload, warning = self._post_chat(self._entity_profile_prompt(compact_profile, question, terse=True))
        if warning:
            fallback = self._deterministic_entity_profile_summary(compact_profile)
            return AiResult(text=fallback, provider="lm_studio", model=self.model, warnings=[warning, "Deterministic entity profile fallback returned because LM Studio rejected the prompt"])
        return AiResult(text=self._content(payload), provider="lm_studio", model=payload.get("model", self.model))

    def _summary_prompt(self, evidence: list[dict[str, Any]], question: str | None, *, terse: bool) -> dict[str, Any]:
        system = (
            "You write a short narrative summary for a TrustVault search results page. "
            "The evidence rows are already displayed to the user in a data grid, so do NOT reproduce the grid. "
            "Never output a numbered list of individual evidence rows. Never list every filename, SHA-256 hash, object ID or row. "
            "Use only the supplied evidence. Do not invent facts. Entity metadata is authoritative. "
            "OCR/extracted text may contain recognition errors, so present it cautiously. "
            "Summarise the overall result set in one short paragraph followed by at most three concise bullets. "
            "Mention only high-level patterns: number of entities, main evidence categories, document types, gaps or limitations. "
            "End with: Preserved FITS evidence and payload hashes remain the source of truth."
        )
        if terse:
            system = (
                "Summarise the TrustVault search result set in one short paragraph and at most 3 bullets. "
                "Do not reproduce rows. Do not use numbered evidence lists. Do not include SHA-256 hashes. "
                "Use Entity terminology. End with: Preserved FITS evidence and payload hashes remain the source of truth."
            )
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question,
                            "row_count": len(evidence),
                            "sample_rows_for_context_only_not_for_listing": evidence,
                            "instruction": "Provide a concise narrative overview only. The data grid will display the rows separately.",
                        },
                        default=str,
                        separators=(",", ":"),
                    ),
                },
            ],
            "temperature": 0.1,
            "max_tokens": 420,
        }

    def _entity_profile_prompt(self, profile: dict[str, Any], question: str | None, *, terse: bool) -> dict[str, Any]:
        system = (
            "You summarise preserved financial-services evidence for compliance and operations users. "
            "Use only the supplied TrustVault entity profile, metadata and evidence excerpts. Do not invent facts. "
            "Treat entity metadata, object IDs, filenames, categories, document types and SHA-256 values as authoritative. "
            "OCR and extracted text may contain recognition errors, so describe excerpts as supporting evidence only. "
            "If evidence is incomplete, missing or inconsistent, say so clearly. Use Entity terminology, not Customer terminology."
        )
        instruction = (
            "Write a natural-language entity summary covering: 1) entity identity and risk context, 2) current FITS archive status, "
            "3) evidence coverage by category/document type, 4) notable evidence examples, 5) completeness, retention, extraction and integrity observations, "
            "and 6) limitations or follow-up actions. Do not list every row. End with a source-of-truth note."
        )
        if terse:
            instruction = "Write one concise paragraph and up to five bullets covering risk context, archive status, evidence coverage, gaps and limitations. End with a source-of-truth note."
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps({"question": question, "entity_profile": profile, "instruction": instruction}, default=str, separators=(",", ":"))},
            ],
            "temperature": 0.1,
            "max_tokens": 1200,
        }

    def _compact_entity_profile(self, profile: dict[str, Any], *, max_evidence: int = 16, max_excerpt_chars: int = 320) -> dict[str, Any]:
        evidence_rows = list(profile.get("representative_evidence") or [])[:max_evidence]
        compact_evidence = []
        for row in evidence_rows:
            text = str(row.get("text_preview") or row.get("snippet") or row.get("text_content") or "")[:max_excerpt_chars]
            compact_evidence.append(
                {
                    "object_id": row.get("evidence_object_id") or row.get("object_id") or row.get("id"),
                    "filename": row.get("filename"),
                    "category": row.get("category"),
                    "document_type": row.get("document_type") or row.get("object_type"),
                    "source_system": row.get("source_system"),
                    "retention_class": row.get("retention_class"),
                    "legal_hold_status": row.get("legal_hold_status"),
                    "sha256": row.get("sha256"),
                    "excerpt": text,
                }
            )
        return {
            "entity": profile.get("entity") or {},
            "container": profile.get("container") or {},
            "evidence_count": profile.get("evidence_count"),
            "counts_by_category": profile.get("counts_by_category") or {},
            "counts_by_document_type": profile.get("counts_by_document_type") or {},
            "completeness": profile.get("completeness") or {},
            "retention": profile.get("retention") or {},
            "extraction": profile.get("extraction") or {},
            "integrity": profile.get("integrity") or {},
            "representative_evidence": compact_evidence,
        }

    def _compact_evidence(self, evidence: list[dict], *, max_rows: int, max_text_chars: int) -> list[dict[str, Any]]:
        compact: list[dict[str, Any]] = []
        for row in self._deduplicate_evidence_rows(evidence)[:max_rows]:
            text = str(row.get("text_preview") or row.get("snippet") or "")
            compact.append(
                {
                    "entity": row.get("entity_external_id"),
                    "name": row.get("entity_display_name"),
                    "file": row.get("filename"),
                    "category": row.get("category"),
                    "type": row.get("document_type") or row.get("object_type"),
                    "jurisdiction": row.get("jurisdiction"),
                    "risk": row.get("risk_rating"),
                    "text": text[:max_text_chars],
                }
            )
        return compact

    def _deduplicate_evidence_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unique: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, str]] = set()
        for row in rows:
            entity_id = str(row.get("entity_external_id") or row.get("entity_id") or "")
            object_id = str(row.get("evidence_object_id") or row.get("object_id") or row.get("id") or "")
            filename = str(row.get("filename") or "")
            document_type = str(row.get("document_type") or row.get("object_type") or "")
            sha = str(row.get("sha256") or "")[:16]
            key = (entity_id.lower(), object_id.lower() if object_id else filename.lower(), document_type.lower(), sha.lower())
            if key in seen:
                continue
            seen.add(key)
            unique.append(row)
        return unique

    def _deterministic_summary(self, evidence: list[dict[str, Any]]) -> str:
        entities = sorted({str(row.get("entity") or "") for row in evidence if row.get("entity")})
        categories = sorted({str(row.get("category") or "") for row in evidence if row.get("category")})
        document_types = sorted({str(row.get("type") or "") for row in evidence if row.get("type")})
        lines = [f"TrustVault found {len(evidence)} representative evidence rows" + (f" across {len(entities)} entit{'y' if len(entities) == 1 else 'ies'}" if entities else "") + "."]
        if categories:
            lines.append(f"Document categories represented include: {', '.join(categories[:6])}.")
        if document_types:
            lines.append(f"Document types represented include: {', '.join(document_types[:8])}.")
        lines.append("Use the data grid for the full row-level evidence list, filenames, previews and SHA-256 verification.")
        lines.append("Preserved FITS evidence and payload hashes remain the source of truth.")
        return "\n".join(lines)

    def _deterministic_entity_profile_summary(self, profile: dict[str, Any]) -> str:
        entity = profile.get("entity") or {}
        container = profile.get("container") or {}
        completeness = profile.get("completeness") or {}
        retention = profile.get("retention") or {}
        extraction = profile.get("extraction") or {}
        integrity = profile.get("integrity") or {}
        evidence = profile.get("representative_evidence") or []
        lines = [
            f"Entity {entity.get('external_id') or entity.get('entity_external_id') or '-'} ({entity.get('display_name') or entity.get('entity_display_name') or '-'}) is recorded with risk rating {entity.get('risk_rating') or '-'} and jurisdiction {entity.get('jurisdiction') or '-'}.",
            f"The entity has {profile.get('evidence_count') or 0} evidence object(s) in the current evidence profile.",
        ]
        if container:
            lines.append(f"Current FITS container status: version={container.get('version_number') or '-'}, storage_uri={container.get('storage_uri') or '-'}, sha256={container.get('sha256') or '-'}." )
        if profile.get("counts_by_category"):
            lines.append("Evidence categories: " + ", ".join(f"{key} ({value})" for key, value in (profile.get("counts_by_category") or {}).items()) + ".")
        if profile.get("counts_by_document_type"):
            lines.append("Document types: " + ", ".join(f"{key} ({value})" for key, value in (profile.get("counts_by_document_type") or {}).items()) + ".")
        if evidence:
            lines.append("Representative files: " + ", ".join(str(row.get("filename") or row.get("object_id") or "-") for row in evidence[:6]) + ".")
        if completeness:
            lines.append(f"Completeness: score={completeness.get('score')}, missing={completeness.get('missing_count')}.")
        if retention:
            lines.append(f"Retention/legal hold: legal_holds={retention.get('legal_hold_count')}, deletion_eligible={retention.get('deletion_eligible_count')}.")
        if extraction:
            lines.append(f"Extraction: text_rows={extraction.get('text_row_count')}, character_count={extraction.get('character_count')}.")
        if integrity:
            lines.append(f"Integrity: status={integrity.get('overall_status')}, failed_payloads={integrity.get('failed_payload_count')}.")
        lines.append("Preserved FITS evidence and payload hashes remain the source of truth.")
        return "\n".join(lines)

    def _looks_like_context_error(self, warning: str) -> bool:
        value = warning.lower()
        return "context length" in value or "tokens to keep" in value or ("prompt" in value and "larger context" in value)

    def _post_chat(self, payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        url = f"{self.base_url}/v1/chat/completions" if not self.base_url.endswith("/v1") else f"{self.base_url}/chat/completions"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8")), None
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:1000]
            return {}, f"HTTP Error {exc.code}: {exc.reason}; response={body}"
        except Exception as exc:
            return {}, str(exc)

    def _content(self, payload: dict[str, Any]) -> str:
        choice = (payload.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        return message.get("content") or message.get("reasoning_content") or ""

    def _extract_json(self, text: str) -> dict[str, Any] | None:
        text = text.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
        return None
