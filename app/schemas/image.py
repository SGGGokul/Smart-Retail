from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ImageBox(BaseModel):
    """Bounding box coordinates in both pixel coordinates and normalized dimensions."""
    x1: float = Field(..., description="Top-left X coordinate in pixels")
    y1: float = Field(..., description="Top-left Y coordinate in pixels")
    x2: float = Field(..., description="Bottom-right X coordinate in pixels")
    y2: float = Field(..., description="Bottom-right Y coordinate in pixels")
    x: float = Field(..., description="Normalized or pixel top-left X")
    y: float = Field(..., description="Normalized or pixel top-left Y")
    width: float = Field(..., description="Bounding box width")
    height: float = Field(..., description="Bounding box height")


class ImageDetectionBox(BaseModel):
    """Individual object detection item."""
    id: str = Field(..., description="Unique detection identifier")
    classId: int = Field(..., description="YOLO class index")
    label: str = Field(..., description="Detected class name (e.g., bottle, cup, person)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    box: ImageBox = Field(..., description="Bounding box coordinates")


class ImageDetectionResponse(BaseModel):
    """Response payload for image object and shelf detection."""
    filename: str = Field(..., description="Name of the processed image file")
    width: int = Field(..., description="Image width in pixels")
    height: int = Field(..., description="Image height in pixels")
    totalDetections: int = Field(..., description="Total count of detected objects")
    detections: List[ImageDetectionBox] = Field(default_factory=list, description="List of bounding boxes")
    detectionCounts: Dict[str, int] = Field(default_factory=dict, description="Counts aggregated by class label")
    annotatedImage: Optional[str] = Field(
        default=None,
        description="Base64-encoded JPEG data URL with drawn bounding boxes and labels",
    )
    modelUsed: str = Field(default="yolo11n.pt", description="YOLO model checkpoint name")
    isCocoGeneralModel: bool = Field(
        default=True,
        description="Whether inference used standard 80 COCO classes rather than dedicated retail shelf SKUs",
    )
    shelfDetectionSupported: bool = Field(
        default=False,
        description="Indicates whether native shelf bay / planogram compliance is supported by current weights",
    )
    note: str = Field(
        default=(
            "Standard COCO weights (80 classes) detected general retail objects. "
            "Native shelf inventory / planogram compliance requires specialized fine-tuned retail models (e.g. SKU-110K)."
        ),
        description="Transparency note on model capabilities",
    )
