ROLE_PERMISSIONS: dict[str, list[str]] = {
    "Admin": ["*"],
    "Compliance Manager": [
        "customers:read", "customers:update", "evidence:read", "evidence:preview", "evidence:classify", "search:execute",
        "ingestion:submit", "containers:rebuild", "integrity:run", "rulesets:edit",
        "completeness:run", "retention:manage", "export:request", "export:approve",
        "audit:read", "licence:admin", "settings:read", "settings:edit",
    ],
    "Compliance Analyst": [
        "customers:read", "customers:update", "evidence:read", "evidence:preview", "evidence:classify", "search:execute",
        "completeness:run", "integrity:run", "export:request",
    ],
    "Read-only Auditor": [
        "customers:read", "evidence:read", "search:execute", "audit:read", "integrity:run",
    ],
    "Ingestion Operator": [
        "customers:read", "customers:update", "evidence:read", "evidence:classify", "ingestion:submit", "containers:rebuild", "settings:read",
    ],
    "Export Approver": [
        "customers:read", "evidence:read", "evidence:preview", "export:request", "export:approve",
    ],
    "local_admin": ["*"],
    "anonymous": [],
}


def permissions_for_roles(roles: list[str]) -> list[str]:
    permissions: set[str] = set()
    for role in roles:
        role_permissions = ROLE_PERMISSIONS.get(role, [])
        if "*" in role_permissions:
            return ["*"]
        permissions.update(role_permissions)
    return sorted(permissions)


def has_permission(user_permissions: list[str], required: str) -> bool:
    return "*" in user_permissions or required in user_permissions
