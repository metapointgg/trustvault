from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from trustvault.core.app_settings import AppSettingsService
from trustvault.core.container_builder import EntityContainerBuilder
from trustvault.core.fits_reader import FitsContainerReader
from trustvault.core.source_folder_ingestion import SourceFolderIngestionService


@dataclass(frozen=True)
class DropFolderValidation:
    valid: bool
    root: str
    errors: list[str]
    warnings: list[str]
    file_count: int


class DropFolderIngestionService:
    REQUIRED_PATHS = ("metadata/customer.json",)
    RECOMMENDED_TOP_LEVEL = {"metadata", "documents", "scans", "emails", "statements", "extracts", "large_evidence"}

    def __init__(self, db: Session):
        self.db = db
        self.settings = AppSettingsService(db)

    def status(self) -> dict[str, Any]:
        values = self.settings.effective_values()
        folders = self._folders(values)
        return {
            "enabled": values.get("auto_ingestion_enabled"),
            "poll_seconds": values.get("auto_ingestion_poll_seconds"),
            "strict_structure": values.get("auto_ingestion_strict_structure"),
            "folders": {name: str(path) for name, path in folders.items()},
            "folder_state": {name: {"exists": path.exists(), "zip_count": len(list(path.glob("*.zip"))) if path.exists() else 0} for name, path in folders.items()},
        }

    def scan_once(self) -> dict[str, Any]:
        values = self.settings.effective_values()
        if not values.get("auto_ingestion_enabled", True):
            return {"enabled": False, "processed_count": 0, "failed_count": 0, "results": []}

        folders = self._folders(values)
        for folder in folders.values():
            folder.mkdir(parents=True, exist_ok=True)

        results: list[dict[str, Any]] = []
        processed_count = 0
        failed_count = 0
        for zip_path in sorted(folders["drop"].glob("*.zip")):
            result = self.process_zip(
                zip_path,
                folders=folders,
                strict_structure=bool(values.get("auto_ingestion_strict_structure", True)),
                rebuild_container=bool(values.get("auto_ingestion_rebuild_container", True)),
                rebuild_index=bool(values.get("auto_ingestion_rebuild_index", True)),
            )
            results.append(result)
            if result["status"] == "processed":
                processed_count += 1
            else:
                failed_count += 1
        return {"enabled": True, "processed_count": processed_count, "failed_count": failed_count, "results": results}

    def process_zip(
        self,
        zip_path: Path,
        *,
        folders: dict[str, Path],
        strict_structure: bool,
        rebuild_container: bool,
        rebuild_index: bool,
    ) -> dict[str, Any]:
        processing_path = self._unique_path(folders["processing"] / zip_path.name)
        moved_final_path: Path | None = None
        started_at = datetime.now(timezone.utc).isoformat()
        try:
            shutil.move(str(zip_path), processing_path)
            validation = self.validate_zip(processing_path)
            if strict_structure and not validation.valid:
                raise ValueError("Invalid source folder ZIP structure: " + "; ".join(validation.errors))

            zip_bytes = processing_path.read_bytes()
            ingestion_result = SourceFolderIngestionService(self.db).ingest_zip_bytes(zip_bytes)
            container = None
            index = None
            if ingestion_result.evidence_object_count > 0 and rebuild_container:
                container = EntityContainerBuilder(self.db).rebuild(ingestion_result.entity_external_id)
            if ingestion_result.evidence_object_count > 0 and rebuild_index:
                index = FitsContainerReader(self.db).rebuild_index_from_current_fits(ingestion_result.entity_external_id)

            moved_final_path = self._unique_path(folders["processed"] / processing_path.name)
            shutil.move(str(processing_path), moved_final_path)
            self._write_sidecar(moved_final_path, {
                "status": "processed",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "validation": validation.__dict__,
                "ingestion": ingestion_result.__dict__,
                "container": container,
                "index": index,
            })
            return {
                "filename": zip_path.name,
                "status": "processed",
                "moved_to": str(moved_final_path),
                "validation": validation.__dict__,
                "ingestion": ingestion_result.__dict__,
                "container": container,
                "index": index,
            }
        except Exception as exc:
            source = processing_path if processing_path.exists() else zip_path
            moved_final_path = self._unique_path(folders["failed"] / source.name)
            if source.exists():
                shutil.move(str(source), moved_final_path)
            self._write_sidecar(moved_final_path, {
                "status": "failed",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
            })
            return {"filename": zip_path.name, "status": "failed", "moved_to": str(moved_final_path), "error": str(exc)}

    def validate_zip(self, zip_path: Path) -> DropFolderValidation:
        errors: list[str] = []
        warnings: list[str] = []
        try:
            with zipfile.ZipFile(zip_path, "r") as archive:
                names = [name for name in archive.namelist() if not name.endswith("/") and not name.startswith("__MACOSX/") and "/._" not in name]
                root = self._detect_root(names)
                relative_names = [name[len(root):] if root and name.startswith(root) else name for name in names]
                for required in self.REQUIRED_PATHS:
                    if required not in relative_names:
                        errors.append(f"Missing required file: {required}")
                top_levels = {Path(name).parts[0] for name in relative_names if Path(name).parts}
                if not top_levels.intersection(self.RECOMMENDED_TOP_LEVEL):
                    warnings.append("No recognised evidence folders were found.")
                if "metadata/customer.json" in relative_names:
                    try:
                        metadata_path = names[relative_names.index("metadata/customer.json")]
                        customer = json.loads(archive.read(metadata_path).decode("utf-8"))
                        if not customer.get("entity_id"):
                            errors.append("metadata/customer.json is missing entity_id")
                        if not customer.get("display_name"):
                            warnings.append("metadata/customer.json is missing display_name")
                    except Exception as exc:
                        errors.append(f"metadata/customer.json could not be parsed: {exc}")
                return DropFolderValidation(valid=not errors, root=root.rstrip("/"), errors=errors, warnings=warnings, file_count=len(relative_names))
        except zipfile.BadZipFile:
            return DropFolderValidation(valid=False, root="", errors=["File is not a valid ZIP archive"], warnings=[], file_count=0)

    def _folders(self, values: dict[str, Any]) -> dict[str, Path]:
        return {
            "drop": Path(str(values.get("auto_ingestion_drop_folder"))).expanduser(),
            "processing": Path(str(values.get("auto_ingestion_processing_folder"))).expanduser(),
            "processed": Path(str(values.get("auto_ingestion_processed_folder"))).expanduser(),
            "failed": Path(str(values.get("auto_ingestion_failed_folder"))).expanduser(),
        }

    def _detect_root(self, names: list[str]) -> str:
        first_parts = [name.split("/", 1)[0] for name in names if "/" in name]
        if not first_parts:
            return ""
        root = first_parts[0]
        return f"{root}/" if all(part == root for part in first_parts) else ""

    def _unique_path(self, path: Path) -> Path:
        if not path.exists():
            return path
        suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return path.with_name(f"{path.stem}-{suffix}{path.suffix}")

    def _write_sidecar(self, zip_path: Path, payload: dict[str, Any]) -> None:
        sidecar = zip_path.with_suffix(zip_path.suffix + ".json")
        sidecar.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
