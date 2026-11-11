import asyncio
import uuid
from typing import Any, Dict, List
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.video import (
    InferenceResult,
    TrackingSummary,
    VideoJob as VideoJobModel,
)
from app.schemas.video import VideoBox, VideoDetectionBox, VideoResultsResponse
from app.services.video_service import get_video_service


def _sample_cv_results() -> Dict[str, Any]:
    return {
        "filename": "store_entrance_test.mp4",
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "total_frames": 300,
        "reported_frames": 300,
        "duration_seconds": 10.0,
        "elapsed_seconds": 1.25,
        "measured_fps": 240.0,
        "unique_customers": 4,
        "tracks_valid_dwell": 4,
        "peak_occupancy": 3,
        "average_occupancy": 1.8,
        "average_dwell_seconds": 5.4,
        "maximum_dwell_seconds": 8.2,
        "minimum_dwell_seconds": 2.1,
        "entries": 3,
        "exits": 2,
        "detections": [
            VideoDetectionBox(
                id="det-1",
                label="person",
                confidence=0.92,
                box=VideoBox(x=100, y=150, width=80, height=200),
            ),
            VideoDetectionBox(
                id="det-2",
                label="person",
                confidence=0.88,
                box=VideoBox(x=300, y=180, width=85, height=210),
            ),
        ],
        "tracking_summaries": [
            {
                "track_id": 1,
                "first_frame": 1,
                "last_frame": 150,
                "dwell_seconds": 5.0,
                "hit_count": 140,
                "hit_rate": 0.93,
                "crossed_entrance": True,
                "crossed_exit": False,
            },
            {
                "track_id": 2,
                "first_frame": 20,
                "last_frame": 200,
                "dwell_seconds": 6.0,
                "hit_count": 170,
                "hit_rate": 0.94,
                "crossed_entrance": True,
                "crossed_exit": True,
            },
        ],
    }


def test_inference_and_tracking_persistence() -> None:
    """Verifies that persist_inference_and_tracking stores both InferenceResult and TrackingSummary."""
    async def _run() -> None:
        video_service = get_video_service()
        session_factory = get_session_factory()
        job_id = f"vj-inf-{uuid.uuid4().hex[:6]}"

        # Seed initial job
        async with session_factory() as session:
            job = VideoJobModel(
                id=job_id,
                filename="store_entrance_test.mp4",
                storage_path=f"data/uploads/{job_id}.mp4",
                file_size_bytes=1000000,
                status="processing",
            )
            session.add(job)
            await session.commit()

        cv_results = _sample_cv_results()
        await video_service.persist_inference_and_tracking(job_id, cv_results)

        # Verify job updated to done
        job_schema = await video_service.get_job(job_id)
        assert job_schema is not None
        assert job_schema.status == "done"
        assert job_schema.frames == 300
        assert job_schema.customersDetected == 4

        # Verify inference result retrieved
        results = await video_service.get_results(job_id)
        assert results is not None
        assert results.jobId == job_id
        assert results.status == "done"
        assert results.totalFrames == 300
        assert results.customersDetected == 4
        assert results.peakCount == 3
        assert results.averageDwellSeconds == 5.4
        assert len(results.detections) == 2
        assert results.detections[0].id == "det-1"
        assert results.detections[0].confidence == 0.92

        # Verify tracking summaries retrieved
        tracks = await video_service.get_tracking_summaries(job_id)
        assert len(tracks) == 2
        assert tracks[0].track_id == 1
        assert tracks[0].dwell_seconds == 5.0
        assert tracks[0].crossed_entrance is True
        assert tracks[0].crossed_exit is False
        assert tracks[1].track_id == 2
        assert tracks[1].crossed_exit is True

    asyncio.run(_run())


def test_inference_and_tracking_cross_session_durability() -> None:
    """Verifies persisted results survive completely separate DB sessions."""
    async def _run() -> None:
        video_service = get_video_service()
        session_factory = get_session_factory()
        job_id = f"vj-dur-{uuid.uuid4().hex[:6]}"

        # Session 1: Create job and persist inference
        async with session_factory() as s1:
            job = VideoJobModel(
                id=job_id,
                filename="durability_test.mp4",
                storage_path=f"data/uploads/{job_id}.mp4",
                file_size_bytes=500000,
                status="processing",
            )
            s1.add(job)
            await s1.commit()

        cv_results = _sample_cv_results()
        await video_service.persist_inference_and_tracking(job_id, cv_results)

        # Session 2: Read from entirely new session directly via ORM
        async with session_factory() as s2:
            inf_res = await s2.execute(
                select(InferenceResult).where(InferenceResult.job_id == job_id)
            )
            inf_record = inf_res.scalar_one_or_none()
            assert inf_record is not None
            assert inf_record.total_frames == 300
            assert inf_record.customers_detected == 4
            assert inf_record.peak_count == 3

            track_res = await s2.execute(
                select(TrackingSummary)
                .where(TrackingSummary.job_id == job_id)
                .order_by(TrackingSummary.track_id)
            )
            track_records = track_res.scalars().all()
            assert len(track_records) == 2
            assert track_records[0].track_id == 1
            assert track_records[0].dwell_seconds == 5.0

    asyncio.run(_run())


def test_missing_inference_returns_none_or_in_progress() -> None:
    """Verifies that querying results for a nonexistent or incomplete job behaves correctly."""
    async def _run() -> None:
        video_service = get_video_service()
        # Nonexistent job
        res = await video_service.get_results("vj-nonexistent-12345")
        assert res is None

        tracks = await video_service.get_tracking_summaries("vj-nonexistent-12345")
        assert tracks == []

    asyncio.run(_run())


def test_retry_idempotence_prevents_duplicate_records() -> None:
    """Verifies that re-running persist_inference_and_tracking updates records without duplication."""
    async def _run() -> None:
        video_service = get_video_service()
        session_factory = get_session_factory()
        job_id = f"vj-retry-{uuid.uuid4().hex[:6]}"

        # Seed job
        async with session_factory() as s:
            job = VideoJobModel(
                id=job_id,
                filename="retry_test.mp4",
                storage_path=f"data/uploads/{job_id}.mp4",
                file_size_bytes=200000,
                status="processing",
            )
            s.add(job)
            await s.commit()

        cv_data_1 = _sample_cv_results()
        await video_service.persist_inference_and_tracking(job_id, cv_data_1)

        # Retry with updated customer count
        cv_data_2 = _sample_cv_results()
        cv_data_2["unique_customers"] = 7
        await video_service.persist_inference_and_tracking(job_id, cv_data_2)

        # Verify no duplicate inference results
        async with session_factory() as s_check:
            inf_res = await s_check.execute(
                select(InferenceResult).where(InferenceResult.job_id == job_id)
            )
            all_infs = inf_res.scalars().all()
            assert len(all_infs) == 1
            assert all_infs[0].customers_detected == 7

            track_res = await s_check.execute(
                select(TrackingSummary).where(TrackingSummary.job_id == job_id)
            )
            all_tracks = track_res.scalars().all()
            assert len(all_tracks) == 2  # Not 4!

    asyncio.run(_run())


def test_api_results_endpoint_with_persisted_data(client: TestClient) -> None:
    """Verifies GET /api/v1/videos/{id}/results returns persisted inference data."""
    async def _seed() -> str:
        video_service = get_video_service()
        session_factory = get_session_factory()
        job_id = f"vj-api-res-{uuid.uuid4().hex[:6]}"

        async with session_factory() as s:
            job = VideoJobModel(
                id=job_id,
                filename="api_clip.mp4",
                storage_path=f"data/uploads/{job_id}.mp4",
                file_size_bytes=300000,
                status="processing",
            )
            s.add(job)
            await s.commit()

        cv_results = _sample_cv_results()
        await video_service.persist_inference_and_tracking(job_id, cv_results)
        return job_id

    job_id = asyncio.run(_seed())

    # Call API endpoint
    response = client.get(f"/api/v1/videos/{job_id}/results")
    assert response.status_code == 200
    data = response.json()
    validated = VideoResultsResponse(**data)
    assert validated.jobId == job_id
    assert validated.status == "done"
    assert validated.totalFrames == 300
    assert validated.customersDetected == 4
    assert validated.peakCount == 3
    assert validated.averageDwellSeconds == 5.4
    assert len(validated.detections) == 2
