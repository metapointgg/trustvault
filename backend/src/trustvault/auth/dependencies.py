from collections.abc import Generator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from trustvault.auth.models import ANONYMOUS_USER, CurrentUser
from trustvault.auth.local_auth import LocalAuthService
from trustvault.auth.permissions import has_permission, permissions_for_roles
from trustvault.db.models import User
from trustvault.db.session import get_db
from trustvault.licensing.dependencies import check_licence_for_permission
from trustvault.settings import get_settings


def _get_db() -> Generator[Session, None, None]:
    yield from get_db()


def _current_user_from_db_user(user: User) -> CurrentUser:
    roles = [str(role) for role in (user.roles or [])]
    return CurrentUser(
        subject=str(user.id),
        email=user.email,
        display_name=user.display_name,
        roles=roles,
        permissions=permissions_for_roles(roles),
    )


def get_current_user(
    authorization: str | None = Header(default=None),
    x_trustvault_user: str | None = Header(default=None),
    x_trustvault_roles: str | None = Header(default=None),
    db: Session = Depends(_get_db),
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

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    if settings.auth_mode == "local":
        token = authorization.split(" ", 1)[1].strip()
        return _current_user_from_db_user(LocalAuthService(db).current_user_from_token(token))

    # Controlled deployment scaffold for upstream-authenticated private deployments.
    # Only trust forwarded identity headers when explicitly configured away from
    # local auth. The default local mode validates the bearer token above.
    if not x_trustvault_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Trusted upstream user header is required for non-local auth mode",
        )
    roles = [role.strip() for role in (x_trustvault_roles or "Read-only Auditor").split(",") if role.strip()]
    return CurrentUser(
        subject=x_trustvault_user,
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
