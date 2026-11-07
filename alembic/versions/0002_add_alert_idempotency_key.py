"""Add idempotency_key to alerts table.

Revision ID: 0002_add_alert_idempotency_key
Revises: 0001_initial_schema
Create Date: 2026-11-06 13:45:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_add_alert_idempotency_key"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add column as nullable first to safely handle existing rows
    op.add_column(
        "alerts",
        sa.Column("idempotency_key", sa.String(64), nullable=True),
    )

    # 2. Backfill any existing records with a deterministic unique fallback
    op.execute(
        "UPDATE alerts SET idempotency_key = MD5(id) WHERE idempotency_key IS NULL;"
    )

    # 3. Enforce NOT NULL constraint
    op.alter_column("alerts", "idempotency_key", nullable=False)

    # 4. Enforce unique index / constraint for conflict resolution
    op.create_index(
        "ix_alerts_idempotency_key",
        "alerts",
        ["idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_alerts_idempotency_key", table_name="alerts")
    op.drop_column("alerts", "idempotency_key")
