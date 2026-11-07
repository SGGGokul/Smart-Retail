from typing import List
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.schemas.video import (
    VideoJob,
    VideoResultsResponse,
    VideoUploadResponse,
)
from app.services.video_service import get_video_service

router = APIRouter()


@router.post(
    "",
    response_model=VideoUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload video for CV processing",
)
async def upload_video(file: UploadFile = File(...)) -> VideoUploadResponse:
    """Uploads a CCTV or store video file for asynchronous detection and tracking."""
    video_service = get_video_service()
    return await video_service.create_job(file)


@router.get(
    "",
    response_model=List[VideoJob],
    summary="List video processing jobs",
)
async def list_videos() -> List[VideoJob]:
    """Retrieves all historical and active video processing jobs."""
    video_service = get_video_service()
    return await video_service.list_jobs()


@router.get(
    "/{id}",
    response_model=VideoJob,
    summary="Get video job status",
)
async def get_video(id: str) -> VideoJob:
    """Checks the processing status and metadata of a video job."""
    video_service = get_video_service()
    job = await video_service.get_job(id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video job '{id}' was not found.",
        )
    return job


@router.get(
    "/{id}/results",
    response_model=VideoResultsResponse,
    summary="Get video inference results",
)
async def get_video_results(id: str) -> VideoResultsResponse:
    """Fetches detailed detection bounding boxes, customer counts, and metrics for a completed video job."""
    video_service = get_video_service()
    job = await video_service.get_job(id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video job '{id}' was not found.",
        )

    results = await video_service.get_results(id)
    if results is None:
        if job.status == "failed":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Video processing failed for job '{id}': {job.error}",
            )
        # Job still queued or processing
        return VideoResultsResponse(
            jobId=id,
            status=job.status,
            totalFrames=job.frames,
            customersDetected=job.customersDetected,
            peakCount=0,
            averageDwellSeconds=0.0,
            detections=[],
        )

    return results
