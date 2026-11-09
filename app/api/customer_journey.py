"""Customer Journey, Anonymous Visits, and Unified Intelligence REST Endpoints."""

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
from app.schemas.retail_intelligence import (
    DailyVisitorListResponse,
    DailyVisitorSchema,
    VisitorMetricsResponse,
)
from app.services.identity_service import get_identity_service
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
    "/metrics",
    response_model=VisitorMetricsResponse,
    summary="Get real-time customer and visitor intelligence metrics",
)
async def get_visitor_metrics(
    store_id: str = Query(default="store-104", description="Store ID"),
    date: Optional[str] = Query(default=None, description="Local calendar date (YYYY-MM-DD)"),
) -> VisitorMetricsResponse:
    """Retrieve distinct counts for person detections, active tracks, daily unique visitors, and visit sessions."""
    identity_svc = get_identity_service()
    visit_svc = get_visit_service()

    target_date = date or identity_svc.get_store_local_date(store_id=store_id)
    daily_visitors = identity_svc.list_daily_visitors(store_id=store_id, local_date=target_date)

    all_visits = [v for v in visit_svc.get_all_visits() if getattr(v, "store_id", store_id) == store_id]
    active_visits = [v for v in all_visits if v.status.value == "active" or str(v.status) == "active"]

    # Calculate camera traffic
    camera_traffic: Dict[str, int] = {}
    for v in all_visits:
        for cam in v.cameras_seen:
            camera_traffic[cam] = camera_traffic.get(cam, 0) + 1

    unique_daily = len(daily_visitors) if daily_visitors else len(set(v.customer_id for v in all_visits))
    returning = sum(1 for dv in daily_visitors if dv.total_visits > 1) if daily_visitors else sum(1 for v in all_visits if v.is_repeat_visit)

    # Estimate person detections from dwell / events
    person_dets = sum(len(v.journey_events) for v in all_visits)

    return VisitorMetricsResponse(
        personDetections=max(person_dets, len(all_visits) * 8),
        activeTracks=len(active_visits),
        uniqueDailyVisitors=unique_daily,
        visitSessions=len(all_visits),
        returningVisitors=returning,
        cameraTraffic=camera_traffic,
    )


@router.get(
    "/daily-visitors",
    response_model=DailyVisitorListResponse,
    summary="List anonymous daily visitors for a store-day",
)
async def list_daily_visitors(
    store_id: str = Query(default="store-104", description="Store ID"),
    date: Optional[str] = Query(default=None, description="Local calendar date (YYYY-MM-DD)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> DailyVisitorListResponse:
    """List store-day visitors with anonymous labels (e.g. VIS-0001), visit counts, and dwell times."""
    identity_svc = get_identity_service()
    target_date = date or identity_svc.get_store_local_date(store_id=store_id)
    visitors = identity_svc.list_daily_visitors(store_id=store_id, local_date=target_date)

    paginated = visitors[offset : offset + limit]
    returning_count = sum(1 for v in visitors if v.total_visits > 1)

    return DailyVisitorListResponse(
        visitors=[
            DailyVisitorSchema(
                id=v.visitor_id,
                storeId=v.store_id,
                localDate=v.local_date,
                anonymousLabel=v.anonymous_label,
                firstSeenAt=round(v.first_seen_at, 2),
                lastSeenAt=round(v.last_seen_at, 2),
                totalVisits=v.total_visits,
                totalDwellSeconds=round(v.total_dwell_seconds, 2),
                camerasSeen=list(v.cameras_seen),
            )
            for v in paginated
        ],
        totalCount=len(visitors),
        uniqueDailyVisitors=len(visitors),
        returningVisitors=returning_count,
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
