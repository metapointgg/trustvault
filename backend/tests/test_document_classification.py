from trustvault.core.document_classification import DocumentClassificationService


class _FakeSession:
    def get(self, *_args):
        return None


def test_filename_classification_uses_document_type_mapping() -> None:
    service = DocumentClassificationService(_FakeSession())

    result = service.classify(filename="mike_ozanne_passport.pdf")

    assert result.document_type == "Passport"
    assert result.category == "Identity"
    assert result.status == "classified"
    assert result.source == "filename_rule"


def test_unmatched_filename_is_remediation_queue_item() -> None:
    service = DocumentClassificationService(_FakeSession())

    result = service.classify(filename="unrecognised_payload.pdf", source_path="documents/unrecognised_payload.pdf")

    assert result.document_type is None
    assert result.category is None
    assert result.status == "uncategorised"
    assert result.confidence == 0.0


def test_document_types_are_available_for_settings_backed_dropdown() -> None:
    service = DocumentClassificationService(_FakeSession())

    rows = service.document_types()

    assert "Passport" in rows
    assert "Proof of Address" in rows
