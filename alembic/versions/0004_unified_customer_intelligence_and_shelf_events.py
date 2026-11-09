"""Add daily_visitors, shelf_zones, and retail_events tables for unified intelligence.

Revision ID: 0004_unified_intel_events
Revises: 0003_customer_journey_rag
Create Date: 2026-11-09 07:45:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004_unified_intel_events"
down_revision: Union[str, None] = "0003_customer_journey_rag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fallback json type for sqlite/postgres compatibility in tests
    json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")

    # 1. Daily Visitors Table
    op.create_table(
        "daily_visitors",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("store_id", sa.String(length=64), nullable=False),
        sa.Column("local_date", sa.String(length=10), nullable=False),
        sa.Column("anonymous_label", sa.String(length=32), nullable=False),
        sa.Column("first_seen_at", sa.Float(), nullable=False),
        sa.Column("last_seen_at", sa.Float(), nullable=False),
        sa.Column("total_visits", sa.Integer(), server_default="1", nullable=False),
        sa.Column("total_dwell_seconds", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("cameras_seen", json_type, server_default="[]", nullable=False),
        sa.Column("feature_embedding", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("store_id", "local_date", "anonymous_label", name="uq_daily_visitors_store_date_label"),
    )
    op.create_index("ix_daily_visitors_store_id", "daily_visitors", ["store_id"])
    op.create_index("ix_daily_visitors_local_date", "daily_visitors", ["local_date"])
    op.create_index("ix_daily_visitors_store_date", "daily_visitors", ["store_id", "local_date"])

    # 2. Shelf Zones Table
    op.create_table(
        "shelf_zones",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("store_id", sa.String(length=64), nullable=False),
        sa.Column("camera_id", sa.String(length=64), server_default="cam-main", nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("aisle", sa.String(length=64), nullable=False),
        sa.Column("tier_count", sa.Integer(), server_default="3", nullable=False),
        sa.Column("polygon", json_type, nullable=False),
        sa.Column("interaction_polygon", json_type, nullable=True),
        sa.Column("configured_capacity", sa.Integer(), server_default="20", nullable=False),
        sa.Column("current_occupancy", sa.Integer(), server_default="0", nullable=False),
        sa.Column("fill_percentage", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="ok", nullable=False),
        sa.Column("empty_positions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("product_classes", json_type, server_default="[]", nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("store_id", "camera_id", "name", name="uq_shelf_zones_store_camera_name"),
    )
    op.create_index("ix_shelf_zones_store_id", "shelf_zones", ["store_id"])
    op.create_index("ix_shelf_zones_camera_id", "shelf_zones", ["camera_id"])
    op.create_index("ix_shelf_zones_store_camera", "shelf_zones", ["store_id", "camera_id"])

    # 3. Unified Retail Events Table
    op.create_table(
        "retail_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("store_id", sa.String(length=64), nullable=False),
        sa.Column("camera_id", sa.String(length=64), server_default="cam-main", nullable=False),
        sa.Column("visitor_id", sa.String(length=64), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("shelf_id", sa.String(length=64), nullable=True),
        sa.Column("zone_id", sa.String(length=64), nullable=True),
        sa.Column("product_id", sa.String(length=64), nullable=True),
        sa.Column("product_class", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("timestamp", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("confirmation_status", sa.String(length=32), server_default="confirmed", nullable=False),
        sa.Column("evidence", json_type, server_default="{}", nullable=False),
        sa.Column("related_event_id", sa.String(length=64), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_retail_events_idempotency_key"),
    )
    op.create_index("ix_retail_events_store_id", "retail_events", ["store_id"])
    op.create_index("ix_retail_events_camera_id", "retail_events", ["camera_id"])
    op.create_index("ix_retail_events_visitor_id", "retail_events", ["visitor_id"])
    op.create_index("ix_retail_events_session_id", "retail_events", ["session_id"])
    op.create_index("ix_retail_events_shelf_id", "retail_events", ["shelf_id"])
    op.create_index("ix_retail_events_event_type", "retail_events", ["event_type"])
    op.create_index("ix_retail_events_confirmation_status", "retail_events", ["confirmation_status"])
    op.create_index("ix_retail_events_store_timestamp", "retail_events", ["store_id", "timestamp"])
    op.create_index("ix_retail_events_visitor_session", "retail_events", ["visitor_id", "session_id"])
    op.create_index("ix_retail_events_shelf_type", "retail_events", ["shelf_id", "event_type"])


def downgrade() -> None:
    op.drop_table("retail_events")
    op.drop_table("shelf_zones")
    op.drop_table("daily_visitors")
