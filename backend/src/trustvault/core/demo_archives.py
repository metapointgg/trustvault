from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from trustvault.core.container_builder import EntityContainerBuilder
from trustvault.core.fits_reader import FitsContainerReader
from trustvault.core.source_folder_ingestion import SourceFolderIngestionService


@dataclass(frozen=True)
class DemoArchiveEntity:
    external_id: str
    display_name: str
    entity_type: str
    metadata: dict[str, Any]
    files: dict[str, str]


HEALTHCARE_DEMO_ENTITIES: tuple[DemoArchiveEntity, ...] = (
    DemoArchiveEntity(
        external_id="PAT-ONC-0001",
        display_name="Eleanor Hughes",
        entity_type="patient",
        metadata={"department": "Oncology", "condition": "Cancer", "responsible_person": "Dr Jones", "risk_rating": "High", "jurisdiction": "United Kingdom", "treatment_status": "Active"},
        files={
            "documents/eleanor_hughes_referral_letter.txt": "Referral Letter\nPatient referred to oncology for treatment pathway review. Consultant: Dr Jones. Condition: cancer.",
            "documents/eleanor_hughes_treatment_plan.txt": "Treatment Plan\nOncology treatment plan agreed. Chemotherapy pathway and monitoring schedule recorded.",
            "documents/eleanor_hughes_diagnostic_report.txt": "Diagnostic Report\nHistology and imaging report confirming oncology diagnosis.",
        },
    ),
    DemoArchiveEntity(
        external_id="PAT-ONC-0002",
        display_name="Noah Patel",
        entity_type="patient",
        metadata={"department": "Oncology", "condition": "Cancer", "responsible_person": "Dr Jones", "risk_rating": "Medium", "jurisdiction": "United Kingdom", "treatment_status": "Pre-treatment"},
        files={
            "documents/noah_patel_referral_letter.txt": "Referral Letter\nGP referral to oncology. Consultant: Dr Jones. Condition: cancer.",
            "documents/noah_patel_consent_form.txt": "Consent Form\nPatient consent form signed for oncology treatment and information sharing.",
            "documents/noah_patel_treatment_plan.txt": "Treatment Plan\nTreatment plan created for oncology care pathway.",
        },
    ),
    DemoArchiveEntity(
        external_id="PAT-CAR-0003",
        display_name="Grace Williams",
        entity_type="patient",
        metadata={"department": "Cardiology", "condition": "Arrhythmia", "responsible_person": "Dr Smith", "risk_rating": "Low", "jurisdiction": "United Kingdom", "treatment_status": "Monitoring"},
        files={
            "documents/grace_williams_referral_letter.txt": "Referral Letter\nReferral to cardiology clinic for arrhythmia monitoring. Responsible clinician: Dr Smith.",
            "documents/grace_williams_consent_form.txt": "Consent Form\nPatient consent form signed for cardiology monitoring.",
            "documents/grace_williams_diagnostic_report.txt": "Diagnostic Report\nECG and monitoring report included.",
        },
    ),
)

SUPPLIER_DEMO_ENTITIES: tuple[DemoArchiveEntity, ...] = (
    DemoArchiveEntity(
        external_id="SUP-IT-0001",
        display_name="Aster Cloud Services Ltd",
        entity_type="supplier",
        metadata={"supplier_category": "IT", "criticality": "Critical", "service_type": "Cloud hosting", "contract_owner": "Technology", "risk_rating": "High", "jurisdiction": "United Kingdom"},
        files={
            "documents/aster_cloud_iso_27001_certificate.txt": "ISO 27001 Certificate\nInformation security certificate provided for Aster Cloud Services Ltd.",
            "documents/aster_cloud_soc_2_report.txt": "SOC 2 Report\nSOC 2 Type II report provided for cloud hosting controls.",
            "documents/aster_cloud_data_processing_agreement.txt": "Data Processing Agreement\nDPA executed for personal data processing by supplier.",
        },
    ),
    DemoArchiveEntity(
        external_id="SUP-IT-0002",
        display_name="Northstar Software Ltd",
        entity_type="supplier",
        metadata={"supplier_category": "IT", "criticality": "Material", "service_type": "Software support", "contract_owner": "Operations", "risk_rating": "Medium", "jurisdiction": "Guernsey"},
        files={
            "documents/northstar_certificate_of_incorporation.txt": "Certificate of Incorporation\nCompany incorporation certificate supplied by Northstar Software Ltd.",
            "documents/northstar_insurance_certificate.txt": "Insurance Certificate\nProfessional indemnity and public liability insurance certificate supplied.",
            "documents/northstar_iso_27001_certificate.txt": "ISO 27001 Certificate\nSupplier confirms ISO 27001 certification for software support operations.",
        },
    ),
    DemoArchiveEntity(
        external_id="SUP-LEGAL-0003",
        display_name="Bailiwick Legal LLP",
        entity_type="supplier",
        metadata={"supplier_category": "Legal", "criticality": "Standard", "service_type": "Legal services", "contract_owner": "Legal", "risk_rating": "Low", "jurisdiction": "Jersey"},
        files={
            "documents/bailiwick_legal_certificate_of_incorporation.txt": "Certificate of Incorporation\nPartnership registration and incorporation evidence supplied.",
            "documents/bailiwick_legal_insurance_certificate.txt": "Insurance Certificate\nProfessional indemnity certificate supplied for legal services.",
        },
    ),
)


class DemoArchiveService:
    def __init__(self, db: Session):
        self.db = db

    def available_archives(self) -> list[dict[str, Any]]:
        return [
            {"key": "healthcare", "label": "Healthcare demo archive", "entity_count": len(HEALTHCARE_DEMO_ENTITIES), "description": "Patient evidence demo with oncology, consent, referral, treatment and diagnostic evidence."},
            {"key": "supplier_due_diligence", "label": "Supplier Due Diligence demo archive", "entity_count": len(SUPPLIER_DEMO_ENTITIES), "description": "Supplier evidence demo with IT supplier onboarding, cyber due diligence and corporate evidence."},
        ]

    def generate(self, archive_key: str) -> dict[str, Any]:
        entities = self._entities_for_key(archive_key)
        results: list[dict[str, Any]] = []
        for entity in entities:
            zip_bytes = self._entity_zip(entity)
            result = SourceFolderIngestionService(self.db).ingest_zip_bytes(zip_bytes, source_system_default=f"demo_{archive_key}")
            container = EntityContainerBuilder(self.db).rebuild(result.entity_external_id) if result.evidence_object_count > 0 else None
            index = FitsContainerReader(self.db).rebuild_index_from_current_fits(result.entity_external_id) if container else None
            results.append(
                {
                    "entity_id": result.entity_id,
                    "entity_external_id": result.entity_external_id,
                    "entity_display_name": result.entity_display_name,
                    "evidence_object_count": result.evidence_object_count,
                    "duplicate_count": result.duplicate_count,
                    "container": container,
                    "index": index,
                }
            )
        return {"archive_key": archive_key, "entity_count": len(results), "entities": results}

    def _entities_for_key(self, archive_key: str) -> tuple[DemoArchiveEntity, ...]:
        key = str(archive_key or "").strip().lower()
        if key == "healthcare":
            return HEALTHCARE_DEMO_ENTITIES
        if key in {"supplier", "supplier_due_diligence", "vendor_due_diligence"}:
            return SUPPLIER_DEMO_ENTITIES
        raise ValueError(f"Unsupported demo archive '{archive_key}'")

    def _entity_zip(self, entity: DemoArchiveEntity) -> bytes:
        root = f"{entity.external_id}/"
        metadata = {
            "entity_id": entity.external_id,
            "display_name": entity.display_name,
            "entity_type": entity.entity_type,
            **entity.metadata,
            "source_systems": ["TrustVault Demo Generator", "Document Store", "Operational System"],
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"{root}customer.json", json.dumps(metadata, indent=2))
            archive.writestr(f"{root}metadata/audit_events.json", json.dumps([{"event": "demo_archive_generated", "entity_id": entity.external_id}], indent=2))
            for relative, text in entity.files.items():
                archive.writestr(f"{root}{relative}", text)
                archive.writestr(f"{root}{relative}.search.txt", text)
        return buffer.getvalue()
