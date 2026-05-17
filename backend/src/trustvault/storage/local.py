import hashlib
from pathlib import Path

from trustvault.storage.base import StorageProvider, StoredObject


class LocalFilesystemStorage(StorageProvider):
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, bucket: str, key: str) -> Path:
        safe_key = key.strip("/")
        return self.root / bucket / safe_key

    def put_bytes(self, bucket: str, key: str, data: bytes, content_type: str | None = None) -> StoredObject:
        path = self._path(bucket, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        return StoredObject(
            bucket=bucket,
            key=key,
            uri=f"local://{bucket}/{key}",
            size_bytes=len(data),
            sha256=digest,
        )

    def get_bytes(self, bucket: str, key: str) -> bytes:
        return self._path(bucket, key).read_bytes()

    def exists(self, bucket: str, key: str) -> bool:
        return self._path(bucket, key).exists()

    def list_keys(self, bucket: str, prefix: str) -> list[str]:
        base = self.root / bucket
        if not base.exists():
            return []
        return [str(path.relative_to(base)) for path in base.rglob("*") if path.is_file() and str(path.relative_to(base)).startswith(prefix)]

    def delete(self, bucket: str, key: str) -> None:
        path = self._path(bucket, key)
        if path.exists():
            path.unlink()
