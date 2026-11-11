from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response conforming strictly to API_CONTRACT.md section 1."""

    status: str = Field(default="ok", description="Service liveness state", examples=["ok"])
    version: str = Field(default="1.0.0", description="API version", examples=["1.0.0"])
    uptimeSeconds: int = Field(..., description="Seconds since service start", examples=[14250])
    timestamp: str = Field(
        ...,
        description="Current UTC ISO-8601 timestamp with Z suffix",
        examples=["2026-10-18T10:30:00Z"],
    )
