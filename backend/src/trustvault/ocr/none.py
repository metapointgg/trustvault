from trustvault.ocr.base import OcrProvider, OcrResult


class NoOcrProvider(OcrProvider):
    def extract_text(self, payload: bytes, content_type: str | None, filename: str) -> OcrResult:
        return OcrResult(text="", confidence=0.0, method="none", warnings=["OCR provider disabled"])
