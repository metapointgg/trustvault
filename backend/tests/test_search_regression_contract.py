from scripts.run_search_regression import TrustVaultRegressionRunner


def _runner() -> TrustVaultRegressionRunner:
    return TrustVaultRegressionRunner(
        base_url="http://testserver",
        token="test-token",
        mode="deterministic",
        limit=50,
        include_ai_summary=False,
        timeout=5,
    )


def test_regression_expectations_pass_for_matching_execute_response() -> None:
    runner = _runner()
    response = {
        "ok": True,
        "json": {
            "structured_query": {
                "capability": "evidence_search",
                "scope": "entity",
                "execute_with": "direct_fits",
                "snapshot_id": "ONBOARDING",
                "document_types": ["passport"],
            },
            "execution_source": "direct_fits_container",
            "result": {"result_count": 2, "results": [{"evidence_object_id": "obj-1"}]},
        },
    }
    derived = runner._derive(response)

    issues = runner._check_expectations(
        {
            "expected_scope": "entity",
            "expected_execute_with": "direct_fits",
            "expected_execution_source": "direct_fits_container",
            "expected_snapshot_id": "ONBOARDING",
            "expect_result_count_min": 1,
            "forbidden_document_type": "ONBOARDING",
        },
        response,
        derived,
    )

    assert issues == []


def test_regression_expectations_report_specific_failures() -> None:
    runner = _runner()
    response = {
        "ok": True,
        "json": {
            "structured_query": {
                "capability": "entity_discovery",
                "scope": "archive",
                "execute_with": "fits_index",
                "snapshot_id": None,
                "document_types": ["ONBOARDING"],
            },
            "execution_source": "fits_index",
            "result": {"result_count": 0, "results": []},
        },
    }
    derived = runner._derive(response)

    issues = runner._check_expectations(
        {
            "expected_capability": "evidence_search",
            "expected_scope": "entity",
            "expected_execute_with": "direct_fits",
            "expected_execution_source": "direct_fits_container",
            "expected_snapshot_id": "ONBOARDING",
            "forbidden_document_type": "ONBOARDING",
            "expect_result_count_min": 1,
        },
        response,
        derived,
    )

    assert "capability_expected_evidence_search_got_entity_discovery" in issues
    assert "scope_expected_entity_got_archive" in issues
    assert "execute_with_expected_direct_fits_got_fits_index" in issues
    assert "execution_source_expected_direct_fits_container_got_fits_index" in issues
    assert "snapshot_id_expected_ONBOARDING_got_None" in issues
    assert "forbidden_document_type_present_ONBOARDING" in issues
    assert "result_count_expected_min_1_got_0" in issues


def test_regression_expectations_validate_endpoint_shape_and_latency() -> None:
    runner = _runner()
    response = {
        "ok": True,
        "elapsed_seconds": 2.5,
        "json": {"checked_count": 10, "summary_mode": "full"},
    }
    issues = runner._check_expectations(
        {
            "expected_json_keys": ["results", "checked_count", "summary_mode"],
            "expected_json_value": {"summary_mode": "metadata"},
            "max_elapsed_seconds": 2.0,
        },
        response,
        runner._derive(response),
    )

    assert "missing_json_key_results" in issues
    assert "json_value_summary_mode_expected_metadata_got_full" in issues
    assert "elapsed_seconds_expected_max_2.0_got_2.5" in issues
