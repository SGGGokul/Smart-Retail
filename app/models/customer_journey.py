"""SQLAlchemy ORM Models for Anonymous Customer Visits and Journey Events."""

import datetime
from typing import Dict, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base

JSONType = JSONB().with_variant(JSON(), "sqlite")


class CustomerVisitModel(Base):
    """Persisted customer visit session record."""

    __tablename__ = "customer_visits"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    video_job_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("video_jobs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    store_id: Mapped[str] = mapped_column(String(64), default="store-104", nullable=False)
    camera_id: Mapped[str] = mapped_column(String(64), default="cam-main", nullable=False)
    entry_time: Mapped[float] = mapped_column(Float, nullable=False)
    exit_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)
    zones_visited: Mapped[List[str]] = mapped_column(JSONType, default=list, nullable=False)
    zone_dwell_times: Mapped[Dict[str, float]] = mapped_column(JSONType, default=dict, nullable=False)
    is_repeat_visit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    visit_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    events: Mapped[List["CustomerZoneEventModel"]] = relationship(
        "CustomerZoneEventModel",
        back_populates="visit",
        cascade="all, delete-orphan",
        order_by="CustomerZoneEventModel.timestamp",
    )


class CustomerZoneEventModel(Base):
    """Detailed zone transition and boundary crossing event for customer journeys."""

    __tablename__ = "customer_zone_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    visit_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("customer_visits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    camera_id: Mapped[str] = mapped_column(String(64), default="cam-main", nullable=False)
    zone_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    zone_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    dwell_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    visit: Mapped["CustomerVisitModel"] = relationship(
        "CustomerVisitModel",
        back_populates="events",
    )
