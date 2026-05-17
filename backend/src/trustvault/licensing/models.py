from datetime import date
from pydantic import BaseModel, Field


class CloudBinding(BaseModel):
    aws_account_id: str | None = None
    azure_tenant_id: str | None = None
    azure_subscription_id: str | None = None


class LicenceDocument(BaseModel):
    licence_id: str
    customer_name: str
    edition: str
    deployment_id: str
    valid_from: date
    valid_until: date
    grace_days: int = 0
    max_entities: int | None = None
    max_users: int | None = None
    max_storage_gb: int | None = None
    environment: str
    modules: list[str] = Field(default_factory=list)
    cloud_binding: CloudBinding = Field(default_factory=CloudBinding)
    signature: str | None = None


class LicenceCheckResult(BaseModel):
    state: str
    licence_id: str | None = None
    customer_name: str | None = None
    edition: str | None = None
    valid_until: date | None = None
    modules: list[str] = Field(default_factory=list)
    message: str
