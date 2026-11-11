import datetime
import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.store import Store


class AnalyticsRecord(Base):
    """Historical and aggregated store traffic, dwell, and footfall rollups."""

    __tablename__ = "analytics_records"
    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "record_date",
            "record_hour",
            name="uq_analytics_store_date_hour",
        ),
        CheckConstraint(
            "record_hour IS NULL OR (record_hour >= 0 AND record_hour <= 23)",
            name="ck_analytics_record_hour",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    store_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    record_date: Mapped[datetime.date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    record_hour: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    total_customers: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    avg_dwell_minutes: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    peak_occupancy: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    video_clips_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship
    store: Mapped[Optional["Store"]] = relationship(
        "Store",
        back_populates="analytics_records",
    )
