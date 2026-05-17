import subprocess
import tempfile
from pathlib import Path

from trustvault.ocr.base import OcrProvider, OcrResult


class TesseractOcrProvider(OcrProvider):
    def __init__(self, command: str = "tesseract"):
        self.command = command

    def extract_text(self, payload: bytes, content_type: str | None, filename: str) -> OcrResult:
        suffix = Path(filename).suffix or ".bin"
        with tempfile.NamedTemporaryFile(suffix=suffix) as source:
            source.write(payload)
            source.flush()
            with tempfile.TemporaryDirectory() as output_dir:
                output_base = str(Path(output_dir) / "ocr")
                try:
                    completed = subprocess.run(
                        [self.command, source.name, output_base],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    output_path = Path(f"{output_base}.txt")
                    text = output_path.read_text(encoding="utf-8", errors="replace") if output_path.exists() else ""
                    confidence = 0.75 if completed.returncode == 0 and text else 0.0
                    warnings = [] if completed.returncode == 0 else [completed.stderr]
                    return OcrResult(text=text, confidence=confidence, method="tesseract", warnings=warnings)
                except FileNotFoundError:
                    return OcrResult(text="", confidence=0.0, method="tesseract", warnings=["Tesseract command not found"])
