from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.db.models import EntityContainerVersion


LEGACY_PLACEHOLDER_STATUS = "legacy_invalid_placeholder"


class ContainerVersionNormaliser:
    """Normalise historic development placeholder container records.

    Early local builds briefly produced ZIP placeholder containers before the FITS
    writer was aligned with the Entity Evidence Container Demo architecture. This
    normaliser preserves those records for audit/history but marks them explicitly
    so they are not confused with valid FITS evidence containers.
    """

    def __init__(self, db: Session):
        self.db = db

    def normalise_legacy_placeholders(self) -> dict[str, Any]:
        versions = self.db.scalars(select(EntityContainerVersion)).all()
        updated: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []

        for version in versions:
            is_fits = version.storage_uri.lower().endswith(".fits")
            manifest_format = str(version.manifest_json.get("container_format", "")).upper()
            is_valid_fits_record = is_fits and manifest_format == "FITS"

            if is_valid_fits_record:
                skipped.append(
                    {
                        "container_version_id": str(version.id),
                        "version_number": version.version_number,
                        "storage_uri": version.storage_uri,
                        "reason": "valid_fits_record",
                    }
                )
                continue

            if version.status == LEGACY_PLACEHOLDER_STATUS:
                skipped.append(
                    {
                        "container_version_id": str(version.id),
                        "version_number": version.version_number,
                        "storage_uri": version.storage_uri,
                        "reason": "already_normalised",
                    }
                )
                continue

            original_status = version.status
            version.status = LEGACY_PLACEHOLDER_STATUS
            version.manifest_json = {
                **version.manifest_json,
                "normalisation": {
                    "reason": "Historic development placeholder container. Not a FITS evidence container.",
                    "original_status": original_status,
                    "normalised_status": LEGACY_PLACEHOLDER_STATUS,
                },
            }
            updated.append(
                {
                    "container_version_id": str(version.id),
                    "version_number": version.version_number,
                    "storage_uri": version.storage_uri,
                    "original_status": original_status,
                    "new_status": LEGACY_PLACEHOLDER_STATUS,
                }
            )

        self.db.commit()
        return {
            "updated_count": len(updated),
            "skipped_count": len(skipped),
            "updated": updated,
            "skipped": skipped,
        }
