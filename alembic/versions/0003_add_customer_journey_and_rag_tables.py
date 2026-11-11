"""Add customer_visits, customer_zone_events, rag_documents, and rag_document_chunks tables.

Revision ID: 0003_add_customer_journey_and_rag_tables
Revises: 0002_add_alert_idempotency_key
Create Date: 2026-11-07 17:20:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_customer_journey_rag"
down_revision: Union[str, None] = "0002_add_alert_idempotency_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn and conn.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    try:
        from pgvector.sqlalchemy import Vector
        embedding_type = Vector(384).with_variant(sa.JSON(), "sqlite")
    except ImportError:
        embedding_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")

    # 1. Customer Visits Table
    op.create_table(
        "customer_visits",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("video_job_id", sa.String(length=64), nullable=True),
        sa.Column("store_id", sa.String(length=64), server_default="store-104", nullable=False),
        sa.Column("camera_id", sa.String(length=64), server_default="cam-main", nullable=False),
        sa.Column("entry_time", sa.Float(), nullable=False),
        sa.Column("exit_time", sa.Float(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("zones_visited", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("zone_dwell_times", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("is_repeat_visit", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("visit_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["video_job_id"], ["video_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_visits_customer_id", "customer_visits", ["customer_id"])
    op.create_index("ix_customer_visits_video_job_id", "customer_visits", ["video_job_id"])
    op.create_index("ix_customer_visits_status", "customer_visits", ["status"])

    # 2. Customer Zone Events Table
    op.create_table(
        "customer_zone_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("visit_id", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("camera_id", sa.String(length=64), server_default="cam-main", nullable=False),
        sa.Column("zone_id", sa.String(length=64), nullable=True),
        sa.Column("zone_name", sa.String(length=128), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("timestamp", sa.Float(), nullable=False),
        sa.Column("dwell_seconds", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["visit_id"], ["customer_visits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_zone_events_visit_id", "customer_zone_events", ["visit_id"])
    op.create_index("ix_customer_zone_events_customer_id", "customer_zone_events", ["customer_id"])
    op.create_index("ix_customer_zone_events_event_type", "customer_zone_events", ["event_type"])

    # 3. RAG Documents Table
    op.create_table(
        "rag_documents",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=16), nullable=False),
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rag_documents_filename", "rag_documents", ["filename"], unique=True)

    # 4. RAG Document Chunks Table
    op.create_table(
        "rag_document_chunks",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("document_name", sa.String(length=255), nullable=False),
        sa.Column("page_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("chunk_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", embedding_type, nullable=False),
        sa.Column("embedding_model", sa.String(length=128), server_default="BAAI/bge-small-en-v1.5", nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), server_default="384", nullable=False),
        sa.Column("citation", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["rag_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rag_document_chunks_document_id", "rag_document_chunks", ["document_id"])
    op.create_index("ix_rag_document_chunks_document_name", "rag_document_chunks", ["document_name"])



def downgrade() -> None:
    op.drop_table("rag_document_chunks")
    op.drop_table("rag_documents")
    op.drop_table("customer_zone_events")
    op.drop_table("customer_visits")
