import hashlib

from trustvault.storage.base import StorageProvider, StoredObject


class S3Storage(StorageProvider):
    def __init__(self, region_name: str | None = None):
        import boto3

        self.client = boto3.client("s3", region_name=region_name)

    def put_bytes(self, bucket: str, key: str, data: bytes, content_type: str | None = None) -> StoredObject:
        extra_args = {"ServerSideEncryption": "aws:kms"}
        if content_type:
            extra_args["ContentType"] = content_type
        self.client.put_object(Bucket=bucket, Key=key, Body=data, **extra_args)
        digest = hashlib.sha256(data).hexdigest()
        return StoredObject(
            bucket=bucket,
            key=key,
            uri=f"s3://{bucket}/{key}",
            size_bytes=len(data),
            sha256=digest,
        )

    def get_bytes(self, bucket: str, key: str) -> bytes:
        response = self.client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()

    def exists(self, bucket: str, key: str) -> bool:
        try:
            self.client.head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False

    def list_keys(self, bucket: str, prefix: str) -> list[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                keys.append(item["Key"])
        return keys

    def delete(self, bucket: str, key: str) -> None:
        self.client.delete_object(Bucket=bucket, Key=key)
