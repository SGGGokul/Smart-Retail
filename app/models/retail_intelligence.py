"""SQLAlchemy ORM Models for Unified Retail Intelligence, Daily Visitors, Shelf Monitoring & Events."""

import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base

JSONType = JSONB().with_variant(JSON(), "sqlite")


class DailyVisitorModel(Base):
    """Anonymous Daily Visitor identity scoped to store and local calendar date."""

    __tablename__ = "daily_visitors"
    __table_args__ = (
        UniqueConstraint("store_id", "local_date", "anonymous_label", name="uq_daily_visitors_store_date_label"),
        Index("ix_daily_visitors_store_date", "store_id", "local_date"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    local_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # YYYY-MM-DD in store local timezone
    anonymous_label: Mapped[str] = mapped_column(String(32), nullable=False)  # e.g. DVIS-0001
    first_seen_at: Mapped[float] = mapped_column(Float, nullable=False)
    last_seen_at: Mapped[float] = mapped_column(Float, nullable=False)
    total_visits: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    total_dwell_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cameras_seen: Mapped[List[str]] = mapped_column(JSONType, default=list, nullable=False)
    feature_embedding: Mapped[Optional[List[float]]] = mapped_column(JSONType, nullable=True)  # Anonymized normalized visual appearance vector
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


class ShelfZoneModel(Base):
    """Monitored retail shelf zone and physical bay definition."""

    __tablename__ = "shelf_zones"
    __table_args__ = (
        UniqueConstraint("store_id", "camera_id", "name", name="uq_shelf_zones_store_camera_name"),
        Index("ix_shelf_zones_store_camera", "store_id", "camera_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    camera_id: Mapped[str] = mapped_column(String(64), default="cam-main", nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    aisle: Mapped[str] = mapped_column(String(64), nullable=False)
    tier_count: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    polygon: Mapped[List[List[float]]] = mapped_column(JSONType, nullable=False)  # [[x1, y1], [x2, y2], ...]
    interaction_polygon: Mapped[Optional[List[List[float]]]] = mapped_column(JSONType, nullable=True)  # Approach/interaction boundary
    configured_capacity: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    current_occupancy: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fill_percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0 to 100
    status: Mapped[str] = mapped_column(String(32), default="ok", nullable=False)  # "ok", "low", "critical"
    empty_positions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    product_classes: Mapped[List[str]] = mapped_column(JSONType, default=list, nullable=False)  # e.g. ["bottle", "can"]
    last_checked_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
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


class RetailEventModel(Base):
    """Unified retail event bus recording customer journeys, shelf interactions, and pickups/returns."""

    __tablename__ = "retail_events"
    __table_args__ = (
        Index("ix_retail_events_store_timestamp", "store_id", "timestamp"),
        Index("ix_retail_events_visitor_session", "visitor_id", "session_id"),
        Index("ix_retail_events_shelf_type", "shelf_id", "event_type"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    store_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    camera_id: Mapped[str] = mapped_column(String(64), default="cam-main", nullable=False, index=True)
    visitor_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # Daily Visitor ID
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # Visit session ID
    shelf_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    zone_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    product_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    product_class: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # e.g. "bottle"
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Types: customer_entered_store, customer_exited_store, customer_approached_shelf,
    # customer_reached_shelf, product_pickup_candidate, product_picked_up,
    # product_return_candidate, product_returned, shelf_occupancy_changed, shelf_low_stock, shelf_out_of_stock
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    confirmation_status: Mapped[str] = mapped_column(
        String(32), default="confirmed", nullable=False, index=True
    )  # "candidate", "confirmed", "rejected", "uncertain"
    evidence: Mapped[Dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    related_event_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
