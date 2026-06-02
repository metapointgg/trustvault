from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from trustvault.core.app_settings import AppSettingsService
from trustvault.core.industry_packs import get_industry_pack, list_industry_packs
from trustvault.db.models import AppSetting

_OVERRIDE_PREFIX = "industry_pack_override::"


class IndustryPackConfigService:
    """Database-backed overrides for shipped industry packs.

    The code-defined packs remain the defaults. Administrators can amend a pack in
    Settings; the amended JSON is stored as an AppSetting override and used by the
    query vocabulary resolver.
    """

    def __init__(self, db: Session):
        self.db = db

    def list_packs(self) -> dict[str, Any]:
        values = AppSettingsService(self.db).effective_values()
        active_key = str(values.get("client_industry") or "financial_services")
        packs: list[dict[str, Any]] = []
        for item in list_industry_packs():
            pack = self.get_pack(str(item["key"]))
            packs.append(
                {
                    "key": pack.get("key"),
                    "label": pack.get("label"),
                    "description": pack.get("description"),
                    "customised": self._override_row(str(item["key"])) is not None,
                }
            )
        return {"active_industry": active_key, "industry_packs": packs}

    def active_pack(self) -> dict[str, Any]:
        values = AppSettingsService(self.db).effective_values()
        return self.get_pack(str(values.get("client_industry") or "financial_services"))

    def get_pack(self, key: str | None) -> dict[str, Any]:
        normalised = self._normalise_key(key)
        row = self._override_row(normalised)
        if row is not None and isinstance(row.value_json, dict):
            pack = deepcopy(row.value_json.get("pack") or {})
            if pack.get("key"):
                pack["customised"] = True
                return pack
        pack = get_industry_pack(normalised).to_dict()
        pack["customised"] = False
        return pack

    def save_pack(self, industry_key: str, pack: dict[str, Any], *, updated_by_user_id: str | None = None) -> dict[str, Any]:
        normalised = self._normalise_key(industry_key)
        validated = self._validate_pack(pack, fallback_key=normalised)
        row = self._override_row(normalised)
        if row is None:
            row = AppSetting(
                key=self._override_key(normalised),
                value_json={"pack": validated},
                value_type="json",
                category="Industry packs",
                description=f"Custom industry pack override for {normalised}",
                is_secret=False,
                is_editable=True,
                updated_by_user_id=updated_by_user_id,
            )
            self.db.add(row)
        else:
            row.value_json = {"pack": validated}
            row.updated_by_user_id = updated_by_user_id
        self.db.commit()
        validated["customised"] = True
        return validated

    def reset_pack(self, industry_key: str) -> dict[str, Any]:
        normalised = self._normalise_key(industry_key)
        row = self._override_row(normalised)
        if row is not None:
            self.db.delete(row)
            self.db.commit()
        return self.get_pack(normalised)

    def _validate_pack(self, pack: dict[str, Any], *, fallback_key: str) -> dict[str, Any]:
        if not isinstance(pack, dict):
            raise ValueError("Industry pack must be a JSON object")
        key = self._normalise_key(str(pack.get("key") or fallback_key))
        output = {
            "key": key,
            "label": str(pack.get("label") or key.replace("_", " ").title()),
            "description": str(pack.get("description") or ""),
            "entity_type_terms": self._string_list(pack.get("entity_type_terms")),
            "vocabulary_lists": [],
            "requirement_groups": [],
        }
        for item in pack.get("vocabulary_lists") or []:
            if not isinstance(item, dict):
                continue
            output["vocabulary_lists"].append(
                {
                    "list_key": str(item.get("list_key") or item.get("key") or "").strip(),
                    "label": str(item.get("label") or item.get("list_key") or "").strip(),
                    "field_binding": item.get("field_binding") or None,
                    "value_type": str(item.get("value_type") or "string"),
                    "is_filterable": bool(item.get("is_filterable", True)),
                    "is_requirement_dimension": bool(item.get("is_requirement_dimension", False)),
                    "items": [
                        {
                            "canonical_value": str(value.get("canonical_value") or "").strip(),
                            "aliases": self._string_list(value.get("aliases")),
                        }
                        for value in (item.get("items") or [])
                        if isinstance(value, dict) and str(value.get("canonical_value") or "").strip()
                    ],
                }
            )
        for group in pack.get("requirement_groups") or []:
            if not isinstance(group, dict):
                continue
            output["requirement_groups"].append(
                {
                    "key": str(group.get("key") or "").strip(),
                    "label": str(group.get("label") or group.get("key") or "").strip(),
                    "aliases": self._string_list(group.get("aliases")),
                    "default_document_types": self._string_list(group.get("default_document_types")),
                }
            )
        return output

    def _string_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, tuple):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    def _normalise_key(self, key: str | None) -> str:
        return str(key or "financial_services").strip().lower().replace("-", "_")

    def _override_key(self, key: str) -> str:
        return f"{_OVERRIDE_PREFIX}{key}"

    def _override_row(self, key: str) -> AppSetting | None:
        return self.db.get(AppSetting, self._override_key(key))
