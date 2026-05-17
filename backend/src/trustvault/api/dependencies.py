from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from trustvault.audit.logger import AuditLogger
from trustvault.db.session import get_db


def get_database() -> Generator[Session, None, None]:
    yield from get_db()


def get_audit_logger(db: Session = Depends(get_database)) -> AuditLogger:
    return AuditLogger(db)
