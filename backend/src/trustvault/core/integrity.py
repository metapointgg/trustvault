import io
import json
import uuid
from typing import Any

import numpy as np
from astropy.io import fits
from sqlalchemy.orm import Session

from trustvault.core.hashing import sha256_bytes
from trustvault.core.storage_uri import parse_storage_uri
from trustvault.db.models import EntityContainerVersion
from trustvault.settings import get_settings
from trustvault.storage.local import LocalFilesystemStorage


class ContainerIntegrityValidator:
    def __init__(self, db: Session):
        self.db = db
        settings = get_settings()
        self.storage = LocalFilesystemStorage(settings.local_storage_root)

    def validate_container_version(self, container_version_id: str) -> dict[str, Any]:
        version = self.db.get(EntityContainerVersion, uuid.UUID(container_version_id))
        if version is None:
            raise ValueError("Container version not found")

        parsed = parse_storage_uri(version.storage_uri)
        if parsed.provider != "local":
            raise ValueError(f"Integrity validation is not yet implemented for provider: {parsed.provider}")

        data = self.storage.get_bytes(parsed.bucket, parsed.key)
        actual_container_sha256 = sha256_bytes(data)
        container_hash_matches = actual_container_sha256 == version.sha256
        is_fits_uri = version.storage_uri.lower().endswith(".fits")

        result: dict[str, Any] = {
            "container_version_id": str(version.id),
            "entity_id": str(version.entity_id),
            "version_number": version.version_number,
            "status": version.status,
            "storage_uri": version.storage_uri,
            "expected_container_sha256": version.sha256,
            "actual_container_sha256": actual_container_sha256,
            "container_hash_matches": container_hash_matches,
            "size_bytes": len(data),
            "expected_size_bytes": version.size_bytes,
            "size_matches": len(data) == version.size_bytes,
            "is_fits_uri": is_fits_uri,
            "fits_opened": False,
            "missing_required_hdus": [],
            "payload_results": [],
            "overall_status": "invalid",
            "errors": [],
        }

        if not is_fits_uri:
            result["errors"].append("Container storage URI is not a .fits file")
            return result

        try:
            with fits.open(io.BytesIO(data), checksum=True) as hdul:
                result["fits_opened"] = True
                hdu_names = [hdu.name for hdu in hdul]
                result["hdu_names"] = hdu_names
                required_hdus = [
                    "PRIMARY",
                    "ENTITY_METADATA",
                    "SUMMARY",
                    "SNAPSHOTS",
                    "MANIFEST",
                    "PROVENANCE",
                    "OCR_TEXT",
                    "HASH_REPORT",
                    "CONTAINER_MANIFEST",
                ]
                result["missing_required_hdus"] = [name for name in required_hdus if name not in hdu_names]

                hash_report = self._read_json_hdu(hdul, "HASH_REPORT")
                payload_results = []
                for item in hash_report.get("objects", []):
                    hdu_name = item.get("hdu_name")
                    expected_sha256 = item.get("sha256")
                    if not hdu_name or hdu_name not in hdu_names:
                        payload_results.append(
                            {
                                "hdu_name": hdu_name,
                                "evidence_object_id": item.get("evidence_object_id"),
                                "filename": item.get("filename"),
                                "valid": False,
                                "error": "Payload HDU missing",
                            }
                        )
                        continue

                    payload_hdu = hdul[hdu_name]
                    payload_bytes = self._hdu_bytes(payload_hdu)
                    actual_sha256 = sha256_bytes(payload_bytes)
                    header_sha256 = payload_hdu.header.get("SHA256")
                    payload_results.append(
                        {
                            "hdu_name": hdu_name,
                            "evidence_object_id": item.get("evidence_object_id"),
                            "filename": item.get("filename"),
                            "expected_sha256": expected_sha256,
                            "actual_sha256": actual_sha256,
                            "header_sha256": header_sha256,
                            "hash_matches": actual_sha256 == expected_sha256,
                            "header_hash_matches": header_sha256 == expected_sha256,
                            "size_bytes": len(payload_bytes),
                            "expected_size_bytes": item.get("size_bytes"),
                            "size_matches": len(payload_bytes) == item.get("size_bytes"),
                            "valid": actual_sha256 == expected_sha256 and header_sha256 == expected_sha256,
                        }
                    )

                result["payload_results"] = payload_results
        except Exception as exc:  # pragma: no cover - defensive validation boundary
            result["errors"].append(f"Failed to open or validate FITS container: {exc}")
            return result

        all_payloads_valid = all(item.get("valid") for item in result["payload_results"])
        result["overall_status"] = "valid" if (
            result["fits_opened"]
            and container_hash_matches
            and result["size_matches"]
            and not result["missing_required_hdus"]
            and all_payloads_valid
            and not result["errors"]
        ) else "invalid"
        return result

    def _read_json_hdu(self, hdul: fits.HDUList, name: str) -> dict[str, Any]:
        if name not in [hdu.name for hdu in hdul]:
            raise ValueError(f"Missing JSON HDU: {name}")
        raw = self._hdu_bytes(hdul[name])
        return json.loads(raw.decode("utf-8"))

    def _hdu_bytes(self, hdu: fits.ImageHDU) -> bytes:
        if hdu.data is None:
            return b""
        return np.asarray(hdu.data, dtype=np.uint8).tobytes()
