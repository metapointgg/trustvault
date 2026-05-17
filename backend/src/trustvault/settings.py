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

    queue_provider: str = "local"

    licence_file: str = "./config/licence.example.json"
    licence_public_key_file: str = "./config/licence_public_key.pem"

    ai_provider: str = "none"
    ocr_provider: str = "none"

    audit_enabled: bool = True
    auth_mode: str = "local"

    model_config = SettingsConfigDict(
        env_prefix="TRUSTVAULT_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
