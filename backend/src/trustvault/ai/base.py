from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AiResult:
    text: str
    provider: str
    model: str | None = None
    citations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    data: dict[str, Any] | None = None


class AiProvider(ABC):
    @abstractmethod
    def expand_query(self, query: str) -> AiResult:
        raise NotImplementedError

    @abstractmethod
    def interpret_query(self, query: str, deterministic_query: dict[str, Any], context: dict[str, Any] | None = None) -> AiResult:
        raise NotImplementedError

    @abstractmethod
    def summarise_evidence(self, evidence: list[dict], question: str | None = None) -> AiResult:
        raise NotImplementedError
