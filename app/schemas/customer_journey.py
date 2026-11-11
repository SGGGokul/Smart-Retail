"""Pydantic Request and Response Schemas for Customer Journey Tracking APIs."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CustomerZoneEventSchema(BaseModel):
    """A single zone entry, exit, or boundary event."""
    id: str
    visitId: str
    customerId: str
    cameraId: str = "cam-main"
    zoneId: Optional[str] = None
    zoneName: Optional[str] = None
    eventType: str
    timestamp: float
    dwellSeconds: float = 0.0


class CustomerVisitSchema(BaseModel):
    """Anonymous customer visit summary."""
    id: str
    customerId: str
    videoJobId: Optional[str] = None
    storeId: str = "store-104"
    cameraId: str = "cam-main"
    entryTime: float
    exitTime: Optional[float] = None
    durationSeconds: float = 0.0
    status: str = "active"
    zonesVisited: List[str] = Field(default_factory=list)
    zoneDwellTimes: Dict[str, float] = Field(default_factory=dict)
    isRepeatVisit: bool = False
    visitNumber: int = 1


class CustomerVisitDetailResponse(BaseModel):
    """Full journey details for an individual visit."""
    visit: CustomerVisitSchema
    events: List[CustomerZoneEventSchema] = Field(default_factory=list)


class CustomerVisitListResponse(BaseModel):
    """Paginated list of customer visits."""
    visits: List[CustomerVisitSchema] = Field(default_factory=list)
    totalCount: int = 0
    activeCount: int = 0
    completedCount: int = 0


class ZoneDwellMetric(BaseModel):
    """Dwell metric for a specific store zone."""
    zoneName: str
    totalVisits: int = 0
    avgDwellSeconds: float = 0.0
    totalDwellSeconds: float = 0.0


class JourneyAnalyticsResponse(BaseModel):
    """Store-level customer journey analytics."""
    totalVisits: int = 0
    uniqueCustomers: int = 0
    avgDwellSeconds: float = 0.0
    zoneDwellSummary: List[ZoneDwellMetric] = Field(default_factory=list)
    popularTransitions: List[Dict[str, Any]] = Field(default_factory=list)
