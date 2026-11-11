from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

ShelfStatus = Literal["ok", "low", "critical"]


class ShelfItem(BaseModel):
    """Monitored retail shelf zone record."""
    id: str
    name: str
    aisle: str
    fillPct: int
    status: ShelfStatus
    lastChecked: str
    capacity: int = 20
    occupancy: int = 0
    emptyPositions: int = 0
    tierCount: int = 3
    productClasses: List[str] = Field(default_factory=list)


class ShelvesResponse(BaseModel):
    """Monitored shelves list response."""
    shelves: List[ShelfItem] = Field(default_factory=list)
    totalCount: int = 0
    criticalCount: int = 0
    lowStockCount: int = 0


class ShelfMetricsResponse(BaseModel):
    """Aggregated retail shelf and stock interaction metrics."""
    shelfOccupancyPercentage: int = 0
    emptyPositions: int = 0
    lowStockCount: int = 0
    outOfStockCount: int = 0
    pickupCandidates: int = 0
    confirmedPickups: int = 0
    returnCandidates: int = 0
    confirmedReturns: int = 0
    customerShelfInteractions: int = 0
