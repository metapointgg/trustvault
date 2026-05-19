from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from trustvault.db.models import User
from trustvault.settings import get_settings

ROLE_ADMIN = "Admin"
ROLE_COMPLIANCE_MANAGER = "Compliance Manager"
ROLE_COMPLIANCE_ANALYST = "Compliance Analyst"
ROLE_READ_ONLY_AUDITOR = "Read-only Auditor"
ROLE_INGESTION_OPERATOR = "Ingestion Operator"
ROLE_EXPORT_APPROVER = "Export Approver"

ALL_ROLES = [
    ROLE_ADMIN,
    ROLE_COMPLIANCE_MANAGER,
    ROLE_COMPLIANCE_ANALYST,
    ROLE_READ_ONLY_AUDITOR,
    ROLE_INGESTION_OPERATOR,
    ROLE_EXPORT_APPROVER,
]


def now_utc() -> datetime:
    return datetime.now(UTC)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return f"pbkdf2_sha256$210000${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(digest_b64.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _b64_json(data: dict[str, Any]) -> str:
    raw = json.dumps(data, separators=(",", ":"), default=str).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64_json(value: str) -> dict[str, Any]:
    padded = value + "=" * (-len(value) % 4)
    return json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))


def _sign(message: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def create_access_token(user: User) -> str:
    settings = get_settings()
    if not settings.auth_token_secret:
        raise HTTPException(status_code=500, detail="TRUSTVAULT_AUTH_TOKEN_SECRET is not configured")
    header = _b64_json({"alg": "HS256", "typ": "TVJWT"})
    payload = _b64_json(
        {
            "sub": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "roles": user.roles or [],
            "iat": int(now_utc().timestamp()),
            "exp": int((now_utc() + timedelta(minutes=settings.auth_token_ttl_minutes)).timestamp()),
        }
    )
    signing_input = f"{header}.{payload}"
    return f"{signing_input}.{_sign(signing_input, settings.auth_token_secret)}"


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.auth_token_secret:
        raise HTTPException(status_code=500, detail="TRUSTVAULT_AUTH_TOKEN_SECRET is not configured")
    try:
        header, payload, signature = token.split(".", 2)
        signing_input = f"{header}.{payload}"
        expected = _sign(signing_input, settings.auth_token_secret)
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")
        data = _unb64_json(payload)
        if int(data.get("exp", 0)) < int(now_utc().timestamp()):
            raise ValueError("Token expired")
        return data
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token") from exc


def public_user(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "external_subject": user.external_subject,
        "email": user.email,
        "display_name": user.display_name,
        "status": user.status,
        "roles": user.roles or [],
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


class LocalAuthService:
    def __init__(self, db: Session):
        self.db = db

    def bootstrap_initial_admin(self) -> None:
        settings = get_settings()
        existing_admin = self.db.scalars(select(User).where(User.roles.contains([ROLE_ADMIN]))).first()
        if existing_admin is not None:
            return
        if not settings.local_admin_password:
            return
        user = self.db.scalars(select(User).where(User.email == settings.local_admin_email)).first()
        if user is None:
            user = User(
                external_subject=f"local:{settings.local_admin_email}",
                email=settings.local_admin_email,
                display_name=settings.local_admin_display_name,
                status="active",
                password_hash=hash_password(settings.local_admin_password),
                roles=[ROLE_ADMIN],
                metadata_json={"bootstrap_admin": True},
            )
            self.db.add(user)
        else:
            user.password_hash = hash_password(settings.local_admin_password)
            user.roles = sorted(set([*(user.roles or []), ROLE_ADMIN]))
            user.status = "active"
        self.db.commit()

    def login(self, email: str, password: str) -> dict[str, Any]:
        user = self.db.scalars(select(User).where(User.email == email.lower().strip())).first()
        if user is None or user.status != "active" or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        user.last_login_at = now_utc()
        self.db.commit()
        self.db.refresh(user)
        return {"access_token": create_access_token(user), "token_type": "bearer", "user": public_user(user)}

    def current_user_from_token(self, token: str) -> User:
        payload = decode_access_token(token)
        user = self.db.get(User, payload.get("sub"))
        if user is None or user.status != "active":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not active")
        return user

    def require_role(self, user: User, role: str) -> None:
        if role not in (user.roles or []):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Requires role: {role}")

    def list_users(self) -> list[dict[str, Any]]:
        rows = self.db.scalars(select(User).order_by(User.created_at.desc())).all()
        return [public_user(row) for row in rows]

    def create_user(self, *, email: str, display_name: str, password: str, roles: list[str], status_value: str = "active") -> dict[str, Any]:
        clean_email = email.lower().strip()
        existing = self.db.scalars(select(User).where(User.email == clean_email)).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail="User email already exists")
        user = User(
            external_subject=f"local:{clean_email}",
            email=clean_email,
            display_name=display_name,
            status=status_value,
            password_hash=hash_password(password),
            roles=self._normalise_roles(roles),
            metadata_json={"identity_provider": "local"},
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return public_user(user)

    def update_user(self, user_id: str, *, display_name: str | None = None, roles: list[str] | None = None, status_value: str | None = None, password: str | None = None) -> dict[str, Any]:
        user = self.db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        if display_name is not None:
            user.display_name = display_name
        if roles is not None:
            user.roles = self._normalise_roles(roles)
        if status_value is not None:
            user.status = status_value
        if password:
            user.password_hash = hash_password(password)
        self.db.commit()
        self.db.refresh(user)
        return public_user(user)

    def _normalise_roles(self, roles: list[str]) -> list[str]:
        allowed = set(ALL_ROLES)
        cleaned = []
        for role in roles:
            if role not in allowed:
                raise HTTPException(status_code=400, detail=f"Unsupported role: {role}")
            if role not in cleaned:
                cleaned.append(role)
        return cleaned or [ROLE_READ_ONLY_AUDITOR]
