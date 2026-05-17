from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QueueMessage:
    id: str
    body: dict[str, Any]
    receipt_handle: str | None = None


class QueueProvider(ABC):
    @abstractmethod
    def enqueue(self, message: dict[str, Any]) -> str:
        raise NotImplementedError

    @abstractmethod
    def receive(self, max_messages: int = 1) -> list[QueueMessage]:
        raise NotImplementedError

    @abstractmethod
    def acknowledge(self, message: QueueMessage) -> None:
        raise NotImplementedError

    @abstractmethod
    def fail(self, message: QueueMessage, reason: str) -> None:
        raise NotImplementedError
