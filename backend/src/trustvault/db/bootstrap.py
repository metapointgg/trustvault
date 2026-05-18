import logging
import time

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from trustvault.db.base import Base
from trustvault.db.models import (  # noqa: F401
    AppSetting,
    AuditEvent,
    CompletenessResult,
    CompletenessRun,
    Entity,
    EntityContainerVersion,
    EvidenceObject,
    ExtractionEvent,
    FitsIndexEntry,
    Job,
    LicenceStatus,
    RetentionPolicy,
    Ruleset,
    RulesetRule,
    SourceSystem,
    User,
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
    """Initial local bootstrap for the controlled deployment build.

    Production deployments should use Alembic migrations. The local bootstrap keeps
    docker-compose usable while the production schema is still stabilising.
    """
    wait_for_database()
    Base.metadata.create_all(bind=engine)
    _apply_local_compatibility_migrations()

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        connection.commit()


def _apply_local_compatibility_migrations() -> None:
    """Small additive migrations for existing local developer databases.

    This prevents older docker-compose volumes from failing when additive columns
    or tables are introduced during the controlled deployment build. Formal
    production deployments should still use Alembic revisions.
    """
    statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS roles JSONB NOT NULL DEFAULT '[]'::jsonb",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email_unique ON users (email)",
        "CREATE TABLE IF NOT EXISTS app_settings ("
        "key VARCHAR(200) PRIMARY KEY, "
        "value_json JSONB NOT NULL DEFAULT '{}'::jsonb, "
        "value_type VARCHAR(50) NOT NULL DEFAULT 'string', "
        "category VARCHAR(100) NOT NULL DEFAULT 'general', "
        "description TEXT, "
        "is_secret BOOLEAN NOT NULL DEFAULT false, "
        "is_editable BOOLEAN NOT NULL DEFAULT true, "
        "updated_by_user_id VARCHAR(200), "
        "created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), "
        "updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()"
        ")",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
