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

    auto_ingestion_enabled: bool = True
    auto_ingestion_poll_seconds: int = 10
    auto_ingestion_drop_folder: str = "./local-data/drop-folder/incoming"
    auto_ingestion_processing_folder: str = "./local-data/drop-folder/processing"
    auto_ingestion_processed_folder: str = "./local-data/drop-folder/processed"
    auto_ingestion_failed_folder: str = "./local-data/drop-folder/failed"
    auto_ingestion_strict_structure: bool = True
    auto_ingestion_rebuild_container: bool = True
    auto_ingestion_rebuild_index: bool = True
    categorisation_filename_document_type_map: str = (
        '{"passport":"Passport","id":"Passport","identity":"Passport","driving_licence":"Driving Licence",'
        '"drivers_license":"Driving Licence","proof_of_address":"Proof of Address","utility_bill":"Proof of Address",'
        '"council_tax":"Proof of Address","address":"Proof of Address","source_of_funds":"Source of Funds",'
        '"sof":"Source of Funds","source_of_wealth":"Source of Wealth","sow":"Source of Wealth","cdd":"CDD Review",'
        '"review":"CDD Review","periodic_review":"CDD Review","application":"Application","onboarding":"Application",'
        '"account_opening":"Application","screening":"Screening Evidence","sanctions":"Screening Evidence","pep":"Screening Evidence",'
        '"edd":"EDD Approval","enhanced_due_diligence":"EDD Approval","registry":"Company Registry Extract",'
        '"company_extract":"Company Registry Extract","beneficial_owner":"Beneficial Owner Evidence","ubo":"Beneficial Owner Evidence",'
        '"authorised_signatory":"Authorised Signatory ID","signatory":"Authorised Signatory ID","statement":"Monthly Statement",'
        '"bank_statement":"Monthly Statement","transaction_extract":"Transaction Extract","transactions":"Transaction Extract",'
        '"email":"Customer Correspondence","correspondence":"Customer Correspondence","letter":"Customer Correspondence",'
        '"customer":"Customer Metadata","metadata":"Customer Metadata","legacy":"Legacy Binary Payload","archive":"Legacy Binary Payload",'
        '"binary":"Legacy Binary Payload","organisation_chart":"Organisation Chart","organization_chart":"Organisation Chart",'
        '"shareholder_certificate":"Shareholder Certificate","certificate_of_incorporation":"Certificate of Incorporation"}'
    )
    categorisation_document_type_category_map: str = (
        '{"Passport":"Identity","Driving Licence":"Identity","Proof of Address":"Address",'
        '"Source of Funds":"Source of Funds","Source of Wealth":"Source of Wealth","CDD Review":"CDD",'
        '"Application":"Onboarding","Screening Evidence":"Screening","EDD Approval":"EDD",'
        '"Company Registry Extract":"Corporate","Beneficial Owner Evidence":"Corporate","Authorised Signatory ID":"Corporate",'
        '"Monthly Statement":"Statement","Transaction Extract":"Transaction","Customer Correspondence":"Correspondence",'
        '"Customer Metadata":"Customer Information","Legacy Binary Payload":"Legacy Evidence","Organisation Chart":"Corporate",'
        '"Shareholder Certificate":"Corporate","Certificate of Incorporation":"Corporate","Audit Events":"Audit"}'
    )

    model_config = SettingsConfigDict(
        env_prefix="TRUSTVAULT_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
