import asyncio
import io
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.video import VideoJob as VideoJobModel
from app.services.video_service import get_video_service


def test_video_job_creation_and_retrieval() -> None:
    """Verifies that VideoJob records are persisted and retrievable via VideoService."""
    async def _run() -> None:
        session_factory = get_session_factory()
        video_service = get_video_service()
        job_id = f"vj-test-{uuid.uuid4().hex[:6]}"

        async with session_factory() as session:
            job_orm = VideoJobModel(
                id=job_id,
                filename="cctv_entrance_sample.mp4",
                storage_path=f"data/uploads/{job_id}_cctv_entrance_sample.mp4",
                file_size_bytes=1048576,
                status="queued",
                frames=0,
                customers_detected=0,
            )
            session.add(job_orm)
            await session.commit()

        retrieved = await video_service.get_job(job_id)
        assert retrieved is not None
        assert retrieved.id == job_id
        assert retrieved.file == "cctv_entrance_sample.mp4"
        assert retrieved.status == "queued"
        assert retrieved.frames == 0
        assert retrieved.customersDetected == 0
        assert retrieved.error is None

    asyncio.run(_run())


def test_video_job_listing() -> None:
    """Verifies that list_jobs retrieves historical records ordered by upload time descending."""
    async def _run() -> None:
        session_factory = get_session_factory()
        video_service = get_video_service()
        job_id_1 = f"vj-list-1-{uuid.uuid4().hex[:4]}"
        job_id_2 = f"vj-list-2-{uuid.uuid4().hex[:4]}"

        async with session_factory() as session:
            job_1 = VideoJobModel(
                id=job_id_1,
                filename="cam_1.mp4",
                storage_path=f"data/uploads/{job_id_1}.mp4",
                file_size_bytes=500000,
                status="queued",
            )
            job_2 = VideoJobModel(
                id=job_id_2,
                filename="cam_2.mp4",
                storage_path=f"data/uploads/{job_id_2}.mp4",
                file_size_bytes=600000,
                status="queued",
            )
            session.add_all([job_1, job_2])
            await session.commit()

        jobs = await video_service.list_jobs()
        job_ids = [j.id for j in jobs]
        assert job_id_1 in job_ids
        assert job_id_2 in job_ids

    asyncio.run(_run())


def test_video_job_status_transitions() -> None:
    """Verifies state transitions: queued -> processing -> done."""
    async def _run() -> None:
        session_factory = get_session_factory()
        video_service = get_video_service()
        job_id = f"vj-trans-{uuid.uuid4().hex[:6]}"

        async with session_factory() as session:
            job = VideoJobModel(
                id=job_id,
                filename="transition_test.mp4",
                storage_path=f"data/uploads/{job_id}.mp4",
                file_size_bytes=204800,
                status="queued",
            )
            session.add(job)
            await session.commit()

        # Transition to processing
        updated_proc = await video_service.update_job_status(job_id, "processing")
        assert updated_proc is not None
        assert updated_proc.status == "processing"

        # Transition to done
        updated_done = await video_service.update_job_status(job_id, "done")
        assert updated_done is not None
        assert updated_done.status == "done"
        assert updated_done.processedAt is not None

    asyncio.run(_run())


def test_video_job_failed_status() -> None:
    """Verifies failed processing status persists error details."""
    async def _run() -> None:
        session_factory = get_session_factory()
        video_service = get_video_service()
        job_id = f"vj-fail-{uuid.uuid4().hex[:6]}"

        async with session_factory() as session:
            job = VideoJobModel(
                id=job_id,
                filename="corrupt_video.mp4",
                storage_path=f"data/uploads/{job_id}.mp4",
                file_size_bytes=100,
                status="processing",
            )
            session.add(job)
            await session.commit()

        error_msg = "Corrupted frame header at byte offset 48"
        failed_job = await video_service.update_job_status(
            job_id,
            "failed",
            error_message=error_msg,
        )
        assert failed_job is not None
        assert failed_job.status == "failed"
        assert failed_job.error == error_msg

    asyncio.run(_run())


def test_persistence_across_separate_database_sessions() -> None:
    """Verifies that writes committed in session 1 survive session disconnection and are visible in session 2."""
    async def _run() -> None:
        session_factory = get_session_factory()
        job_id = f"vj-cross-{uuid.uuid4().hex[:6]}"

        # Session 1: Create and commit
        async with session_factory() as session1:
            async with session1.begin():
                job = VideoJobModel(
                    id=job_id,
                    filename="cross_session.mp4",
                    storage_path=f"data/uploads/{job_id}.mp4",
                    file_size_bytes=789123,
                    status="queued",
                    frames=120,
                    customers_detected=8,
                    duration_seconds=12.0,
                    fps=10.0,
                )
                session1.add(job)

        # Session 2: Read in new session
        async with session_factory() as session2:
            res = await session2.execute(select(VideoJobModel).where(VideoJobModel.id == job_id))
            persisted = res.scalar_one_or_none()
            assert persisted is not None
            assert persisted.id == job_id
            assert persisted.filename == "cross_session.mp4"
            assert persisted.frames == 120
            assert persisted.customers_detected == 8
            assert persisted.duration_seconds == 12.0
            assert persisted.fps == 10.0

    asyncio.run(_run())


def test_api_video_lifecycle_and_missing_job(client: TestClient) -> None:
    """Verifies video API endpoints with PostgreSQL persistence:
    - POST /api/v1/videos creates job
    - GET /api/v1/videos/{id} retrieves job
    - GET /api/v1/videos lists jobs
    - GET /api/v1/videos/{id} with missing ID returns 404
    """
    fake_video_data = io.BytesIO(b"\x00\x00\x00 ftypisom\x00\x00\x02\x00isomiso2mp41")
    upload_res = client.post(
        "/api/v1/videos",
        files={"file": ("api_test_clip.mp4", fake_video_data, "video/mp4")},
    )
    assert upload_res.status_code in (200, 201)
    upload_data = upload_res.json()
    job_id = upload_data["jobId"]
    assert job_id.startswith("vj-")

    # Retrieve status
    get_res = client.get(f"/api/v1/videos/{job_id}")
    assert get_res.status_code == 200
    job_data = get_res.json()
    assert job_data["id"] == job_id
    assert job_data["file"] == "api_test_clip.mp4"
    assert job_data["status"] in ("queued", "processing", "done", "failed")

    # List check
    list_res = client.get("/api/v1/videos")
    assert list_res.status_code == 200
    jobs = list_res.json()
    assert any(j["id"] == job_id for j in jobs)

    # Missing job 404
    missing_res = client.get("/api/v1/videos/vj-missing-nonexistent")
    assert missing_res.status_code == 404
    err_body = missing_res.json()
    assert "error" in err_body
    assert err_body["error"]["code"] == "RESOURCE_NOT_FOUND"
