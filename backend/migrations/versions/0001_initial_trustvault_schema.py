"""Initial TrustVault schema

Revision ID: 0001_initial_trustvault_schema
Revises:
Create Date: 2026-05-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_trustvault_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The controlled deployment branch currently bootstraps from SQLAlchemy metadata
    # for local docker-compose. This migration establishes the Alembic baseline. For
    # production deployment, generate the concrete DDL with:
    #   alembic revision --autogenerate -m "initial trustvault schema"
    # after validating the final model set for the target database.
    pass


def downgrade() -> None:
    pass
