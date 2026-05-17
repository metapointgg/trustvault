from collections.abc import Generator

from sqlalchemy.orm import Session

from trustvault.audit.logger import AuditLogger
from trustvault.db.session import get_db


def get_audit_logger(db: Session) -> AuditLogger:
    return AuditLogger(db)


def get_database() -> Generator[Session, None, None]:
    yield from get_db()
