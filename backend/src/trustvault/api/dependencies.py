from collections.abc import Generator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from trustvault.audit.logger import AuditLogger
from trustvault.auth.local_auth import LocalAuthService, ROLE_ADMIN
from trustvault.db.models import User
from trustvault.db.session import get_db
from trustvault.settings import get_settings


def get_database() -> Generator[Session, None, None]:
    yield from get_db()


def get_audit_logger(db: Session = Depends(get_database)) -> AuditLogger:
    return AuditLogger(db)


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_database),
) -> User:
    settings = get_settings()
    if not settings.auth_required or settings.auth_mode == "disabled":
        bootstrap = LocalAuthService(db)
        bootstrap.bootstrap_initial_admin()
        users = bootstrap.list_users()
        if users:
            user = db.get(User, users[0]["id"])
            if user is not None:
                return user
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No local user available")

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    return LocalAuthService(db).current_user_from_token(token)


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if ROLE_ADMIN not in (current_user.roles or []):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user
