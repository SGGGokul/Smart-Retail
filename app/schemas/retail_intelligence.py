"""Pydantic schemas for Unified Retail Intelligence, Daily Visitors, and Event Timelines."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DailyVisitorSchema(BaseModel):
    """Anonymous daily visitor identity record."""
    id: str
    storeId: str
    localDate: str
    anonymousLabel: str
    firstSeenAt: float
    lastSeenAt: float
    totalVisits: int = 1
    totalDwellSeconds: float = 0.0
    camerasSeen: List[str] = Field(default_factory=list)


class DailyVisitorListResponse(BaseModel):
    """Paginated list of store-day visitors."""
    visitors: List[DailyVisitorSchema] = Field(default_factory=list)
    totalCount: int = 0
    uniqueDailyVisitors: int = 0
    returningVisitors: int = 0


class VisitorMetricsResponse(BaseModel):
    """Real-time visitor counts and tracking metrics."""
    personDetections: int = 0
    activeTracks: int = 0
    uniqueDailyVisitors: int = 0
    visitSessions: int = 0
    returningVisitors: int = 0
    cameraTraffic: Dict[str, int] = Field(default_factory=dict)


class RetailEventSchema(BaseModel):
    """Unified retail event bus record."""
    id: str
    storeId: str
    cameraId: str
    eventType: str
    timestamp: float
    confidence: float = 1.0
    confirmationStatus: str = "confirmed"  # candidate, confirmed, rejected, uncertain
    visitorId: Optional[str] = None
    sessionId: Optional[str] = None
    shelfId: Optional[str] = None
    zoneId: Optional[str] = None
    productId: Optional[str] = None
    productClass: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)
    relatedEventId: Optional[str] = None


class EventTimelineResponse(BaseModel):
    """Unified chronological event timeline."""
    events: List[RetailEventSchema] = Field(default_factory=list)
    totalCount: int = 0
    candidateCount: int = 0
    confirmedCount: int = 0
