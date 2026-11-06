from typing import List
from pydantic import BaseModel, Field


class AnalyticsSummaryResponse(BaseModel):
    """Aggregate KPI metrics for the store overview dashboard."""
    todayCustomers: int = 0
    todayCustomersDelta: str = ""
    avgDwellMinutes: float = 0.0
    avgDwellDelta: str = ""
    longestQueueCheckout: str = "N/A"
    longestQueueCount: int = 0
    shelvesNeedingRestock: int = 0
    criticalShelvesCount: int = 0
    lowStockShelvesCount: int = 0


class TrafficPoint(BaseModel):
    """Daily customer count."""
    day: str
    customers: int


class HourlyPoint(BaseModel):
    """Hourly customer count."""
    hour: str
    customers: int


class AnalyticsTrafficResponse(BaseModel):
    """Customer traffic response for daily and hourly aggregations."""
    daily: List[TrafficPoint] = Field(default_factory=list)
    hourly: List[HourlyPoint] = Field(default_factory=list)
    totalCustomers: int = 0


class DwellPoint(BaseModel):
    """Dwell time per store section."""
    section: str
    minutes: float


class AnalyticsDwellResponse(BaseModel):
    """Customer dwell time response."""
    bySection: List[DwellPoint] = Field(default_factory=list)
    averageDwellMinutes: float = 0.0


class QueuePoint(BaseModel):
    """Queue telemetry per checkout lane."""
    checkoutId: str
    currentQueue: int
    avgWaitMinutes: float
    peakQueue: int


class AnalyticsQueuesResponse(BaseModel):
    """Active checkout queue status response."""
    queues: List[QueuePoint] = Field(default_factory=list)
    updatedAt: str
