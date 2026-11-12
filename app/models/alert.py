import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.store import Store
    from app.models.video import VideoJob


class Alert(Base):
    """Operational and vision-derived alert incident record."""

    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info', 'warning', 'critical')",
            name="ck_alerts_severity",
        ),
    )

    # String primary key matching current contract (e.g. 'al-01')
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
    job_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("video_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    shelf_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    shelf_occupancy: Mapped[Optional[float]] = mapped_column(
        nullable=True,
    )
    detected_products: Mapped[Optional[int]] = mapped_column(
        nullable=True,
    )
    annotated_image_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    alert_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    area: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    acknowledged: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    time_str: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    acknowledged_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    store: Mapped[Optional["Store"]] = relationship(
        "Store",
        back_populates="alerts",
    )
    video_job: Mapped[Optional["VideoJob"]] = relationship(
        "VideoJob",
        back_populates="alerts",
    )
