"""Add shelf alert tracking columns to alerts table.

Revision ID: 0005_shelf_alert_fields
Revises: 0004_unified_intel_events
Create Date: 2026-11-12 19:40:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005_shelf_alert_fields"
down_revision: Union[str, None] = "0004_unified_intel_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    # Safely add columns if not already present
    op.add_column(
        "alerts",
        sa.Column("shelf_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("shelf_occupancy", sa.Float(), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("detected_products", sa.Integer(), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("annotated_image_url", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_alerts_shelf_id",
        "alerts",
        ["shelf_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_alerts_shelf_id", table_name="alerts")
    op.drop_column("alerts", "annotated_image_url")
    op.drop_column("alerts", "detected_products")
    op.drop_column("alerts", "shelf_occupancy")
    op.drop_column("alerts", "shelf_id")
