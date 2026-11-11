from typing import List, Literal, Optional
from pydantic import BaseModel, Field

Severity = Literal["info", "warning", "critical"]


class AlertItem(BaseModel):
    """Store system or vision alert."""
    id: str
    type: str
    time: str
    area: str
    severity: Severity
    description: str
    acknowledged: bool = False


class AlertsResponse(BaseModel):
    """List of alerts with counts."""
    alerts: List[AlertItem] = Field(default_factory=list)
    totalCount: int = 0
    unacknowledgedCount: int = 0


class AlertUpdateRequest(BaseModel):
    """Payload to acknowledge or annotate an alert."""
    acknowledged: bool
    notes: Optional[str] = None
