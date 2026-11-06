from typing import List, Literal
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


class ShelvesResponse(BaseModel):
    """Monitored shelves list response."""
    shelves: List[ShelfItem] = Field(default_factory=list)
    totalCount: int = 0
    criticalCount: int = 0
    lowStockCount: int = 0
