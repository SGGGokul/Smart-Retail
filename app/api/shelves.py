from typing import Optional
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.schemas.image import ImageDetectionResponse
from app.schemas.shelves import ShelfItem, ShelfMetricsResponse, ShelvesResponse
from app.services.image_service import get_image_detection_service
from app.services.shelf_service import get_shelf_service

router = APIRouter()


@router.post(
    "/detect",
    response_model=ImageDetectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload shelf image for visual object detection",
)
async def detect_shelf_image(
    file: UploadFile = File(..., description="Shelf image file (.jpg, .jpeg, .png, .webp)"),
    confidence: float = Query(default=0.25, ge=0.05, le=0.95, description="Detection confidence threshold"),
) -> ImageDetectionResponse:
    """Processes uploaded retail shelf imagery through YOLO detection."""
    service = get_image_detection_service()
    return await service.detect_image(file, confidence_threshold=confidence)


@router.get(
    "/metrics",
    response_model=ShelfMetricsResponse,
    summary="Get aggregated shelf occupancy and stock metrics",
)
async def get_shelf_metrics(
    store_id: str = Query(default="store-104", description="Store ID"),
) -> ShelfMetricsResponse:
    """Retrieve store-level shelf occupancy percentage, empty positions, and pickup/return counts."""
    service = get_shelf_service()
    data = service.get_shelf_metrics(store_id=store_id)
    return ShelfMetricsResponse(**data)


@router.get(
    "",
    response_model=ShelvesResponse,
    summary="List monitored shelf zones",
)
async def list_shelves(
    status: Optional[str] = Query(default=None, description="all | low | critical | ok"),
    store_id: str = Query(default="store-104", description="Store ID"),
) -> ShelvesResponse:
    """Lists all monitored retail shelf zones, stock fill levels, and empty positions."""
    service = get_shelf_service()
    shelf_states = service.list_shelves(store_id=store_id, status_filter=status)

    items = [
        ShelfItem(
            id=s.bay.shelf_id,
            name=s.bay.name,
            aisle=s.bay.aisle,
            fillPct=s.fill_percentage,
            status=s.status,  # type: ignore[arg-type]
            lastChecked="Just now" if s.last_updated_timestamp > 0 else "Pending stream",
            capacity=s.bay.configured_capacity,
            occupancy=s.current_occupancy,
            emptyPositions=s.empty_positions,
            tierCount=s.bay.tier_count,
            productClasses=s.bay.product_classes,
        )
        for s in shelf_states
    ]

    critical_count = sum(1 for item in items if item.status == "critical")
    low_count = sum(1 for item in items if item.status == "low")

    return ShelvesResponse(
        shelves=items,
        totalCount=len(items),
        criticalCount=critical_count,
        lowStockCount=low_count,
    )


@router.get(
    "/{id}",
    response_model=ShelfItem,
    summary="Get individual shelf zone",
)
async def get_shelf(
    id: str,
    store_id: str = Query(default="store-104", description="Store ID"),
) -> ShelfItem:
    """Retrieves an individual shelf bay status."""
    service = get_shelf_service()
    state = service.get_shelf_state(store_id=store_id, shelf_id=id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shelf zone '{id}' not found.",
        )

    return ShelfItem(
        id=state.bay.shelf_id,
        name=state.bay.name,
        aisle=state.bay.aisle,
        fillPct=state.fill_percentage,
        status=state.status,  # type: ignore[arg-type]
        lastChecked="Just now" if state.last_updated_timestamp > 0 else "Pending stream",
        capacity=state.bay.configured_capacity,
        occupancy=state.current_occupancy,
        emptyPositions=state.empty_positions,
        tierCount=state.bay.tier_count,
        productClasses=state.bay.product_classes,
    )
