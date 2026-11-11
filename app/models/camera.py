import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.store import Store
    from app.models.video import VideoJob

# Fallback JSON type for cross-dialect compatibility (JSONB on PostgreSQL, JSON on SQLite)
JSONType = JSONB().with_variant(JSON(), "sqlite")


class Camera(Base):
    """CCTV camera feed configuration, ingress lines, and placement zones."""

    __tablename__ = "cameras"
    __table_args__ = (
        UniqueConstraint("store_id", "camera_code", name="uq_cameras_store_code"),
        CheckConstraint("zone_type IN ('entrance', 'aisle', 'checkout')", name="ck_cameras_zone_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    camera_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    zone_type: Mapped[str] = mapped_column(
        String(50),
        default="entrance",
        nullable=False,
    )
    stream_url: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )
    resolution: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    fps: Mapped[Optional[float]] = mapped_column(
        Float,
        default=15.0,
        nullable=True,
    )
    zone_coords: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONType,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    store: Mapped["Store"] = relationship(
        "Store",
        back_populates="cameras",
    )
    video_jobs: Mapped[List["VideoJob"]] = relationship(
        "VideoJob",
        back_populates="camera",
    )
