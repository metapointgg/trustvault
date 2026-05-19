import hashlib

from trustvault.storage.base import StorageProvider, StoredObject


class AzureBlobStorage(StorageProvider):
    def __init__(self, account_url: str | None):
        if not account_url:
            raise ValueError("azure_storage_account_url must be configured for Azure Blob storage")
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        self.client = BlobServiceClient(account_url=account_url, credential=DefaultAzureCredential())

    def put_bytes(self, bucket: str, key: str, data: bytes, content_type: str | None = None) -> StoredObject:
        blob_client = self.client.get_blob_client(container=bucket, blob=key)
        content_settings = None
        if content_type:
            from azure.storage.blob import ContentSettings

            content_settings = ContentSettings(content_type=content_type)
        blob_client.upload_blob(data, overwrite=True, content_settings=content_settings)
        digest = hashlib.sha256(data).hexdigest()
        return StoredObject(
            bucket=bucket,
            key=key,
            uri=f"azblob://{bucket}/{key}",
            size_bytes=len(data),
            sha256=digest,
        )

    def get_bytes(self, bucket: str, key: str) -> bytes:
        return self.client.get_blob_client(container=bucket, blob=key).download_blob().readall()

    def exists(self, bucket: str, key: str) -> bool:
        return self.client.get_blob_client(container=bucket, blob=key).exists()

    def list_keys(self, bucket: str, prefix: str) -> list[str]:
        container = self.client.get_container_client(bucket)
        return [blob.name for blob in container.list_blobs(name_starts_with=prefix)]

    def delete(self, bucket: str, key: str) -> None:
        blob_client = self.client.get_blob_client(container=bucket, blob=key)
        if blob_client.exists():
            blob_client.delete_blob()
