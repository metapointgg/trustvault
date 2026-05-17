from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class StoredObject:
    bucket: str
    key: str
    uri: str
    size_bytes: int | None = None
    sha256: str | None = None


class StorageProvider(ABC):
    @abstractmethod
    def put_bytes(self, bucket: str, key: str, data: bytes, content_type: str | None = None) -> StoredObject:
        raise NotImplementedError

    @abstractmethod
    def get_bytes(self, bucket: str, key: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def exists(self, bucket: str, key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_keys(self, bucket: str, prefix: str) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def delete(self, bucket: str, key: str) -> None:
        raise NotImplementedError
