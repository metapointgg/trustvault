from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TrustVault"
    environment: str = "local"

    database_url: str = Field(
        default="postgresql+psycopg://trustvault:trustvault_dev_password@localhost:5432/trustvault"
    )

    storage_provider: str = "local"
    local_storage_root: str = "./local-data/storage"
    aws_region: str = "eu-west-1"
    s3_source_bucket: str = "trustvault-source-imports"
    s3_fits_bucket: str = "trustvault-fits-containers"
    s3_export_bucket: str = "trustvault-derived-reports"
    azure_storage_account_url: str | None = None
    azure_source_container: str = "source-imports"
    azure_fits_container: str = "fits-containers"
    azure_export_container: str = "derived-reports"

    queue_provider: str = "database"
    sqs_queue_url: str | None = None
    azure_service_bus_fully_qualified_namespace: str | None = None
    azure_service_bus_queue_name: str = "trustvault-jobs"
    azure_storage_queue_url: str | None = None

    licence_file: str = "./config/licence.example.json"
    licence_public_key_file: str = "./config/licence_public_key.pem"
    licence_enforcement_enabled: bool = False

    ai_provider: str = "none"
    lm_studio_base_url: str = "http://localhost:1234"
    lm_studio_model: str = "qwen/qwen3-vl-4b"
    lm_studio_query_model: str = "qwen/qwen3-vl-4b"
    azure_openai_endpoint: str | None = None
    azure_openai_deployment: str | None = None
    bedrock_model_id: str | None = None

    ocr_provider: str = "none"
    tesseract_command: str = "tesseract"

    audit_enabled: bool = True
    auth_mode: str = "local"  # local, oidc, disabled
    auth_required: bool = True
    auth_token_secret: str | None = None
    auth_token_ttl_minutes: int = 480
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    local_admin_email: str = "admin@trustvault.local"
    local_admin_password: str | None = None
    local_admin_display_name: str = "TrustVault Administrator"

    export_approval_required: bool = False

    model_config = SettingsConfigDict(
        env_prefix="TRUSTVAULT_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
