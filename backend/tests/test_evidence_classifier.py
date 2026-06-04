from trustvault.core.evidence_classifier import EvidenceClassifier


class _FakeSession:
    def get(self, *_args):
        return None


class _FakeEntity:
    metadata_json = {"industry_pack": "healthcare", "department": "Oncology"}


class _FakeSupplierEntity:
    metadata_json = {"industry_pack": "supplier_due_diligence", "supplier_category": "IT"}


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
