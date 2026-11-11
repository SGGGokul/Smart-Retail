import uuid
from typing import TYPE_CHECKING, List
from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.analytics import AnalyticsRecord
    from app.models.camera import Camera
    from app.models.video import VideoJob


class Store(Base):
    """Store entity supporting multi-store retail environments."""

    __tablename__ = "stores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    store_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    location: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )
    timezone: Mapped[str] = mapped_column(
        String(50),
        default="UTC",
        nullable=False,
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    cameras: Mapped[List["Camera"]] = relationship(
        "Camera",
        back_populates="store",
        cascade="all, delete-orphan",
    )
    video_jobs: Mapped[List["VideoJob"]] = relationship(
        "VideoJob",
        back_populates="store",
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert",
        back_populates="store",
    )
    analytics_records: Mapped[List["AnalyticsRecord"]] = relationship(
        "AnalyticsRecord",
        back_populates="store",
        cascade="all, delete-orphan",
    )
