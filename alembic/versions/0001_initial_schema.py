"""Initial PostgreSQL schema for RetailIQ.

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-11-06 12:55:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Dialect-agnostic JSON type (JSONB on PostgreSQL, JSON on SQLite)
json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")
uuid_type = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    # 1. stores table
    op.create_table(
        "stores",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("store_number", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("timezone", sa.String(50), server_default="UTC", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_stores_store_number", "stores", ["store_number"], unique=True)

    # 2. cameras table
    op.create_table(
        "cameras",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("store_id", uuid_type, sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("camera_code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("zone_type", sa.String(50), server_default="entrance", nullable=False),
        sa.Column("stream_url", sa.String(512), nullable=True),
        sa.Column("resolution", sa.String(20), nullable=True),
        sa.Column("fps", sa.Float(), server_default="15.0", nullable=True),
        sa.Column("zone_coords", json_type, nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("store_id", "camera_code", name="uq_cameras_store_code"),
        sa.CheckConstraint("zone_type IN ('entrance', 'aisle', 'checkout')", name="ck_cameras_zone_type"),
    )
    op.create_index("ix_cameras_store_id", "cameras", ["store_id"])

    # 3. video_jobs table
    op.create_table(
        "video_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("store_id", uuid_type, sa.ForeignKey("stores.id", ondelete="SET NULL"), nullable=True),
        sa.Column("camera_id", uuid_type, sa.ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(512), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(20), server_default="queued", nullable=False),
        sa.Column("frames", sa.Integer(), server_default="0", nullable=False),
        sa.Column("customers_detected", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("fps", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('queued', 'processing', 'done', 'failed')", name="ck_video_jobs_status"),
    )
    op.create_index("ix_video_jobs_status", "video_jobs", ["status"])
    op.create_index("ix_video_jobs_uploaded_at", "video_jobs", ["uploaded_at"])
    op.create_index("ix_video_jobs_store_id", "video_jobs", ["store_id"])
    op.create_index("ix_video_jobs_camera_id", "video_jobs", ["camera_id"])

    # 4. inference_results table
    op.create_table(
        "inference_results",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("job_id", sa.String(64), sa.ForeignKey("video_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("total_frames", sa.Integer(), nullable=False),
        sa.Column("customers_detected", sa.Integer(), nullable=False),
        sa.Column("peak_count", sa.Integer(), nullable=False),
        sa.Column("average_dwell_seconds", sa.Float(), nullable=False),
        sa.Column("sample_detections", json_type, nullable=False),
        sa.Column("raw_metrics", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("job_id", name="uq_inference_results_job_id"),
    )
    op.create_index("ix_inference_results_job_id", "inference_results", ["job_id"])

    # 5. tracking_summaries table
    op.create_table(
        "tracking_summaries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(64), sa.ForeignKey("video_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("first_frame", sa.Integer(), nullable=False),
        sa.Column("last_frame", sa.Integer(), nullable=False),
        sa.Column("dwell_seconds", sa.Float(), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False),
        sa.Column("hit_rate", sa.Float(), nullable=False),
        sa.Column("crossed_entrance", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("crossed_exit", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("job_id", "track_id", name="uq_tracking_job_track"),
    )
    op.create_index("ix_tracking_summaries_job_id", "tracking_summaries", ["job_id"])

    # 6. alerts table
    op.create_table(
        "alerts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("store_id", uuid_type, sa.ForeignKey("stores.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_id", sa.String(64), sa.ForeignKey("video_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("alert_type", sa.String(100), nullable=False),
        sa.Column("area", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("acknowledged", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("time_str", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("severity IN ('info', 'warning', 'critical')", name="ck_alerts_severity"),
    )
    op.create_index("ix_alerts_severity", "alerts", ["severity"])
    op.create_index("ix_alerts_acknowledged", "alerts", ["acknowledged"])
    op.create_index("ix_alerts_created_at", "alerts", ["created_at"])
    op.create_index("ix_alerts_store_id", "alerts", ["store_id"])

    # 7. analytics_records table
    op.create_table(
        "analytics_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("store_id", uuid_type, sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=True),
        sa.Column("record_date", sa.Date(), nullable=False),
        sa.Column("record_hour", sa.Integer(), nullable=True),
        sa.Column("total_customers", sa.Integer(), server_default="0", nullable=False),
        sa.Column("avg_dwell_minutes", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("peak_occupancy", sa.Integer(), server_default="0", nullable=False),
        sa.Column("video_clips_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("store_id", "record_date", "record_hour", name="uq_analytics_store_date_hour"),
        sa.CheckConstraint("record_hour IS NULL OR (record_hour >= 0 AND record_hour <= 23)", name="ck_analytics_record_hour"),
    )
    op.create_index("ix_analytics_records_date", "analytics_records", ["record_date"])
    op.create_index("ix_analytics_records_hour", "analytics_records", ["record_hour"])
    op.create_index("ix_analytics_records_store_id", "analytics_records", ["store_id"])


def downgrade() -> None:
    op.drop_table("analytics_records")
    op.drop_table("alerts")
    op.drop_table("tracking_summaries")
    op.drop_table("inference_results")
    op.drop_table("video_jobs")
    op.drop_table("cameras")
    op.drop_table("stores")
