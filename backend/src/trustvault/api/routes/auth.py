from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from trustvault.api.dependencies import get_current_user, get_database, require_admin
from trustvault.auth.local_auth import ALL_ROLES, LocalAuthService, public_user
from trustvault.db.models import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    verifier: str = Field(min_length=1)


class CreateUserRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1)
    roles: list[str] = Field(default_factory=list)
    status: str = "active"


class UpdateUserRequest(BaseModel):
    display_name: str | None = None
    roles: list[str] | None = None
    status: str | None = None


@router.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_database)) -> dict[str, Any]:
    return LocalAuthService(db).login(request.email, request.verifier)


@router.get("/me")
def me(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    return public_user(current_user)


@router.get("/roles")
def roles(current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {"roles": ALL_ROLES, "current_user": public_user(current_user)}


@router.get("/users")
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_database)) -> dict[str, Any]:
    users = LocalAuthService(db).list_users()
    return {"user_count": len(users), "users": users}


@router.post("/users")
def create_user(request: CreateUserRequest, _: User = Depends(require_admin), db: Session = Depends(get_database)) -> dict[str, Any]:
    user = User(
        external_subject=f"local:{request.email.lower().strip()}",
        email=request.email.lower().strip(),
        display_name=request.display_name,
        status=request.status,
        roles=LocalAuthService(db)._normalise_roles(request.roles),
        metadata_json={"identity_provider": "local", "activation_pending": True},
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return public_user(user)


@router.patch("/users/{user_id}")
def update_user(user_id: str, request: UpdateUserRequest, _: User = Depends(require_admin), db: Session = Depends(get_database)) -> dict[str, Any]:
    return LocalAuthService(db).update_user(
        user_id,
        display_name=request.display_name,
        roles=request.roles,
        status_value=request.status,
    )
