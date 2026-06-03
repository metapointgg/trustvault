from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class VocabularyItem:
    canonical_value: str
    aliases: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"canonical_value": self.canonical_value, "aliases": list(self.aliases)}


@dataclass(frozen=True)
class VocabularyList:
    list_key: str
    label: str
    field_binding: str | None = None
    value_type: str = "string"
    is_filterable: bool = True
    is_requirement_dimension: bool = False
    items: tuple[VocabularyItem, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["items"] = [item.to_dict() for item in self.items]
        return data


@dataclass(frozen=True)
class RequirementGroup:
    key: str
    label: str
    aliases: tuple[str, ...] = ()
    default_document_types: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "aliases": list(self.aliases),
            "default_document_types": list(self.default_document_types),
        }


@dataclass(frozen=True)
class IndustryPack:
    key: str
    label: str
    description: str
    entity_type_terms: tuple[str, ...]
    vocabulary_lists: tuple[VocabularyList, ...] = field(default_factory=tuple)
    requirement_groups: tuple[RequirementGroup, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "entity_type_terms": list(self.entity_type_terms),
            "vocabulary_lists": [item.to_dict() for item in self.vocabulary_lists],
            "requirement_groups": [item.to_dict() for item in self.requirement_groups],
        }


BASE_VOCABULARY = (
    VocabularyList(
        "risk_rating",
        "Risk rating",
        field_binding="risk_rating",
        items=(
            VocabularyItem("High", ("high risk", "higher risk")),
            VocabularyItem("Medium", ("medium risk", "standard risk")),
            VocabularyItem("Low", ("low risk", "lower risk")),
            VocabularyItem("Critical", ("critical risk", "very high risk")),
        ),
    ),
    VocabularyList(
        "evidence_status",
        "Evidence status",
        field_binding="evidence_status",
        items=(
            VocabularyItem("Present", ("supplied", "provided", "held", "available")),
            VocabularyItem("Missing", ("missing", "not supplied", "not provided", "outstanding", "absent")),
            VocabularyItem("Expired", ("expired", "out of date", "stale")),
            VocabularyItem("Incomplete", ("incomplete", "partial")),
        ),
    ),
)


INDUSTRY_PACKS: dict[str, IndustryPack] = {
    "financial_services": IndustryPack(
        key="financial_services",
        label="Financial Services",
        description="KYC, CDD, onboarding, account opening, periodic review and regulated financial-services evidence.",
        entity_type_terms=("entity", "entities", "customer", "customers", "client", "clients", "account holder", "beneficial owner", "trust", "company", "fund"),
        vocabulary_lists=BASE_VOCABULARY
        + (
            VocabularyList(
                "jurisdiction",
                "Jurisdiction",
                field_binding="jurisdiction",
                items=(
                    VocabularyItem("Guernsey", ("gg",)),
                    VocabularyItem("Jersey", ("je",)),
                    VocabularyItem("United Kingdom", ("uk", "great britain", "britain")),
                    VocabularyItem("Isle of Man", ("iom",)),
                    VocabularyItem("Malta", ("mt",)),
                ),
            ),
            VocabularyList(
                "document_type",
                "Document type",
                is_filterable=False,
                is_requirement_dimension=True,
                items=(
                    VocabularyItem("Passport", ("identity document", "id evidence")),
                    VocabularyItem("Proof of Address", ("poa", "utility bill", "address evidence")),
                    VocabularyItem("Source of Funds", ("sof", "funds evidence", "source of funds evidence")),
                    VocabularyItem("Source of Wealth", ("sow", "wealth evidence", "source of wealth evidence")),
                    VocabularyItem("Account Opening Application", ("application", "onboarding form")),
                    VocabularyItem("CDD Review", ("kyc review", "customer due diligence")),
                    VocabularyItem("Screening Evidence", ("sanctions screening", "pep screening", "adverse media")),
                    VocabularyItem("Certificate of Incorporation", ("coi", "incorporation certificate")),
                    VocabularyItem("Beneficial Ownership Evidence", ("ubo", "beneficial owner evidence")),
                ),
            ),
        ),
        requirement_groups=(
            RequirementGroup("onboarding", "Onboarding", ("onboarding documentation", "onboarding pack", "account opening pack"), ("Account Opening Application", "Passport", "Proof of Address")),
            RequirementGroup("kyc_cdd", "KYC / CDD", ("kyc", "cdd", "customer due diligence"), ("CDD Review", "Screening Evidence")),
            RequirementGroup("periodic_review", "Periodic Review", ("review", "annual review", "periodic cdd"), ("CDD Review",)),
        ),
    ),
    "healthcare": IndustryPack(
        key="healthcare",
        label="Healthcare",
        description="Patient, clinician, pathway, consent, referral, treatment and clinical evidence.",
        entity_type_terms=("patient", "patients", "clinician", "doctor", "consultant", "department", "referral"),
        vocabulary_lists=BASE_VOCABULARY
        + (
            VocabularyList("department", "Department", field_binding="department", items=(VocabularyItem("Oncology", ("cancer", "cancer care")), VocabularyItem("Cardiology", ("heart",)), VocabularyItem("Radiology", ("imaging",)))),
            VocabularyList("responsible_person", "Responsible clinician", field_binding="responsible_person", items=(VocabularyItem("Dr Jones", ("doctor jones", "jones")), VocabularyItem("Dr Smith", ("doctor smith", "smith")))),
            VocabularyList("document_type", "Document type", is_filterable=False, is_requirement_dimension=True, items=(VocabularyItem("Consent Form", ("consent", "patient consent")), VocabularyItem("Referral Letter", ("gp letter", "referral")), VocabularyItem("Treatment Plan", ("care plan", "clinical plan")), VocabularyItem("Diagnostic Report", ("diagnostics", "diagnostic", "diagnostic report", "diagnostic reports", "reports", "report")),)),
        ),
        requirement_groups=(RequirementGroup("patient_onboarding", "Patient Onboarding", ("patient onboarding",), ("Referral Letter", "Medical History")), RequirementGroup("treatment_consent", "Treatment Consent", ("consent", "consent form", "treatment consent"), ("Consent Form",))),
    ),
    "supplier_due_diligence": IndustryPack(
        key="supplier_due_diligence",
        label="Supplier / Vendor Due Diligence",
        description="Supplier onboarding, critical supplier review, cyber due diligence, contracts and annual reviews.",
        entity_type_terms=("supplier", "suppliers", "vendor", "vendors", "contractor", "service provider"),
        vocabulary_lists=BASE_VOCABULARY
        + (
            VocabularyList("supplier_category", "Supplier category", field_binding="supplier_category", items=(VocabularyItem("IT", ("technology", "tech", "software")), VocabularyItem("Legal", ("law firm", "legal services")), VocabularyItem("Facilities", ("property services", "premises")))),
            VocabularyList("document_type", "Document type", is_filterable=False, is_requirement_dimension=True, items=(VocabularyItem("Certificate of Incorporation", ("coi", "incorporation certificate", "company incorporation certificate")), VocabularyItem("Insurance Certificate", ("insurance", "public liability")), VocabularyItem("ISO 27001 Certificate", ("iso27001", "iso 27001", "information security certificate")), VocabularyItem("SOC 2 Report", ("soc2", "soc 2", "service organisation control")), VocabularyItem("Data Processing Agreement", ("dpa", "data processing agreement", "data processing agreements")),)),
        ),
        requirement_groups=(RequirementGroup("supplier_onboarding", "Supplier Onboarding", ("supplier onboarding", "vendor onboarding"), ("Certificate of Incorporation", "Insurance Certificate")), RequirementGroup("cyber_due_diligence", "Cyber Due Diligence", ("cyber", "security review"), ("ISO 27001 Certificate", "SOC 2 Report"))),
    ),
    "insurance": IndustryPack("insurance", "Insurance", "Policyholder, policy, broker, claims and underwriting evidence.", ("policyholder", "claimant", "broker", "policy", "claim")),
    "legal_professional_services": IndustryPack("legal_professional_services", "Legal / Professional Services", "Client, matter, AML, conflict and case evidence.", ("client", "matter", "case", "counterparty")),
    "corporate_services": IndustryPack("corporate_services", "Corporate Services / Trust / Fiduciary", "Company, trust, foundation, beneficial owner and governance evidence.", ("company", "trust", "foundation", "beneficial owner", "director", "shareholder")),
    "human_resources": IndustryPack("human_resources", "Human Resources", "Employee, contractor, right-to-work, training and role-compliance evidence.", ("employee", "contractor", "candidate", "worker")),
    "property_real_estate": IndustryPack("property_real_estate", "Property / Real Estate", "Property, tenant, landlord, sale, lease and transaction evidence.", ("property", "tenant", "landlord", "buyer", "seller")),
    "education": IndustryPack("education", "Education", "Student, parent, guardian, safeguarding, admissions and consent evidence.", ("student", "parent", "guardian", "teacher", "course")),
    "charity_non_profit": IndustryPack("charity_non_profit", "Charity / Non-Profit", "Donor, beneficiary, volunteer, trustee, grant and safeguarding evidence.", ("donor", "beneficiary", "volunteer", "trustee", "grant applicant")),
    "public_sector": IndustryPack("public_sector", "Public Sector / Government", "Citizen, applicant, case, licence, permit and departmental evidence.", ("citizen", "applicant", "case", "licence", "permit")),
    "retail_consumer_operations": IndustryPack("retail_consumer_operations", "Retail / Consumer Operations", "Customer, order, complaint, return, warranty and supplier evidence.", ("customer", "order", "complaint", "return", "supplier")),
    "custom": IndustryPack("custom", "Custom", "Empty configurable industry pack for client-specific vocabularies.", ("entity", "entities")),
}


def list_industry_packs() -> list[dict[str, Any]]:
    return [{"key": pack.key, "label": pack.label, "description": pack.description} for pack in INDUSTRY_PACKS.values()]


def get_industry_pack(key: str | None) -> IndustryPack:
    normalised = str(key or "financial_services").strip().lower()
    return INDUSTRY_PACKS.get(normalised) or INDUSTRY_PACKS["financial_services"]
