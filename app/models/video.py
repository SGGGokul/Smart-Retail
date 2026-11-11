import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.camera import Camera
    from app.models.store import Store

JSONType = JSONB().with_variant(JSON(), "sqlite")


class VideoJob(Base):
    """Video ingestion record and processing lifecycle status."""

    __tablename__ = "video_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'processing', 'done', 'failed')",
            name="ck_video_jobs_status",
        ),
    )

    # String primary key to match existing API contract (e.g. 'vj-101-1614')
    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    store_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    camera_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cameras.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    storage_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    file_size_bytes: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="queued",
        nullable=False,
        index=True,
    )
    frames: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    customers_detected: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    fps: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    uploaded_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    processed_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    store: Mapped[Optional["Store"]] = relationship(
        "Store",
        back_populates="video_jobs",
    )
    camera: Mapped[Optional["Camera"]] = relationship(
        "Camera",
        back_populates="video_jobs",
    )
    inference_result: Mapped[Optional["InferenceResult"]] = relationship(
        "InferenceResult",
        back_populates="video_job",
        uselist=False,
        cascade="all, delete-orphan",
    )
    tracking_summaries: Mapped[List["TrackingSummary"]] = relationship(
        "TrackingSummary",
        back_populates="video_job",
        cascade="all, delete-orphan",
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert",
        back_populates="video_job",
    )


class InferenceResult(Base):
    """Detailed Computer Vision analytics and detections for a completed video job."""

    __tablename__ = "inference_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    job_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("video_jobs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    total_frames: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    customers_detected: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    peak_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    average_dwell_seconds: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    sample_detections: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONType,
        default=list,
        nullable=False,
    )
    raw_metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONType,
        nullable=True,
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship
    video_job: Mapped["VideoJob"] = relationship(
        "VideoJob",
        back_populates="inference_result",
    )


class TrackingSummary(Base):
    """ByteTrack trajectory and dwell consistency records per customer."""

    __tablename__ = "tracking_summaries"
    __table_args__ = (
        UniqueConstraint("job_id", "track_id", name="uq_tracking_job_track"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    job_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("video_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    track_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    first_frame: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    last_frame: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    dwell_seconds: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    hit_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    hit_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    crossed_entrance: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    crossed_exit: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationship
    video_job: Mapped["VideoJob"] = relationship(
        "VideoJob",
        back_populates="tracking_summaries",
    )
