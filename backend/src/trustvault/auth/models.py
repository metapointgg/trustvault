from dataclasses import dataclass, field


@dataclass(frozen=True)
class CurrentUser:
    subject: str
    email: str | None = None
    display_name: str | None = None
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    is_authenticated: bool = True


ANONYMOUS_USER = CurrentUser(
    subject="anonymous",
    email=None,
    display_name="Anonymous",
    roles=["anonymous"],
    permissions=[],
    is_authenticated=False,
)
