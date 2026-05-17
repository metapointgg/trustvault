from sqlalchemy import text

from trustvault.db.base import Base
from trustvault.db.models import AuditEvent, Entity, EvidenceObject, Job, LicenceStatus  # noqa: F401
from trustvault.db.session import engine


def initialise_database() -> None:
    """Create database tables for the initial controlled deployment skeleton.

    Alembic migrations should replace this for production-grade schema management once
    the first model set stabilises.
    """
    Base.metadata.create_all(bind=engine)

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        connection.commit()
