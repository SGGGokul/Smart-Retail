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
    lastCheckedAt: Optional[str] = None
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


class ShelfEmptySpace(BaseModel):
    """Empty gap / space detected along shelf tier."""
    x1: float
    y1: float
    x2: float
    y2: float
    width: float
    height: float
    sectionIndex: int
    gapType: str = "out_of_stock_gap"


class ShelfDetectedProduct(BaseModel):
    """Product item localized inside a shelf section."""
    id: str
    className: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    width: float
    height: float
    sectionIndex: int
    source: str = "hybrid_retail_detector"


class ShelfSectionDetail(BaseModel):
    """Telemetry and occupancy analysis for an individual shelf section."""
    sectionIndex: int
    name: str
    x1: float
    y1: float
    x2: float
    y2: float
    occupancyPercentage: float
    status: str
    productsCount: int
    emptySpacesCount: int
    products: List[ShelfDetectedProduct] = Field(default_factory=list)
    emptySpaces: List[ShelfEmptySpace] = Field(default_factory=list)


class ShelfAnalysisResponse(BaseModel):
    """Complete response payload for empty shelf detection and out-of-stock analysis."""
    shelfId: str
    location: str
    width: int
    height: int
    overallOccupancyPercentage: float
    totalProductsCount: int
    totalEmptySpacesCount: int
    shelfStatus: str  # "empty", "critical", "low", "ok", "poor_lighting"
    isDetectionReliable: bool = True
    reliabilityNote: Optional[str] = None
    sections: List[ShelfSectionDetail] = Field(default_factory=list)
    totalDetections: int = 0
    detectionCounts: Dict[str, int] = Field(default_factory=dict)
    annotatedImage: Optional[str] = None
    modelUsed: str = "retailiq_hybrid_shelf_v1"
    alertGenerated: bool = False
    generatedAlertId: Optional[str] = None
    generatedAlertSeverity: Optional[str] = None
    alertDescription: Optional[str] = None
    replenishmentResolved: bool = False
