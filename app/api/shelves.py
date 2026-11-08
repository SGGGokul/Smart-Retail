from typing import Optional
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from app.schemas.image import ImageDetectionResponse
from app.schemas.shelves import ShelfItem, ShelvesResponse
from app.services.image_service import get_image_detection_service

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
    "",
    response_model=ShelvesResponse,
    summary="List monitored shelf zones",
)
async def list_shelves(
    status: Optional[str] = Query(default=None, description="all | low | critical")
) -> ShelvesResponse:
    """Lists all monitored retail shelf zones and stock levels.

    NOTE: Shelf inventory detection with YOLO11n is not supported; returning
    contract-valid empty response without fabricating fill percentages.
    """
    return ShelvesResponse(
        shelves=[],
        totalCount=0,
        criticalCount=0,
        lowStockCount=0,
    )


@router.get(
    "/{id}",
    response_model=ShelfItem,
    summary="Get individual shelf zone",
)
async def get_shelf(id: str) -> ShelfItem:
    """Retrieves an individual shelf bay status."""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Shelf zone '{id}' not found.",
    )
