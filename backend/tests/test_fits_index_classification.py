from trustvault.core.fits_index_classification import FitsIndexClassificationService


class _FakeIndexEntry:
    def __init__(self, *, filename: str, object_type: str, metadata_json: dict):
        self.filename = filename
        self.object_type = object_type
        self.metadata_json = metadata_json


def _service() -> FitsIndexClassificationService:
    return FitsIndexClassificationService.__new__(FitsIndexClassificationService)


def test_restores_polluted_transaction_extract_to_generic_artifact() -> None:
    service = _service()
    row = _FakeIndexEntry(
        filename="transactions_2026_q1.csv",
        object_type="Passport",
        metadata_json={
            "category": "identity",
            "document_type": "Passport",
            "classification_source": "industry_vocabulary",
            "classification_status": "suggested",
            "classification_confidence": 0.72,
            "metadata": {
                "category": "identity",
                "document_type": "Passport",
                "classification_source": "industry_vocabulary",
                "classification_status": "suggested",
            },
        },
    )

    profile = service._generic_artifact_profile(index_entry=row, metadata=row.metadata_json)
    assert profile == {
        "object_type": "structured_extract",
        "category": "structured_extracts",
        "document_type": "structured_extract",
    }

    changed = service._apply_generic_artifact_profile(row, profile)

    assert changed is True
    assert row.object_type == "structured_extract"
    assert row.metadata_json["category"] == "structured_extracts"
    assert row.metadata_json["document_type"] == "structured_extract"
    assert "classification_source" not in row.metadata_json
    assert "classification_status" not in row.metadata_json
    assert "classification_confidence" not in row.metadata_json
    assert "classification_matched_alias" not in row.metadata_json
    assert "industry_pack" not in row.metadata_json
    assert row.metadata_json["metadata"]["category"] == "structured_extracts"
    assert row.metadata_json["metadata"]["document_type"] == "structured_extract"
    assert "classification_source" not in row.metadata_json["metadata"]


def test_restores_polluted_bulk_archive_placeholder_to_generic_artifact() -> None:
    service = _service()
    row = _FakeIndexEntry(
        filename="bulk_archive_attachment_missing_poa.bin",
        object_type="Proof of Address",
        metadata_json={
            "category": "proof_of_address",
            "document_type": "Proof of Address",
            "classification_source": "industry_vocabulary",
            "classification_status": "classified",
            "metadata": {
                "category": "proof_of_address",
                "document_type": "Proof of Address",
                "classification_source": "industry_vocabulary",
                "classification_status": "classified",
            },
        },
    )

    profile = service._generic_artifact_profile(index_entry=row, metadata=row.metadata_json)
    assert profile == {
        "object_type": "bulk_archive_attachment",
        "category": "large_evidence",
        "document_type": "bulk_archive_attachment",
    }

    changed = service._apply_generic_artifact_profile(row, profile)

    assert changed is True
    assert row.object_type == "bulk_archive_attachment"
    assert row.metadata_json["category"] == "large_evidence"
    assert row.metadata_json["document_type"] == "bulk_archive_attachment"
    assert "classification_source" not in row.metadata_json
    assert "classification_status" not in row.metadata_json
    assert row.metadata_json["metadata"]["category"] == "large_evidence"
    assert row.metadata_json["metadata"]["document_type"] == "bulk_archive_attachment"
    assert "classification_source" not in row.metadata_json["metadata"]


def test_genuine_business_evidence_is_not_treated_as_generic_artifact() -> None:
    service = _service()
    row = _FakeIndexEntry(
        filename="aster_cloud_iso_27001_certificate.txt",
        object_type="ISO 27001 Certificate",
        metadata_json={
            "category": "cyber_due_diligence",
            "document_type": "ISO 27001 Certificate",
            "classification_source": "industry_vocabulary",
        },
    )

    assert service._generic_artifact_profile(index_entry=row, metadata=row.metadata_json) is None
