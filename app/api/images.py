from fastapi import APIRouter, File, Query, UploadFile, status

from app.schemas.image import ImageDetectionResponse
from app.services.image_service import get_image_detection_service

router = APIRouter()


@router.post(
    "/detect",
    response_model=ImageDetectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload image for YOLO object and shelf detection",
)
async def detect_image(
    file: UploadFile = File(..., description="Image file (.jpg, .jpeg, .png, .webp)"),
    confidence: float = Query(default=0.25, ge=0.05, le=0.95, description="Detection confidence threshold"),
) -> ImageDetectionResponse:
    """Detects objects in an uploaded store or shelf image using YOLO and returns

    bounding boxes, class labels, counts, and an annotated image.
    """
    service = get_image_detection_service()
    return await service.detect_image(file, confidence_threshold=confidence)
