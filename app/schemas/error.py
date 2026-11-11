from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Standardized inner error structure conforming to API_CONTRACT.md."""

    code: str = Field(..., description="Machine-readable error code", examples=["RESOURCE_NOT_FOUND"])
    message: str = Field(..., description="Human-readable error description")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Contextual error payload")


class ErrorEnvelope(BaseModel):
    """Top-level error response envelope required by API_CONTRACT.md."""

    error: ErrorDetail
