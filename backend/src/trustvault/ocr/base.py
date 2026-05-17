from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float
    method: str
    warnings: list[str] = field(default_factory=list)


class OcrProvider(ABC):
    @abstractmethod
    def extract_text(self, payload: bytes, content_type: str | None, filename: str) -> OcrResult:
        raise NotImplementedError
