from fastapi import HTTPException, status

from trustvault.licensing.validator import LicenceValidator
from trustvault.settings import get_settings

MODULE_PERMISSION_MAP = {
    "ingestion:submit": "continuous_ingestion",
    "containers:rebuild": "core_archive",
    "integrity:run": "core_archive",
    "rulesets:edit": "ruleset_builder",
    "completeness:run": "completeness_rules",
    "retention:manage": "retention_legal_hold",
    "export:request": "evidence_pack_export",
    "export:approve": "evidence_pack_export",
    "audit:read": "audit_log",
    "search:execute": "direct_fits_search",
}


def check_licence_for_permission(permission: str) -> None:
    settings = get_settings()
    if not settings.licence_enforcement_enabled:
        return
    result = LicenceValidator(settings.licence_file).check()
    if result.state in {"missing", "invalid", "not_yet_valid"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Licence unavailable: {result.message}")
    if result.state == "expired" and permission not in {"customers:read", "evidence:read", "search:execute", "audit:read"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Licence expired; write/export/AI functions are disabled")
    module = MODULE_PERMISSION_MAP.get(permission)
    if module and module not in result.modules:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Licence does not include module: {module}")
