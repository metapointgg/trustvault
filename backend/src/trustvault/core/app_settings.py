from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.db.models import AppSetting
from trustvault.settings import Settings, get_settings


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    category: str
    value_type: str
    description: str
    editable: bool = True
    secret: bool = False


SETTING_DEFINITIONS: list[SettingDefinition] = [
    SettingDefinition("environment", "Runtime", "string", "Deployment environment label.", editable=False),
    SettingDefinition("storage_provider", "Storage", "string", "Storage provider: local, s3 or azure."),
    SettingDefinition("local_storage_root", "Storage", "string", "Local storage root used for local deployments."),
    SettingDefinition("queue_provider", "Queue", "string", "Queue provider: database, sqs or azure."),
    SettingDefinition("ai_provider", "AI", "string", "AI provider: none, lm_studio, azure_openai or bedrock."),
    SettingDefinition("lm_studio_base_url", "AI", "string", "LM Studio/OpenAI-compatible local endpoint."),
    SettingDefinition("lm_studio_query_model", "AI", "string", "Model used for query interpretation."),
    SettingDefinition("ocr_provider", "OCR", "string", "OCR provider: none, tesseract, sidecar or cloud provider."),
    SettingDefinition("tesseract_command", "OCR", "string", "Tesseract command path when local OCR is enabled."),
    SettingDefinition("auth_mode", "Auth", "string", "Authentication mode: local, oidc or disabled."),
    SettingDefinition("auth_required", "Auth", "bool", "Whether API authentication is enforced."),
    SettingDefinition("auth_token_ttl_minutes", "Auth", "int", "Local session token lifetime in minutes."),
    SettingDefinition("licence_enforcement_enabled", "Licence", "bool", "Whether module licence enforcement is active."),
    SettingDefinition("export_approval_required", "Export", "bool", "Whether exports require approval before generation."),
    SettingDefinition("auto_ingestion_enabled", "Automatic ingestion", "bool", "Enable automatic source-folder ZIP ingestion."),
    SettingDefinition("auto_ingestion_poll_seconds", "Automatic ingestion", "int", "Worker polling interval for source-folder ZIP ingestion."),
    SettingDefinition("auto_ingestion_drop_folder", "Automatic ingestion", "string", "Folder where customer ZIPs are dropped for ingestion."),
    SettingDefinition("auto_ingestion_processing_folder", "Automatic ingestion", "string", "Folder used while a ZIP is being processed."),
    SettingDefinition("auto_ingestion_processed_folder", "Automatic ingestion", "string", "Folder where successfully ingested ZIPs are moved."),
    SettingDefinition("auto_ingestion_failed_folder", "Automatic ingestion", "string", "Folder where failed ZIPs are moved."),
    SettingDefinition("auto_ingestion_strict_structure", "Automatic ingestion", "bool", "Validate required source folder structure before ingestion."),
    SettingDefinition("auto_ingestion_rebuild_container", "Automatic ingestion", "bool", "Rebuild affected customer FITS archive after automatic ingestion."),
    SettingDefinition("auto_ingestion_rebuild_index", "Automatic ingestion", "bool", "Rebuild affected customer index rows after automatic ingestion."),
    SettingDefinition("auth_token_secret", "Secrets", "string", "Local token signing secret. Managed via environment/secret manager only.", editable=False, secret=True),
    SettingDefinition("local_admin_password", "Secrets", "string", "Initial bootstrap verifier. Managed via environment/secret manager only.", editable=False, secret=True),
]

DEFINITION_BY_KEY = {definition.key: definition for definition in SETTING_DEFINITIONS}


class AppSettingsService:
    def __init__(self, db: Session):
        self.db = db
        self.environment_settings = get_settings()

    def list_settings(self) -> dict[str, Any]:
        stored = {row.key: row for row in self.db.scalars(select(AppSetting)).all()}
        items = [self._present_setting(definition, stored.get(definition.key)) for definition in SETTING_DEFINITIONS]
        categories: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            categories.setdefault(item["category"], []).append(item)
        return {"categories": categories, "settings": items}

    def update_settings(self, updates: dict[str, Any], *, updated_by_user_id: str | None = None) -> dict[str, Any]:
        changed: list[str] = []
        for key, raw_value in updates.items():
            definition = DEFINITION_BY_KEY.get(key)
            if definition is None or not definition.editable or definition.secret:
                continue
            value = self._coerce_value(raw_value, definition.value_type)
            row = self.db.get(AppSetting, key)
            if row is None:
                row = AppSetting(
                    key=key,
                    value_json={"value": value},
                    value_type=definition.value_type,
                    category=definition.category,
                    description=definition.description,
                    is_secret=definition.secret,
                    is_editable=definition.editable,
                    updated_by_user_id=updated_by_user_id,
                )
                self.db.add(row)
            else:
                row.value_json = {"value": value}
                row.value_type = definition.value_type
                row.category = definition.category
                row.description = definition.description
                row.is_secret = definition.secret
                row.is_editable = definition.editable
                row.updated_by_user_id = updated_by_user_id
            changed.append(key)
        self.db.commit()
        return {"updated_count": len(changed), "updated_keys": changed, **self.list_settings()}

    def effective_value(self, key: str) -> Any:
        definition = DEFINITION_BY_KEY.get(key)
        if definition is None:
            raise KeyError(key)
        row = self.db.get(AppSetting, key)
        if row is not None and isinstance(row.value_json, dict) and "value" in row.value_json:
            return row.value_json["value"]
        return getattr(self.environment_settings, key)

    def effective_values(self) -> dict[str, Any]:
        return {definition.key: self.effective_value(definition.key) for definition in SETTING_DEFINITIONS if not definition.secret}

    def _present_setting(self, definition: SettingDefinition, row: AppSetting | None) -> dict[str, Any]:
        env_value = getattr(self.environment_settings, definition.key)
        if definition.secret:
            value = "********" if env_value else None
            source = "environment" if env_value else "unset"
        elif row is not None and isinstance(row.value_json, dict) and "value" in row.value_json:
            value = row.value_json["value"]
            source = "database"
        else:
            value = env_value
            source = "environment"
        return {
            "key": definition.key,
            "category": definition.category,
            "value": value,
            "environment_value": "********" if definition.secret and env_value else env_value,
            "value_type": definition.value_type,
            "description": definition.description,
            "editable": definition.editable,
            "secret": definition.secret,
            "source": source,
            "updated_at": row.updated_at if row is not None else None,
            "updated_by_user_id": row.updated_by_user_id if row is not None else None,
        }

    def _coerce_value(self, raw_value: Any, value_type: str) -> Any:
        if value_type == "bool":
            if isinstance(raw_value, bool):
                return raw_value
            return str(raw_value).strip().lower() in {"true", "1", "yes", "y", "on"}
        if value_type == "int":
            return int(raw_value)
        return str(raw_value)
