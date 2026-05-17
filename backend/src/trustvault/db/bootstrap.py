import logging
import time

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from trustvault.db.base import Base
from trustvault.db.models import (  # noqa: F401
    AuditEvent,
    Entity,
    EntityContainerVersion,
    EvidenceObject,
    FitsIndexEntry,
    Job,
    LicenceStatus,
)
from trustvault.db.session import engine

logger = logging.getLogger(__name__)


def wait_for_database(max_attempts: int = 30, delay_seconds: int = 2) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except OperationalError:
            logger.info("Database not ready yet; attempt %s/%s", attempt, max_attempts)
            time.sleep(delay_seconds)

    raise RuntimeError("Database did not become ready in time")


def initialise_database() -> None:
    """Create database tables for the initial controlled deployment skeleton.

    Alembic migrations should replace this for production-grade schema management once
    the first model set stabilises.
    """
    wait_for_database()
    Base.metadata.create_all(bind=engine)

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        connection.commit()
