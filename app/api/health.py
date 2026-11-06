from datetime import datetime, timezone
from fastapi import APIRouter, status
from app.core.config import get_settings
from app.core.state import get_uptime_seconds
from app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Service Liveness and Health Check",
    description="Verifies backend service liveness and returns uptime and timestamp per API_CONTRACT.md Section 1.",
)
def get_health() -> HealthResponse:
    """Return backend liveness status strictly conforming to API_CONTRACT.md."""
    settings = get_settings()
    now_utc = datetime.now(timezone.utc)

    return HealthResponse(
        status="ok",
        version=settings.VERSION,
        uptimeSeconds=get_uptime_seconds(),
        timestamp=now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
