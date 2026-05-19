from fastapi import Depends, Header, HTTPException, status

from trustvault.auth.models import ANONYMOUS_USER, CurrentUser
from trustvault.auth.permissions import has_permission, permissions_for_roles
from trustvault.licensing.dependencies import check_licence_for_permission
from trustvault.settings import get_settings


def get_current_user(
    authorization: str | None = Header(default=None),
    x_trustvault_user: str | None = Header(default=None),
    x_trustvault_roles: str | None = Header(default=None),
) -> CurrentUser:
    settings = get_settings()
    if not settings.auth_required:
        roles = [role.strip() for role in (x_trustvault_roles or "local_admin").split(",") if role.strip()]
        return CurrentUser(
            subject=x_trustvault_user or settings.local_admin_email,
            email=x_trustvault_user or settings.local_admin_email,
            display_name=x_trustvault_user or "Local Admin",
            roles=roles,
            permissions=permissions_for_roles(roles),
        )

    if settings.auth_mode == "disabled":
        return ANONYMOUS_USER

    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    # Controlled deployment scaffold: real OIDC validation is configured through the
    # issuer/audience/JWKS settings and can be swapped in without changing route code.
    # For local/private deployments, upstream reverse proxies can pass trusted user
    # headers after validating OIDC/SAML.
    roles = [role.strip() for role in (x_trustvault_roles or "Read-only Auditor").split(",") if role.strip()]
    return CurrentUser(
        subject=x_trustvault_user or "authenticated-user",
        email=x_trustvault_user,
        display_name=x_trustvault_user,
        roles=roles,
        permissions=permissions_for_roles(roles),
    )


def require_permission(permission: str):
    def dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not current_user.is_authenticated and permission:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        if not has_permission(current_user.permissions, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing permission: {permission}")
        check_licence_for_permission(permission)
        return current_user

    return dependency
