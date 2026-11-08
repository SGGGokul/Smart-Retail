"""Customer Journey and Anonymous Visit REST Endpoints."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.customer_journey import CustomerVisitModel, CustomerZoneEventModel
from app.schemas.customer_journey import (
    CustomerVisitDetailResponse,
    CustomerVisitListResponse,
    CustomerVisitSchema,
    CustomerZoneEventSchema,
    JourneyAnalyticsResponse,
    ZoneDwellMetric,
)
from app.services.visit_service import get_visit_service

router = APIRouter()


def _model_to_visit_schema(v: CustomerVisitModel) -> CustomerVisitSchema:
    return CustomerVisitSchema(
        id=v.id,
        customerId=v.customer_id,
        videoJobId=v.video_job_id,
        storeId=v.store_id,
        cameraId=v.camera_id,
        entryTime=round(v.entry_time, 2),
        exitTime=round(v.exit_time, 2) if v.exit_time is not None else None,
        durationSeconds=round(v.duration_seconds, 2),
        status=v.status,
        zonesVisited=v.zones_visited or [],
        zoneDwellTimes=v.zone_dwell_times or {},
        isRepeatVisit=v.is_repeat_visit,
        visitNumber=v.visit_number,
    )


def _model_to_event_schema(ev: CustomerZoneEventModel) -> CustomerZoneEventSchema:
    return CustomerZoneEventSchema(
        id=ev.id,
        visitId=ev.visit_id,
        customerId=ev.customer_id,
        cameraId=ev.camera_id,
        zoneId=ev.zone_id,
        zoneName=ev.zone_name,
        eventType=ev.event_type,
        timestamp=round(ev.timestamp, 2),
        dwellSeconds=round(ev.dwell_seconds, 2),
    )


@router.get(
    "/visits",
    response_model=CustomerVisitListResponse,
    summary="List customer visits",
)
async def list_visits(
    status: Optional[str] = Query(default=None, description="Filter by status: active | completed | incomplete | timed_out"),
    camera_id: Optional[str] = Query(default=None, description="Filter by camera ID"),
    customer_id: Optional[str] = Query(default=None, description="Filter by customer ID (e.g. CUST-000001)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> CustomerVisitListResponse:
    """Retrieve paginated customer visits with optional filters for camera, customer, or status."""
    visit_service = get_visit_service()
    visits, total, active, completed = await visit_service.list_visits_from_db(
        session=db,
        camera_id=camera_id,
        customer_id=customer_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return CustomerVisitListResponse(
        visits=[_model_to_visit_schema(v) for v in visits],
        totalCount=total,
        activeCount=active,
        completedCount=completed,
    )


@router.get(
    "/visits/{visit_id}",
    response_model=CustomerVisitDetailResponse,
    summary="Get customer visit details with event timeline",
)
async def get_visit_detail(
    visit_id: str,
    db: AsyncSession = Depends(get_db),
) -> CustomerVisitDetailResponse:
    """Retrieve an individual visit's details and full chronological event journey."""
    visit_service = get_visit_service()
    res = await visit_service.get_visit_detail_from_db(db, visit_id)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer visit '{visit_id}' not found.",
        )
    visit, events = res
    return CustomerVisitDetailResponse(
        visit=_model_to_visit_schema(visit),
        events=[_model_to_event_schema(ev) for ev in events],
    )


@router.get(
    "/customers/{customer_id}/history",
    response_model=List[CustomerVisitSchema],
    summary="Get visit history for an anonymous customer",
)
async def get_customer_history(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[CustomerVisitSchema]:
    """Retrieve all historical visits for a persistent pseudonymous customer ID."""
    visit_service = get_visit_service()
    visits = await visit_service.get_customer_history_from_db(db, customer_id)
    return [_model_to_visit_schema(v) for v in visits]


@router.get(
    "/zones/analytics",
    response_model=JourneyAnalyticsResponse,
    summary="Get store-level zone analytics and customer journeys",
)
async def get_zone_analytics(
    db: AsyncSession = Depends(get_db),
) -> JourneyAnalyticsResponse:
    """Aggregated dwell metrics per zone and common customer transition patterns."""
    visit_service = get_visit_service()
    data = await visit_service.get_journey_analytics_from_db(db)
    dwell_summaries = [
        ZoneDwellMetric(
            zoneName=item["zoneName"],
            totalVisits=item["totalVisits"],
            avgDwellSeconds=item["avgDwellSeconds"],
            totalDwellSeconds=item["totalDwellSeconds"],
        )
        for item in data.get("zoneDwellSummary", [])
    ]
    return JourneyAnalyticsResponse(
        totalVisits=data.get("totalVisits", 0),
        uniqueCustomers=data.get("uniqueCustomers", 0),
        avgDwellSeconds=data.get("avgDwellSeconds", 0.0),
        zoneDwellSummary=dwell_summaries,
        popularTransitions=data.get("popularTransitions", []),
    )


@router.get(
    "/cameras/{camera_id}/analytics",
    summary="Get camera-specific customer analytics",
)
async def get_camera_analytics(
    camera_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve customer visit metrics recorded by a specific camera stream."""
    visit_service = get_visit_service()
    return await visit_service.get_camera_analytics_from_db(db, camera_id)
