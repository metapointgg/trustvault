from trustvault.core.evidence_classifier import EvidenceClassifier


class _FakeSession:
    def get(self, *_args):
        return None


class _FakeEntity:
    metadata_json = {"industry_pack": "healthcare", "department": "Oncology"}


class _FakeSupplierEntity:
    metadata_json = {"industry_pack": "supplier_due_diligence", "supplier_category": "IT"}


class _FakeFinancialServicesEntity:
    metadata_json = {"industry_pack": "financial_services", "risk_rating": "High"}


def test_industry_classifier_uses_healthcare_vocabulary() -> None:
    service = EvidenceClassifier(_FakeSession())

    result = service.classify(
        filename="eleanor_hughes_diagnostic_report.txt",
        object_type="eleanor_hughes_diagnostic_report",
        source_system="Document Store",
        text_content="Diagnostic Report confirming oncology diagnosis.",
        metadata={"industry_pack": "healthcare"},
        entity=_FakeEntity(),
    )

    assert result is not None
    assert result.document_type == "Diagnostic Report"
    assert result.classification_status == "classified"
    assert result.industry_pack == "healthcare"


def test_industry_classifier_uses_supplier_vocabulary() -> None:
    service = EvidenceClassifier(_FakeSession())

    result = service.classify(
        filename="aster_cloud_iso_27001_certificate.txt",
        object_type="aster_cloud_iso_27001_certificate",
        source_system="Document Store",
        text_content="ISO 27001 Certificate for supplier assurance.",
        metadata={"industry_pack": "supplier_due_diligence"},
        entity=_FakeSupplierEntity(),
    )

    assert result is not None
    assert result.document_type == "ISO 27001 Certificate"
    assert result.category == "cyber_due_diligence"
    assert result.classification_status == "classified"
    assert result.industry_pack == "supplier_due_diligence"


def test_classifier_does_not_reclassify_structured_extract_as_passport() -> None:
    service = EvidenceClassifier(_FakeSession())

    result = service.classify(
        filename="transactions_2026_q1.csv",
        object_type="structured_extract",
        source_system="Operational System",
        text_content="Contains customer transactions and passport verification fields in exported data.",
        metadata={
            "industry_pack": "financial_services",
            "category": "structured_extracts",
            "document_type": "structured_extract",
        },
        entity=_FakeFinancialServicesEntity(),
    )

    assert result is None


def test_classifier_does_not_reclassify_bulk_archive_placeholder_as_poa() -> None:
    service = EvidenceClassifier(_FakeSession())

    result = service.classify(
        filename="bulk_archive_attachment_missing_poa.bin",
        object_type="bulk_archive_attachment",
        source_system="Document Store",
        text_content="Placeholder generated while proof of address was unavailable.",
        metadata={
            "industry_pack": "financial_services",
            "category": "large_evidence",
            "document_type": "bulk_archive_attachment",
        },
        entity=_FakeFinancialServicesEntity(),
    )

    assert result is None
