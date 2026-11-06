from typing import Optional
from fastapi import APIRouter, Query

from app.schemas.analytics import (
    AnalyticsDwellResponse,
    AnalyticsQueuesResponse,
    AnalyticsSummaryResponse,
    AnalyticsTrafficResponse,
)
from app.services.analytics_service import get_analytics_service

router = APIRouter()


@router.get(
    "/summary",
    response_model=AnalyticsSummaryResponse,
    summary="Get store summary metrics",
)
async def get_analytics_summary() -> AnalyticsSummaryResponse:
    """Returns aggregate KPI metrics for the store overview dashboard."""
    analytics_service = get_analytics_service()
    return analytics_service.get_summary()


@router.get(
    "/traffic",
    response_model=AnalyticsTrafficResponse,
    summary="Get customer traffic distribution",
)
async def get_analytics_traffic(
    range: Optional[str] = Query(default="7d", description="Timeframe: today | 7d | 30d")
) -> AnalyticsTrafficResponse:
    """Retrieves daily and hourly customer traffic counts."""
    analytics_service = get_analytics_service()
    return analytics_service.get_traffic(range_param=range)


@router.get(
    "/dwell-time",
    response_model=AnalyticsDwellResponse,
    summary="Get customer dwell time metrics",
)
async def get_analytics_dwell_time() -> AnalyticsDwellResponse:
    """Retrieves customer dwell time per store department/section."""
    analytics_service = get_analytics_service()
    return analytics_service.get_dwell_time()


@router.get(
    "/queues",
    response_model=AnalyticsQueuesResponse,
    summary="Get checkout queue metrics",
)
async def get_analytics_queues() -> AnalyticsQueuesResponse:
    """Retrieves active checkout queue telemetry."""
    analytics_service = get_analytics_service()
    return analytics_service.get_queues()
