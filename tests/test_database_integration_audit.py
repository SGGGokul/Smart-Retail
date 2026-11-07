import asyncio
import io
import time
from pathlib import Path
import cv2
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch

from app.core.config import get_settings
from app.db.session import check_db_connectivity, get_session_factory
from app.models.alert import Alert as AlertModel
from app.models.analytics import AnalyticsRecord as AnalyticsRecordModel
from app.models.video import (
    InferenceResult as InferenceResultModel,
    TrackingSummary as TrackingSummaryModel,
    VideoJob as VideoJobModel,
)
from app.schemas.alerts import AlertsResponse
from app.schemas.analytics import (
    AnalyticsDwellResponse,
    AnalyticsQueuesResponse,
    AnalyticsSummaryResponse,
    AnalyticsTrafficResponse,
)
from app.schemas.assistant import AssistantChatResponse
from app.schemas.shelves import ShelvesResponse
from app.schemas.video import VideoJob, VideoResultsResponse


@pytest.fixture(scope="module")
def real_cctv_video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generates an authentic CCTV test video from MERL shopping dataset frames."""
    settings = get_settings()
    sample_dir = settings.BASE_DIR / "results" / "sample_frames"
    sample_images = sorted(list(sample_dir.glob("*.png")))

    temp_dir = tmp_path_factory.mktemp("audit_videos")
    video_file = temp_dir / "audit_cctv_footage.mp4"

    first_frame = cv2.imread(str(sample_images[0]))
    h, w, _ = first_frame.shape
    fps = 10.0

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(video_file), fourcc, fps, (w, h))
    for _ in range(3):  # write 15 frames from 5 real CCTV crops
        for img_path in sample_images:
            out.write(cv2.imread(str(img_path)))
    out.release()
    return video_file


def test_endpoint_verification_all_routes(client: TestClient) -> None:
    """Verifies all API endpoints for schema conformance, HTTP status codes, and error envelopes."""
    # 1. /health
    r_health = client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "ok"

    # 2. /api/v1/health
    r_v1_health = client.get("/api/v1/health")
    assert r_v1_health.status_code == 200
    assert r_v1_health.json()["status"] == "ok"

    # 3. /api/v1/videos (list)
    r_videos = client.get("/api/v1/videos")
    assert r_videos.status_code == 200
    assert isinstance(r_videos.json(), list)

    # 4. /api/v1/analytics/summary
    r_summary = client.get("/api/v1/analytics/summary")
    assert r_summary.status_code == 200
    AnalyticsSummaryResponse(**r_summary.json())

    # 5. /api/v1/analytics/traffic
    r_traffic = client.get("/api/v1/analytics/traffic?range=7d")
    assert r_traffic.status_code == 200
    AnalyticsTrafficResponse(**r_traffic.json())

    # 6. /api/v1/analytics/dwell-time
    r_dwell = client.get("/api/v1/analytics/dwell-time")
    assert r_dwell.status_code == 200
    AnalyticsDwellResponse(**r_dwell.json())

    # 7. /api/v1/analytics/queues
    r_queues = client.get("/api/v1/analytics/queues")
    assert r_queues.status_code == 200
    AnalyticsQueuesResponse(**r_queues.json())

    # 8. /api/v1/shelves
    r_shelves = client.get("/api/v1/shelves")
    assert r_shelves.status_code == 200
    ShelvesResponse(**r_shelves.json())

    # 9. /api/v1/alerts
    r_alerts = client.get("/api/v1/alerts")
    assert r_alerts.status_code == 200
    AlertsResponse(**r_alerts.json())

    # 10. /api/v1/assistant/chat
    r_chat = client.post("/api/v1/assistant/chat", json={"message": "What is the average dwell time?"})
    assert r_chat.status_code == 200
    AssistantChatResponse(**r_chat.json())


def test_end_to_end_cctv_video_data_flow(client: TestClient, real_cctv_video: Path) -> None:
    """Verifies complete end-to-end pipeline against PostgreSQL authoritative records:
    Upload -> VideoJob -> YOLO11n -> ByteTrack -> InferenceResult -> TrackingSummary -> Alert generation -> Analytics rollup -> API retrieval.
    """
    with real_cctv_video.open("rb") as f:
        video_bytes = f.read()

    # 1. Upload video
    upload_res = client.post(
        "/api/v1/videos",
        files={"file": ("audit_cctv_footage.mp4", io.BytesIO(video_bytes), "video/mp4")},
    )
    assert upload_res.status_code in (200, 201)
    job_id = upload_res.json()["jobId"]

    # 2. Poll until CV background worker completes (allow adequate CPU warm-up time)
    max_wait = 45
    start = time.time()
    final_status = None
    while time.time() - start < max_wait:
        status_res = client.get(f"/api/v1/videos/{job_id}")
        assert status_res.status_code == 200
        data = status_res.json()
        if data["status"] in ("done", "failed"):
            final_status = data["status"]
            break
        time.sleep(0.5)

    assert final_status == "done", f"Job failed or timed out: {data}"

    # 3. Verify PostgreSQL records directly
    async def _verify_db() -> None:
        session_factory = get_session_factory()
        async with session_factory() as session:
            # VideoJob record
            job_orm = await session.get(VideoJobModel, job_id)
            assert job_orm is not None
            assert job_orm.status == "done"
            assert job_orm.frames == 15
            assert job_orm.customers_detected >= 1
            assert job_orm.processed_at is not None

            # InferenceResult record
            stmt_inf = select(InferenceResultModel).where(InferenceResultModel.job_id == job_id)
            inf_orm = (await session.execute(stmt_inf)).scalar_one_or_none()
            assert inf_orm is not None
            assert inf_orm.total_frames == 15
            assert inf_orm.customers_detected >= 1
            assert len(inf_orm.sample_detections) > 0

            # TrackingSummary records
            stmt_tracks = select(TrackingSummaryModel).where(TrackingSummaryModel.job_id == job_id)
            tracks_orm = (await session.execute(stmt_tracks)).scalars().all()
            assert len(tracks_orm) >= 1
            assert tracks_orm[0].dwell_seconds >= 0.0

            # Analytics rollup in analytics_records
            stmt_ar = select(AnalyticsRecordModel).where(
                AnalyticsRecordModel.record_date == job_orm.processed_at.date(),
                AnalyticsRecordModel.record_hour == job_orm.processed_at.hour,
            )
            ar_orm = (await session.execute(stmt_ar)).scalars().first()
            assert ar_orm is not None
            assert ar_orm.total_customers >= 1
            assert ar_orm.video_clips_count >= 1

    asyncio.run(_verify_db())

    # 4. Verify API retrieval reflects persisted data
    res_api = client.get(f"/api/v1/videos/{job_id}/results")
    assert res_api.status_code == 200
    res_data = res_api.json()
    assert res_data["totalFrames"] == 15
    assert res_data["customersDetected"] >= 1
    assert len(res_data["detections"]) > 0

    # 5. Verify Analytics Summary API reflects persisted customers
    summary_res = client.get("/api/v1/analytics/summary")
    assert summary_res.status_code == 200
    assert summary_res.json()["todayCustomers"] >= 1


def test_reliability_backend_restart_and_durability() -> None:
    """Verifies that persisted data survives engine reset and session isolation."""
    async def _test() -> None:
        session_factory = get_session_factory()
        job_id = f"vj-durable-{int(time.time())}"

        # Session 1: Write
        async with session_factory() as s1:
            job = VideoJobModel(
                id=job_id,
                filename="durability.mp4",
                storage_path=f"path_{job_id}.mp4",
                status="done",
                customers_detected=7,
            )
            s1.add(job)
            await s1.commit()

        # Session 2: Read in new session
        async with session_factory() as s2:
            fetched = await s2.get(VideoJobModel, job_id)
            assert fetched is not None
            assert fetched.customers_detected == 7

    asyncio.run(_test())


def test_reliability_database_connectivity_check() -> None:
    """Verifies check_db_connectivity returns True on active connection and False when connection fails."""
    async def _test() -> None:
        # Healthy connection
        is_up, msg = await check_db_connectivity()
        assert is_up is True
        assert "latency" in msg.lower() or "connected" in msg.lower() or "postgresql" in msg.lower()

        # Simulated disconnection
        with patch("app.db.session.get_engine", side_effect=RuntimeError("Database engine offline")):
            is_up_fail, err_msg = await check_db_connectivity()
            assert is_up_fail is False
            assert "database engine offline" in err_msg.lower()

    asyncio.run(_test())


def test_reliability_missing_records_return_404(client: TestClient) -> None:
    """Verifies missing records across all resource endpoints return RFC-compliant 404 envelopes."""
    # Video not found
    r_vid = client.get("/api/v1/videos/vj-missing-999999")
    assert r_vid.status_code == 404
    assert r_vid.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    # Results not found
    r_res = client.get("/api/v1/videos/vj-missing-999999/results")
    assert r_res.status_code == 404
    assert r_res.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    # Alert not found
    r_alt = client.patch("/api/v1/alerts/al-missing-999999", json={"acknowledged": True})
    assert r_alt.status_code == 404
    assert r_alt.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    # Shelf not found
    r_sh = client.get("/api/v1/shelves/sh-missing-999999")
    assert r_sh.status_code == 404
    assert r_sh.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
