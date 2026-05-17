from trustvault.settings import Settings, get_settings
from trustvault.storage.base import StorageProvider
from trustvault.storage.local import LocalFilesystemStorage


def get_storage_provider(settings: Settings | None = None) -> StorageProvider:
    settings = settings or get_settings()
    provider = settings.storage_provider.lower()
    if provider == "local":
        return LocalFilesystemStorage(settings.local_storage_root)
    if provider == "s3":
        from trustvault.storage.s3 import S3Storage

        return S3Storage(region_name=settings.aws_region)
    if provider in {"azure", "azure_blob", "blob"}:
        from trustvault.storage.azure_blob import AzureBlobStorage

        return AzureBlobStorage(account_url=settings.azure_storage_account_url)
    raise ValueError(f"Unsupported storage provider: {settings.storage_provider}")


def bucket_for_logical_name(logical_bucket: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    provider = settings.storage_provider.lower()
    if provider == "s3":
        mapping = {
            "source-imports": settings.s3_source_bucket,
            "fits-containers": settings.s3_fits_bucket,
            "derived-reports": settings.s3_export_bucket,
            "export-packs": settings.s3_export_bucket,
        }
        return mapping.get(logical_bucket, logical_bucket)
    if provider in {"azure", "azure_blob", "blob"}:
        mapping = {
            "source-imports": settings.azure_source_container,
            "fits-containers": settings.azure_fits_container,
            "derived-reports": settings.azure_export_container,
            "export-packs": settings.azure_export_container,
        }
        return mapping.get(logical_bucket, logical_bucket)
    return logical_bucket
