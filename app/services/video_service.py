import asyncio
from concurrent.futures import ThreadPoolExecutor
import datetime
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings
from app.schemas.video import (
    JobStatus,
    VideoJob,
    VideoResultsResponse,
    VideoUploadResponse,
)
from app.services.cv_service import CVService
from app.services.rule_engine import get_rule_engine

logger = logging.getLogger("retailiq.video_service")

ALLOWED_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi"}

# Thread pool for CPU-bound video inference tasks
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cv-worker")


class VideoService:
    """Manages video job lifecycle, validation, asynchronous execution, and results.

    STAGE 2 IN-PROCESS WORKER LIMITATIONS:
      1. State is kept in process memory; restarting the server clears active/queued job history.
      2. Concurrency is limited by local host CPU/GPU cores (ThreadPoolExecutor max_workers=2).
      3. For multi-node high-throughput production, this architecture will migrate to Redis + Celery.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.upload_dir = settings.UPLOAD_DIR
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.cv_service = CVService(model_path=settings.MODEL_PATH)

        self._jobs: Dict[str, VideoJob] = {}
        self._results: Dict[str, VideoResultsResponse] = {}
        self._raw_cv_results: Dict[str, Dict[str, Any]] = {}
        self._counter = 100

    def _generate_job_id(self) -> str:
        self._counter += 1
        short_uuid = uuid.uuid4().hex[:4]
        return f"vj-{self._counter}-{short_uuid}"

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        # Strip path traversal and keep safe alphanumeric characters
        base = os.path.basename(filename)
        clean = re.sub(r"[^a-zA-Z0-9_.-]", "_", base)
        return clean or "uploaded_video.mp4"

    async def create_job(self, file: UploadFile) -> VideoUploadResponse:
        """Validate uploaded video, store it safely, and queue background CV inference."""
        filename = file.filename or "unknown.mp4"
        ext = Path(filename).suffix.lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported video format '{ext}'. Allowed formats: {sorted(ALLOWED_EXTENSIONS)}",
            )

        job_id = self._generate_job_id()
        safe_name = self._sanitize_filename(filename)
        dest_filename = f"{job_id}_{safe_name}"
        dest_path = self.upload_dir / dest_filename

        # Write file in chunks to disk safely
        total_bytes = 0
        try:
            with dest_path.open("wb") as out_file:
                while chunk := await file.read(1024 * 1024):  # 1MB chunks
                    total_bytes += len(chunk)
                    out_file.write(chunk)
        except Exception as exc:
            if dest_path.exists():
                dest_path.unlink(missing_ok=True)
            logger.error(f"Failed to save video upload {filename}: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to store video upload: {exc}",
            )

        if total_bytes == 0:
            if dest_path.exists():
                dest_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes).",
            )

        uploaded_time_str = datetime.datetime.now().strftime("Today %H:%M")

        job = VideoJob(
            id=job_id,
            file=safe_name,
            uploaded=uploaded_time_str,
            status="queued",
            frames=0,
            customersDetected=0,
        )
        self._jobs[job_id] = job

        logger.info(f"Queued video job {job_id} ({safe_name}, {total_bytes} bytes)")

        # Schedule asynchronous processing in background
        asyncio.create_task(self._run_async_job(job_id, dest_path))

        return VideoUploadResponse(
            jobId=job_id,
            filename=safe_name,
            status="queued",
            message="Video queued for CV inference.",
        )

    def _sync_process(self, job_id: str, video_path: Path) -> Dict[str, Any]:
        """Synchronous target executed inside ThreadPoolExecutor to prevent blocking loop."""
        def progress_cb(current_frames: int, unique_customers: int) -> None:
            if job_id in self._jobs:
                job = self._jobs[job_id]
                self._jobs[job_id] = job.model_copy(
                    update={
                        "status": "processing",
                        "frames": current_frames,
                        "customersDetected": unique_customers,
                    }
                )

        return self.cv_service.process_video(
            video_path=video_path,
            progress_callback=progress_cb,
        )

    async def _run_async_job(self, job_id: str, video_path: Path) -> None:
        """Asynchronous worker executing CV inference, updating status, and invoking rule engine."""
        loop = asyncio.get_running_loop()
        job = self._jobs.get(job_id)
        if not job:
            return

        self._jobs[job_id] = job.model_copy(update={"status": "processing"})
        logger.info(f"Job {job_id} status transitioned to 'processing'")

        try:
            cv_results = await loop.run_in_executor(_executor, self._sync_process, job_id, video_path)

            total_frames = cv_results["total_frames"]
            customers_detected = cv_results["unique_customers"]
            duration_s = cv_results["duration_seconds"]
            fps = cv_results["fps"]
            peak_count = cv_results["peak_occupancy"]
            avg_dwell_s = cv_results["average_dwell_seconds"]
            detections = cv_results["detections"]
            processed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # Store finished job state
            self._jobs[job_id] = self._jobs[job_id].model_copy(
                update={
                    "status": "done",
                    "frames": total_frames,
                    "customersDetected": customers_detected,
                    "durationSeconds": duration_s,
                    "fps": fps,
                    "processedAt": processed_at,
                }
            )

            # Store results conforming to VideoResultsResponse schema
            self._results[job_id] = VideoResultsResponse(
                jobId=job_id,
                status="done",
                totalFrames=total_frames,
                customersDetected=customers_detected,
                peakCount=peak_count,
                averageDwellSeconds=avg_dwell_s,
                detections=detections,
            )

            self._raw_cv_results[job_id] = cv_results

            # Evaluate CV telemetry in RuleEngine for genuine alerts
            rule_engine = get_rule_engine()
            rule_engine.evaluate_cv_results(cv_results)

            logger.info(f"Job {job_id} completed successfully ({customers_detected} customers detected).")

        except Exception as exc:
            logger.exception(f"Inference job {job_id} failed: {exc}")
            if job_id in self._jobs:
                self._jobs[job_id] = self._jobs[job_id].model_copy(
                    update={
                        "status": "failed",
                        "error": str(exc),
                    }
                )

    def get_job(self, job_id: str) -> Optional[VideoJob]:
        """Fetch job metadata by id."""
        return self._jobs.get(job_id)

    def list_jobs(self) -> List[VideoJob]:
        """List historical video processing jobs."""
        return list(reversed(list(self._jobs.values())))

    def get_results(self, job_id: str) -> Optional[VideoResultsResponse]:
        """Fetch detailed inference results for a completed job."""
        return self._results.get(job_id)

    def get_raw_results(self) -> List[Dict[str, Any]]:
        """Return raw completed CV results for analytics aggregation."""
        return list(self._raw_cv_results.values())


_video_service: Optional[VideoService] = None


def get_video_service() -> VideoService:
    """Singleton getter for video service."""
    global _video_service
    if _video_service is None:
        _video_service = VideoService()
    return _video_service
