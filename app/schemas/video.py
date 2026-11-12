from typing import List, Literal, Optional
from pydantic import BaseModel, Field

JobStatus = Literal["queued", "processing", "done", "failed"]


class VideoBox(BaseModel):
    """Bounding box coordinates for detected object."""
    x: int
    y: int
    width: int
    height: int


class VideoDetectionBox(BaseModel):
    """Individual detection representation."""
    id: str
    label: str = "person"
    confidence: float
    box: VideoBox


class VideoUploadResponse(BaseModel):
    """Response returned upon video upload."""
    jobId: str
    filename: str
    status: JobStatus
    message: str


class VideoJob(BaseModel):
    """Video processing job record."""
    id: str
    file: str
    uploaded: str
    uploadedAt: Optional[str] = None
    status: JobStatus
    frames: int = 0
    customersDetected: int = 0
    durationSeconds: Optional[float] = None
    fps: Optional[float] = None
    processedAt: Optional[str] = None
    error: Optional[str] = None


class VideoResultsResponse(BaseModel):
    """Detailed analytics and detections for completed video job."""
    jobId: str
    status: JobStatus
    totalFrames: int
    customersDetected: int
    peakCount: int
    averageDwellSeconds: float
    detections: List[VideoDetectionBox] = Field(default_factory=list)
