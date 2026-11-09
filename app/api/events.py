"""Unified Retail Event Bus & Timeline Endpoints."""

from typing import Optional
from fastapi import APIRouter, Query

from app.schemas.retail_intelligence import EventTimelineResponse, RetailEventSchema
from app.services.shelf_service import get_shelf_service

router = APIRouter()


@router.get(
    "/timeline",
    response_model=EventTimelineResponse,
    summary="Get unified retail event timeline",
)
async def get_event_timeline(
    store_id: Optional[str] = Query(default="store-104", description="Store ID filter"),
    camera_id: Optional[str] = Query(default=None, description="Camera ID filter"),
    shelf_id: Optional[str] = Query(default=None, description="Shelf ID filter"),
    visitor_id: Optional[str] = Query(default=None, description="Daily visitor ID filter"),
    event_type: Optional[str] = Query(default=None, description="Event type filter"),
    confirmation_status: Optional[str] = Query(default=None, description="candidate | confirmed | rejected | uncertain"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> EventTimelineResponse:
    """Retrieve chronological event timeline for customer entries, exits, shelf approaches, and pickups/returns."""
    shelf_service = get_shelf_service()
    events, total = shelf_service.get_timeline_events(
        store_id=store_id,
        camera_id=camera_id,
        shelf_id=shelf_id,
        visitor_id=visitor_id,
        event_type=event_type,
        confirmation_status=confirmation_status,
        limit=limit,
        offset=offset,
    )

    candidate_count = sum(1 for e in events if e.confirmation_status == "candidate")
    confirmed_count = sum(1 for e in events if e.confirmation_status == "confirmed")

    return EventTimelineResponse(
        events=[
            RetailEventSchema(
                id=e.event_id,
                storeId=e.store_id,
                cameraId=e.camera_id,
                eventType=e.event_type,
                timestamp=round(e.timestamp, 2),
                confidence=round(e.confidence, 2),
                confirmationStatus=e.confirmation_status,
                visitorId=e.visitor_id,
                sessionId=e.session_id,
                shelfId=e.shelf_id,
                zoneId=e.zone_id,
                productId=e.product_id,
                productClass=e.product_class,
                evidence=e.evidence,
                relatedEventId=e.related_event_id,
            )
            for e in events
        ],
        totalCount=total,
        candidateCount=candidate_count,
        confirmedCount=confirmed_count,
    )
