"""repair missing collector tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-24

This migration is intentionally idempotent. Some early Render deployments had
an alembic_version row for 0001 even though the application tables were absent.
The repair creates every table still missing and preserves any existing data.
"""

from alembic import op

from btc_engine.storage.models import Base

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # No destructive downgrade: this revision repairs schema state and must not
    # drop populated collector tables.
    pass
