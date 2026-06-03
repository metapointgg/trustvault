from __future__ import annotations

import re
from typing import Any

ENRICHED_QUERY_SCENARIOS: list[dict[str, Any]] = [
    {
        "group": "Archive/status checks",
        "examples": [
            "Use TrustVault to show me the archive status.",
            "Use TrustVault to tell me how many entities, containers and indexed evidence objects are available.",
            "Use TrustVault to show the configured source folder, containers folder, index path and exports folder.",
        ],
    },
    {
        "group": "Financial Services - entity discovery",
        "examples": [
            "Use TrustVault to list high risk customers.",
            "Use TrustVault to list high risk customers in Guernsey.",
            "Use TrustVault to list high risk entities in Guernsey.",
            "Use TrustVault to list medium risk entities in Jersey.",
            "Use TrustVault to show high risk entities in Guernsey missing onboarding documentation.",
            "Use TrustVault to identify entities missing mandatory evidence.",
        ],
    },
    {
        "group": "Financial Services - evidence and completeness",
        "examples": [
            "Use TrustVault to search the archive for source of funds evidence.",
            "Use TrustVault to search the archive for onboarding documentation for high risk entities in Guernsey.",
            "Use TrustVault to find CDD review evidence for high risk entities.",
            "Use TrustVault to find all screening evidence for Guernsey entities.",
            "Use TrustVault to execute this query: Which entities are missing proof of address?",
            "Use TrustVault to execute this query for CUST-000001: What evidence explains where the entity money came from?",
        ],
    },
    {
        "group": "Healthcare - patient evidence",
        "examples": [
            "Use TrustVault to list patients.",
            "Use TrustVault to list patients in oncology.",
            "Use TrustVault to show cancer patients missing a consent form.",
            "Use TrustVault to show patients in oncology missing consent forms.",
            "Use TrustVault to show Dr Jones patients missing consent forms.",
            "Use TrustVault to search for diagnostic reports for oncology patients.",
            "Use TrustVault to check patient evidence completeness for Eleanor Hughes.",
        ],
    },
    {
        "group": "Supplier Due Diligence - supplier evidence",
        "examples": [
            "Use TrustVault to list suppliers.",
            "Use TrustVault to list IT suppliers.",
            "Use TrustVault to list critical suppliers.",
            "Use TrustVault to show IT suppliers that have not supplied a certificate of incorporation.",
            "Use TrustVault to show critical suppliers missing ISO 27001 certificates.",
            "Use TrustVault to show IT suppliers missing SOC 2 reports.",
            "Use TrustVault to show suppliers missing insurance certificates.",
            "Use TrustVault to search supplier due diligence evidence for data processing agreements.",
        ],
    },
    {
        "group": "Selected entity searches",
        "examples": [
            "Use TrustVault to summarise entity CUST-000001.",
            "Use TrustVault to show the FITS containers available for CUST-000001.",
            "Use TrustVault to show the evidence counts by category and document type for CUST-000001.",
            "Use TrustVault to search CUST-000001 directly for onboarding documentation.",
            "Use TrustVault to search CUST-000001 for proof of address evidence.",
            "Use TrustVault to check evidence completeness for CUST-000001.",
        ],
    },
    {
        "group": "Query interpretation tests",
        "examples": [
            "Use TrustVault to interpret this query: Which high risk entities in Guernsey are missing proof of address?",
            "Use TrustVault to interpret this query: Which cancer patients are missing a consent form?",
            "Use TrustVault to interpret this query: Which IT suppliers have not supplied a certificate of incorporation?",
            "Use TrustVault to interpret this query: Which critical suppliers are missing ISO 27001 certificates?",
        ],
    },
]

CORE_QUERY_REGRESSION_TEST_CASES: list[dict[str, Any]] = [
    {
        "id": "archive_status_neutral_context_even_when_saved_industry_healthcare",
        "industry": "healthcare",
        "query": "tell me how many entities, containers and indexed evidence objects are available.",
        "mode": "auto",
        "expect": {
            "capability": "archive_status",
            "execution_source": "archive_status",
            "active_industry_is_null": True,
            "context_source": "not_applicable_archive_status",
            "min_result_count": 1,
        },
    },
    {
        "id": "archive_config_neutral_context_even_when_saved_industry_healthcare",
        "industry": "healthcare",
        "query": "show the configured source folder, containers folder, index path and exports folder.",
        "mode": "auto",
        "expect": {
            "capability": "archive_status",
            "execution_source": "archive_status",
            "active_industry_is_null": True,
            "context_source": "not_applicable_archive_status",
            "min_result_count": 1,
        },
    },
    {
        "id": "auto_generic_entities_infers_financial_services_even_when_saved_industry_healthcare",
        "industry": "healthcare",
        "query": "list high risk entities in Guernsey.",
        "mode": "auto",
        "expect": {
            "capability": "entity_discovery",
            "execution_source": "entity_metadata",
            "active_industry": "financial_services",
            "risk_rating": "High",
            "jurisdiction": "Guernsey",
            "min_result_count": 2,
            "expected_entity_external_ids": ["CUST-000046", "CUST-999001"],
        },
    },
    {
        "id": "fs_guernsey_high_risk_search_onboarding_evidence",
        "industry": "financial_services",
        "query": "search the archive for onboarding documentation for high risk entities in Guernsey.",
        "mode": "auto",
        "expect": {
            "capability": "evidence_search",
            "execution_source": "fits_index",
            "active_industry": "financial_services",
            "risk_rating": "High",
            "jurisdiction": "Guernsey",
        },
    },
    {
        "id": "fs_guernsey_high_risk_missing_onboarding",
        "industry": "financial_services",
        "query": "Show me high risk entities in Guernsey who are missing onboarding documentation",
        "mode": "auto",
        "expect": {"capability": "completeness_check", "execution_source": "completeness_rules", "active_industry": "financial_services", "risk_rating": "High", "jurisdiction": "Guernsey", "min_result_count": 1, "expected_entity_external_ids": ["CUST-999001"], "document_types": ["Proof of Address"]},
    },
    {
        "id": "fs_malta_missing_onboarding",
        "industry": "financial_services",
        "query": "Are there any entities in Malta missing onboarding documentation?",
        "mode": "auto",
        "expect": {"capability": "completeness_check", "execution_source": "completeness_rules", "active_industry": "financial_services", "jurisdiction": "Malta", "forbidden_entity_external_ids": ["CUST-999001"]},
    },
    {
        "id": "healthcare_cancer_missing_consent",
        "industry": "healthcare",
        "query": "Which cancer patients are missing a consent form?",
        "mode": "auto",
        "expect": {"capability": "completeness_check", "execution_source": "completeness_rules", "active_industry": "healthcare", "document_types": ["Consent Form"], "expected_entity_external_ids": ["PAT-ONC-0001"], "forbidden_entity_external_ids": ["PAT-ONC-0002", "PAT-CAR-0003", "SUP-IT-0001"]},
    },
    {
        "id": "healthcare_oncology_missing_consent",
        "industry": "healthcare",
        "query": "Which patients in oncology are missing consent forms?",
        "mode": "auto",
        "expect": {"capability": "completeness_check", "execution_source": "completeness_rules", "active_industry": "healthcare", "metadata_filters": {"department": "Oncology"}, "document_types": ["Consent Form"], "expected_entity_external_ids": ["PAT-ONC-0001"], "forbidden_entity_external_ids": ["PAT-ONC-0002", "PAT-CAR-0003"]},
    },
    {
        "id": "healthcare_dr_jones_missing_consent",
        "industry": "healthcare",
        "query": "Which of Dr Jones patients are missing consent forms?",
        "mode": "auto",
        "expect": {"capability": "completeness_check", "execution_source": "completeness_rules", "active_industry": "healthcare", "metadata_filters": {"responsible_person": "Dr Jones"}, "document_types": ["Consent Form"], "expected_entity_external_ids": ["PAT-ONC-0001"]},
    },
    {
        "id": "supplier_it_missing_certificate_of_incorporation",
        "industry": "supplier_due_diligence",
        "query": "Which IT suppliers have not supplied a certificate of incorporation?",
        "mode": "auto",
        "expect": {"capability": "completeness_check", "execution_source": "completeness_rules", "active_industry": "supplier_due_diligence", "metadata_filters": {"supplier_category": "IT"}, "document_types": ["Certificate of Incorporation"], "expected_entity_external_ids": ["SUP-IT-0001"], "forbidden_entity_external_ids": ["SUP-IT-0002", "SUP-LEGAL-0003", "PAT-ONC-0001"]},
    },
    {
        "id": "supplier_critical_missing_iso27001",
        "industry": "supplier_due_diligence",
        "query": "Which critical suppliers are missing ISO 27001 certificates?",
        "mode": "auto",
        "expect": {"capability": "completeness_check", "execution_source": "completeness_rules", "active_industry": "supplier_due_diligence", "metadata_filters": {"criticality": "Critical"}, "document_types": ["ISO 27001 Certificate"], "result_count": 0, "forbidden_risk_rating": "Critical"},
    },
    {
        "id": "supplier_it_missing_soc2",
        "industry": "supplier_due_diligence",
        "query": "Which IT suppliers are missing SOC 2 reports?",
        "mode": "auto",
        "expect": {"capability": "completeness_check", "execution_source": "completeness_rules", "active_industry": "supplier_due_diligence", "metadata_filters": {"supplier_category": "IT"}, "document_types": ["SOC 2 Report"], "expected_entity_external_ids": ["SUP-IT-0002"], "forbidden_entity_external_ids": ["SUP-IT-0001", "SUP-LEGAL-0003"]},
    },
    {
        "id": "healthcare_named_patient_eleanor_completeness",
        "industry": "healthcare",
        "query": "Use TrustVault to check patient evidence completeness for Eleanor Hughes.",
        "mode": "auto",
        "expect": {"capability": "completeness_check", "execution_source": "completeness_rules", "active_industry": "healthcare", "expected_entity_external_ids": ["PAT-ONC-0001"], "forbidden_entity_external_ids": ["PAT-ONC-0002", "PAT-CAR-0003"], "min_result_count": 1},
    },
    {
        "id": "selected_entity_summary_cust_000001",
        "industry": "financial_services",
        "query": "Use TrustVault to summarise entity CUST-000001.",
        "mode": "auto",
        "expect": {"capability": "entity_summary", "execution_source": "fits_index", "active_industry": "financial_services", "expected_entity_external_ids": ["CUST-000001"], "min_result_count": 1},
    },
    {
        "id": "selected_entity_containers_cust_000001",
        "industry": "financial_services",
        "query": "Use TrustVault to show the FITS containers available for CUST-000001.",
        "mode": "auto",
        "expect": {"capability": "entity_summary", "execution_source": "fits_index", "active_industry": "financial_services", "expected_entity_external_ids": ["CUST-000001"], "min_result_count": 1},
    },
    {
        "id": "selected_entity_evidence_counts_cust_000001",
        "industry": "financial_services",
        "query": "Use TrustVault to show the evidence counts by category and document type for CUST-000001.",
        "mode": "auto",
        "expect": {"capability": "entity_summary", "execution_source": "fits_index", "active_industry": "financial_services", "expected_entity_external_ids": ["CUST-000001"], "min_result_count": 1},
    },
    {
        "id": "supplier_data_processing_agreements_search",
        "industry": "supplier_due_diligence",
        "query": "Use TrustVault to search supplier due diligence evidence for data processing agreements.",
        "mode": "auto",
        "expect": {"capability": "evidence_search", "execution_source": "fits_index", "active_industry": "supplier_due_diligence", "document_types": ["Data Processing Agreement"]},
    },
    {
        "id": "healthcare_diagnostic_reports_oncology_search",
        "industry": "healthcare",
        "query": "Use TrustVault to search for diagnostic reports for oncology patients.",
        "mode": "auto",
        "expect": {"capability": "evidence_search", "execution_source": "fits_index", "active_industry": "healthcare", "metadata_filters": {"department": "Oncology"}, "document_types": ["Diagnostic Report"]},
    },
    {
        "id": "healthcare_list_patients",
        "industry": "healthcare",
        "query": "list patients.",
        "mode": "auto",
        "expect": {"capability": "entity_discovery", "execution_source": "entity_metadata", "active_industry": "healthcare", "min_result_count": 3, "expected_entity_external_ids": ["PAT-ONC-0001", "PAT-ONC-0002", "PAT-CAR-0003"]},
    },
    {
        "id": "healthcare_list_patients_oncology",
        "industry": "healthcare",
        "query": "list patients in oncology.",
        "mode": "auto",
        "expect": {"capability": "entity_discovery", "execution_source": "entity_metadata", "active_industry": "healthcare", "metadata_filters": {"department": "Oncology"}, "min_result_count": 2, "expected_entity_external_ids": ["PAT-ONC-0001", "PAT-ONC-0002"], "forbidden_entity_external_ids": ["PAT-CAR-0003", "SUP-IT-0001"]},
    },
    {
        "id": "supplier_list_suppliers",
        "industry": "supplier_due_diligence",
        "query": "list suppliers.",
        "mode": "auto",
        "expect": {"capability": "entity_discovery", "execution_source": "entity_metadata", "active_industry": "supplier_due_diligence", "min_result_count": 3, "expected_entity_external_ids": ["SUP-IT-0001", "SUP-IT-0002", "SUP-LEGAL-0003"]},
    },
    {
        "id": "supplier_list_it_suppliers",
        "industry": "supplier_due_diligence",
        "query": "list IT suppliers.",
        "mode": "auto",
        "expect": {"capability": "entity_discovery", "execution_source": "entity_metadata", "active_industry": "supplier_due_diligence", "metadata_filters": {"supplier_category": "IT"}, "min_result_count": 2, "expected_entity_external_ids": ["SUP-IT-0001", "SUP-IT-0002"], "forbidden_entity_external_ids": ["SUP-LEGAL-0003", "PAT-ONC-0001"]},
    },
    {
        "id": "supplier_list_critical_suppliers",
        "industry": "supplier_due_diligence",
        "query": "list critical suppliers.",
        "mode": "auto",
        "expect": {"capability": "entity_discovery", "execution_source": "entity_metadata", "active_industry": "supplier_due_diligence", "metadata_filters": {"criticality": "Critical"}, "min_result_count": 1, "expected_entity_external_ids": ["SUP-IT-0001"], "forbidden_entity_external_ids": ["SUP-IT-0002", "SUP-LEGAL-0003"]},
    },
]


def _industry_for_group(group: str) -> str:
    group_lower = group.lower()
    if "healthcare" in group_lower:
        return "healthcare"
    if "supplier" in group_lower:
        return "supplier_due_diligence"
    return "financial_services"


def _case_id(group: str, index: int, query: str) -> str:
    prefix = re.sub(r"[^a-z0-9]+", "_", group.lower()).strip("_")[:42]
    slug = re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")[:54]
    return f"sample_{prefix}_{index + 1:02d}_{slug}"


def _sample_case_expectation(group: str, example: str) -> dict[str, Any]:
    expectation: dict[str, Any] = {"smoke_only": True, "no_error": True}
    lower = example.lower()
    if "how many entities, containers and indexed evidence objects" in lower or "configured source folder" in lower or "archive status" in lower:
        return {**expectation, "capability": "archive_status", "execution_source": "archive_status", "active_industry_is_null": True, "context_source": "not_applicable_archive_status", "min_result_count": 1}
    if "search the archive for onboarding documentation for high risk entities in guernsey" in lower:
        return {**expectation, "active_industry": "financial_services", "capability": "evidence_search", "execution_source": "fits_index", "risk_rating": "High", "jurisdiction": "Guernsey"}
    if "list high risk entities in guernsey" in lower:
        return {**expectation, "active_industry": "financial_services", "capability": "entity_discovery", "execution_source": "entity_metadata", "risk_rating": "High", "jurisdiction": "Guernsey", "min_result_count": 2, "expected_entity_external_ids": ["CUST-000046", "CUST-999001"]}
    if "check patient evidence completeness for eleanor hughes" in lower:
        return {**expectation, "active_industry": "healthcare", "capability": "completeness_check", "execution_source": "completeness_rules", "expected_entity_external_ids": ["PAT-ONC-0001"], "forbidden_entity_external_ids": ["PAT-ONC-0002", "PAT-CAR-0003"], "min_result_count": 1}
    if "summarise entity cust-000001" in lower or "summarize entity cust-000001" in lower or "fits containers available for cust-000001" in lower or "evidence counts by category" in lower:
        return {**expectation, "active_industry": "financial_services", "capability": "entity_summary", "execution_source": "fits_index", "expected_entity_external_ids": ["CUST-000001"], "min_result_count": 1}
    if "diagnostic reports for oncology patients" in lower:
        return {**expectation, "active_industry": "healthcare", "capability": "evidence_search", "execution_source": "fits_index", "metadata_filters": {"department": "Oncology"}, "document_types": ["Diagnostic Report"]}
    if "data processing agreements" in lower:
        return {**expectation, "active_industry": "supplier_due_diligence", "capability": "evidence_search", "execution_source": "fits_index", "document_types": ["Data Processing Agreement"]}
    if "list patients in oncology" in lower:
        return {**expectation, "active_industry": "healthcare", "capability": "entity_discovery", "execution_source": "entity_metadata", "metadata_filters": {"department": "Oncology"}, "min_result_count": 2, "expected_entity_external_ids": ["PAT-ONC-0001", "PAT-ONC-0002"], "forbidden_entity_external_ids": ["PAT-CAR-0003", "SUP-IT-0001"]}
    if "list patients" in lower:
        return {**expectation, "active_industry": "healthcare", "capability": "entity_discovery", "execution_source": "entity_metadata", "min_result_count": 3, "expected_entity_external_ids": ["PAT-ONC-0001", "PAT-ONC-0002", "PAT-CAR-0003"]}
    if "list it suppliers" in lower:
        return {**expectation, "active_industry": "supplier_due_diligence", "capability": "entity_discovery", "execution_source": "entity_metadata", "metadata_filters": {"supplier_category": "IT"}, "min_result_count": 2, "expected_entity_external_ids": ["SUP-IT-0001", "SUP-IT-0002"], "forbidden_entity_external_ids": ["SUP-LEGAL-0003", "PAT-ONC-0001"]}
    if "list critical suppliers" in lower:
        return {**expectation, "active_industry": "supplier_due_diligence", "capability": "entity_discovery", "execution_source": "entity_metadata", "metadata_filters": {"criticality": "Critical"}, "min_result_count": 1, "expected_entity_external_ids": ["SUP-IT-0001"], "forbidden_entity_external_ids": ["SUP-IT-0002", "SUP-LEGAL-0003"]}
    if "list suppliers" in lower:
        return {**expectation, "active_industry": "supplier_due_diligence", "capability": "entity_discovery", "execution_source": "entity_metadata", "min_result_count": 3, "expected_entity_external_ids": ["SUP-IT-0001", "SUP-IT-0002", "SUP-LEGAL-0003"]}
    if "supplier" in group.lower() or "supplier" in lower:
        expectation["active_industry"] = "supplier_due_diligence"
    elif "healthcare" in group.lower() or any(term in lower for term in ("patient", "patients", "oncology", "dr jones", "cancer", "consent")):
        expectation["active_industry"] = "healthcare"
    elif any(term in lower for term in ("customer", "customers", "entity", "entities", "cdd", "onboarding", "screening", "source of funds")):
        expectation["active_industry"] = "financial_services"
    return expectation


def _sample_cases_from_scenarios() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for scenario in ENRICHED_QUERY_SCENARIOS:
        group = str(scenario.get("group") or "Examples")
        industry = _industry_for_group(group)
        for index, example in enumerate(scenario.get("examples") or []):
            cases.append({"id": _case_id(group, index, str(example)), "industry": industry, "query": str(example), "mode": "auto", "source": "search_query_page_example", "scenario_group": group, "expect": _sample_case_expectation(group, str(example))})
    return cases


QUERY_REGRESSION_TEST_CASES: list[dict[str, Any]] = [
    *CORE_QUERY_REGRESSION_TEST_CASES,
    *_sample_cases_from_scenarios(),
]
