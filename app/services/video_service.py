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
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models.customer_journey import CustomerVisitModel, CustomerZoneEventModel
from app.models.video import (
    InferenceResult,
    TrackingSummary,
    VideoJob as VideoJobModel,
)
from app.schemas.video import (
    JobStatus,
    VideoBox,
    VideoDetectionBox,
    VideoJob as VideoJobSchema,
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
    """Manages video job lifecycle, validation, asynchronous execution, and results

    backed by PostgreSQL persistence.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.upload_dir = settings.UPLOAD_DIR
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.cv_service = CVService(model_path=settings.MODEL_PATH)
        self._counter = 100

    def _generate_job_id(self) -> str:
        self._counter += 1
        short_uuid = uuid.uuid4().hex[:4]
        return f"vj-{self._counter}-{short_uuid}"

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        base = os.path.basename(filename)
        clean = re.sub(r"[^a-zA-Z0-9_.-]", "_", base)
        return clean or "uploaded_video.mp4"

    @staticmethod
    def _orm_to_schema(job_orm: VideoJobModel) -> VideoJobSchema:
        uploaded_str = (
            job_orm.uploaded_at.strftime("Today %H:%M")
            if job_orm.uploaded_at
            else datetime.datetime.now().strftime("Today %H:%M")
        )
        processed_str = (
            job_orm.processed_at.isoformat()
            if job_orm.processed_at
            else None
        )
        return VideoJobSchema(
            id=job_orm.id,
            file=job_orm.filename,
            uploaded=uploaded_str,
            status=job_orm.status,  # type: ignore[arg-type]
            frames=job_orm.frames,
            customersDetected=job_orm.customers_detected,
            durationSeconds=job_orm.duration_seconds,
            fps=job_orm.fps,
            processedAt=processed_str,
            error=job_orm.error_message,
        )

    async def create_job(
        self,
        file: UploadFile,
        session: Optional[AsyncSession] = None,
    ) -> VideoUploadResponse:
        """Validate uploaded video, store it safely, persist to PostgreSQL, and queue background CV inference."""
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

        # Persist initial record in PostgreSQL
        new_job = VideoJobModel(
            id=job_id,
            filename=safe_name,
            storage_path=str(dest_path),
            file_size_bytes=total_bytes,
            status="queued",
            frames=0,
            customers_detected=0,
        )

        if session is not None:
            session.add(new_job)
            await session.commit()
        else:
            session_factory = get_session_factory()
            async with session_factory() as s:
                async with s.begin():
                    s.add(new_job)

        logger.info(f"Persisted and queued video job {job_id} ({safe_name}, {total_bytes} bytes)")

        # Schedule asynchronous processing in background
        asyncio.create_task(self._run_async_job(job_id, dest_path))

        return VideoUploadResponse(
            jobId=job_id,
            filename=safe_name,
            status="queued",
            message="Video queued for CV inference.",
        )

    def _sync_process(self, video_path: Path) -> Dict[str, Any]:
        """Synchronous target executed inside ThreadPoolExecutor.

        Never interacts with database sessions or async loops.
        """
        return self.cv_service.process_video(video_path=video_path)

    async def persist_inference_and_tracking(
        self,
        job_id: str,
        cv_results: Dict[str, Any],
        session: Optional[AsyncSession] = None,
    ) -> InferenceResult:
        """Persist YOLO inference results and ByteTrack tracking summaries in a single transactional unit."""
        total_frames = cv_results["total_frames"]
        customers_detected = cv_results["unique_customers"]
        duration_s = cv_results["duration_seconds"]
        fps = cv_results["fps"]
        peak_count = cv_results["peak_occupancy"]
        avg_dwell_s = cv_results["average_dwell_seconds"]
        detections = cv_results.get("detections", [])
        tracking_data = cv_results.get("tracking_summaries", [])
        processed_at = datetime.datetime.now(datetime.timezone.utc)

        sample_dets = [
            d.model_dump() if hasattr(d, "model_dump") else d
            for d in detections
        ]
        clean_raw_metrics = {
            k: v for k, v in cv_results.items()
            if k not in ("detections", "visits", "journey_events")
        }
        visits = cv_results.get("visits", [])
        journey_events = cv_results.get("journey_events", [])

        async def _do_persist(s: AsyncSession) -> InferenceResult:
            # Prevent duplicate records on retry
            await s.execute(delete(InferenceResult).where(InferenceResult.job_id == job_id))
            await s.execute(delete(TrackingSummary).where(TrackingSummary.job_id == job_id))

            # Clean up existing customer visits/events for this job if any
            existing_visits_q = await s.execute(
                select(CustomerVisitModel.id).where(CustomerVisitModel.video_job_id == job_id)
            )
            existing_vids = list(existing_visits_q.scalars().all())
            if existing_vids:
                await s.execute(
                    delete(CustomerZoneEventModel).where(CustomerZoneEventModel.visit_id.in_(existing_vids))
                )
                await s.execute(
                    delete(CustomerVisitModel).where(CustomerVisitModel.video_job_id == job_id)
                )

            inference_orm = InferenceResult(
                job_id=job_id,
                total_frames=total_frames,
                customers_detected=customers_detected,
                peak_count=peak_count,
                average_dwell_seconds=avg_dwell_s,
                sample_detections=sample_dets,
                raw_metrics=clean_raw_metrics,
            )
            s.add(inference_orm)

            for t in tracking_data:
                summary_orm = TrackingSummary(
                    job_id=job_id,
                    track_id=t["track_id"],
                    first_frame=t["first_frame"],
                    last_frame=t["last_frame"],
                    dwell_seconds=t["dwell_seconds"],
                    hit_count=t["hit_count"],
                    hit_rate=t["hit_rate"],
                    crossed_entrance=t["crossed_entrance"],
                    crossed_exit=t["crossed_exit"],
                )
                s.add(summary_orm)

            # Persist customer visits and journey events
            for v in visits:
                v_status = v.status.value if hasattr(v.status, "value") else str(v.status)
                cam_id = list(v.cameras_seen)[0] if v.cameras_seen else "cam-main"
                visit_orm = CustomerVisitModel(
                    id=v.visit_id,
                    customer_id=v.customer_id,
                    video_job_id=job_id,
                    store_id=getattr(v, "store_id", "store-104"),
                    camera_id=cam_id,
                    entry_time=float(v.entry_time),
                    exit_time=float(v.exit_time) if v.exit_time is not None else None,
                    duration_seconds=float(v.duration_seconds),
                    status=v_status,
                    zones_visited=list(v.zones_visited),
                    zone_dwell_times=dict(v.zone_dwell_times),
                    is_repeat_visit=bool(v.is_repeat_visit),
                    visit_number=int(v.visit_number),
                )
                s.add(visit_orm)

            for ev in journey_events:
                event_orm = CustomerZoneEventModel(
                    id=ev.event_id,
                    visit_id=ev.visit_id,
                    customer_id=ev.customer_id,
                    camera_id=ev.camera_id,
                    zone_id=ev.zone_id,
                    zone_name=ev.zone_name,
                    event_type=ev.event_type,
                    timestamp=float(ev.timestamp),
                    dwell_seconds=float(ev.dwell_seconds),
                )
                s.add(event_orm)

            stmt = (
                update(VideoJobModel)
                .where(VideoJobModel.id == job_id)
                .values(
                    status="done",
                    frames=total_frames,
                    customers_detected=customers_detected,
                    duration_seconds=duration_s,
                    fps=fps,
                    processed_at=processed_at,
                )
            )
            await s.execute(stmt)
            return inference_orm

        if session is not None:
            inf = await _do_persist(session)
            await session.commit()
        else:
            session_factory = get_session_factory()
            async with session_factory() as s:
                async with s.begin():
                    inf = await _do_persist(s)

        return inf

    async def _run_async_job(self, job_id: str, video_path: Path) -> None:
        """Asynchronous worker executing CV inference, persisting results in DB, and invoking rule engine."""
        loop = asyncio.get_running_loop()
        session_factory = get_session_factory()

        # Transition status to processing in dedicated session
        try:
            async with session_factory() as session:
                async with session.begin():
                    stmt = (
                        update(VideoJobModel)
                        .where(VideoJobModel.id == job_id)
                        .values(status="processing")
                    )
                    await session.execute(stmt)
            logger.info(f"Job {job_id} status transitioned to 'processing' in DB")
        except Exception as exc:
            logger.error(f"Failed to update job {job_id} status to processing: {exc}")

        try:
            cv_results = await loop.run_in_executor(_executor, self._sync_process, video_path)

            # Persist results in PostgreSQL
            await self.persist_inference_and_tracking(job_id, cv_results)

            # Evaluate CV telemetry in RuleEngine for genuine alerts
            rule_engine = get_rule_engine()
            await rule_engine.evaluate_and_persist(cv_results, job_id=job_id)

            # Persist and roll up analytics in PostgreSQL
            from app.services.analytics_service import get_analytics_service
            analytics_service = get_analytics_service()
            await analytics_service.record_job_analytics(job_id, cv_results)

            cust_count = cv_results.get("unique_customers", 0)
            tracks_count = len(cv_results.get("tracking_summaries", []))
            logger.info(
                f"Job {job_id} completed and persisted successfully "
                f"({cust_count} customers, {tracks_count} tracking summaries)."
            )

        except Exception as exc:
            logger.exception(f"Inference job {job_id} failed: {exc}")
            try:
                async with session_factory() as session:
                    async with session.begin():
                        stmt = (
                            update(VideoJobModel)
                            .where(VideoJobModel.id == job_id)
                            .values(
                                status="failed",
                                error_message=str(exc),
                            )
                        )
                        await session.execute(stmt)
            except Exception as db_exc:
                logger.error(f"Failed to update failed job {job_id} in DB: {db_exc}")

    async def get_job(
        self,
        job_id: str,
        session: Optional[AsyncSession] = None,
    ) -> Optional[VideoJobSchema]:
        """Fetch job metadata from PostgreSQL by id."""
        if session is not None:
            job_orm = await session.get(VideoJobModel, job_id)
            return self._orm_to_schema(job_orm) if job_orm else None

        session_factory = get_session_factory()
        async with session_factory() as s:
            job_orm = await s.get(VideoJobModel, job_id)
            return self._orm_to_schema(job_orm) if job_orm else None

    async def list_jobs(
        self,
        session: Optional[AsyncSession] = None,
    ) -> List[VideoJobSchema]:
        """List historical video processing jobs ordered by upload time descending."""
        stmt = select(VideoJobModel).order_by(VideoJobModel.uploaded_at.desc())
        if session is not None:
            result = await session.execute(stmt)
            return [self._orm_to_schema(j) for j in result.scalars().all()]

        session_factory = get_session_factory()
        async with session_factory() as s:
            result = await s.execute(stmt)
            return [self._orm_to_schema(j) for j in result.scalars().all()]

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error_message: Optional[str] = None,
        session: Optional[AsyncSession] = None,
    ) -> Optional[VideoJobSchema]:
        """Update job status and optional error message in PostgreSQL."""
        values: Dict[str, Any] = {"status": status}
        if error_message is not None:
            values["error_message"] = error_message
        if status == "done":
            values["processed_at"] = datetime.datetime.now(datetime.timezone.utc)

        stmt = update(VideoJobModel).where(VideoJobModel.id == job_id).values(**values)

        if session is not None:
            await session.execute(stmt)
            await session.commit()
            return await self.get_job(job_id, session=session)

        session_factory = get_session_factory()
        async with session_factory() as s:
            async with s.begin():
                await s.execute(stmt)
            return await self.get_job(job_id, session=s)

    async def get_results(
        self,
        job_id: str,
        session: Optional[AsyncSession] = None,
    ) -> Optional[VideoResultsResponse]:
        """Fetch detailed inference results for a completed job from PostgreSQL."""
        stmt = (
            select(InferenceResult, VideoJobModel)
            .join(VideoJobModel, InferenceResult.job_id == VideoJobModel.id)
            .where(InferenceResult.job_id == job_id)
        )
        if session is not None:
            res = await session.execute(stmt)
            row = res.first()
        else:
            session_factory = get_session_factory()
            async with session_factory() as s:
                res = await s.execute(stmt)
                row = res.first()

        if not row:
            return None

        inf, job = row
        detections: List[VideoDetectionBox] = []
        for d in inf.sample_detections:
            if isinstance(d, dict):
                box_dict = d.get("box", {})
                detections.append(
                    VideoDetectionBox(
                        id=d.get("id", "det-0"),
                        label=d.get("label", "person"),
                        confidence=d.get("confidence", 1.0),
                        box=VideoBox(
                            x=box_dict.get("x", 0),
                            y=box_dict.get("y", 0),
                            width=box_dict.get("width", 1),
                            height=box_dict.get("height", 1),
                        ),
                    )
                )

        return VideoResultsResponse(
            jobId=inf.job_id,
            status=job.status,  # type: ignore[arg-type]
            totalFrames=inf.total_frames,
            customersDetected=inf.customers_detected,
            peakCount=inf.peak_count,
            averageDwellSeconds=inf.average_dwell_seconds,
            detections=detections,
        )

    async def get_tracking_summaries(
        self,
        job_id: str,
        session: Optional[AsyncSession] = None,
    ) -> List[TrackingSummary]:
        """Fetch ByteTrack tracking summary records for a video job from PostgreSQL."""
        stmt = (
            select(TrackingSummary)
            .where(TrackingSummary.job_id == job_id)
            .order_by(TrackingSummary.track_id.asc())
        )
        if session is not None:
            res = await session.execute(stmt)
            return list(res.scalars().all())

        session_factory = get_session_factory()
        async with session_factory() as s:
            res = await s.execute(stmt)
            return list(res.scalars().all())

    def get_raw_results(self) -> List[Dict[str, Any]]:
        """Deprecated: Returns empty list as analytics are directly queried from PostgreSQL."""
        return []


_video_service: Optional[VideoService] = None


def get_video_service() -> VideoService:
    """Singleton getter for video service."""
    global _video_service
    if _video_service is None:
        _video_service = VideoService()
    return _video_service
