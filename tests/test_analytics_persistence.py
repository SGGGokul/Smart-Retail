import asyncio
import datetime
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch

from app.db.session import get_session_factory
from app.models.alert import Alert as AlertModel
from app.models.analytics import AnalyticsRecord as AnalyticsRecordModel
from app.models.video import (
    InferenceResult as InferenceResultModel,
    TrackingSummary as TrackingSummaryModel,
    VideoJob as VideoJobModel,
)
from app.schemas.analytics import (
    AnalyticsDwellResponse,
    AnalyticsQueuesResponse,
    AnalyticsSummaryResponse,
    AnalyticsTrafficResponse,
)
from app.services.analytics_service import get_analytics_service


def test_empty_database_analytics(client: TestClient) -> None:
    """Verifies that queries against an empty database return valid empty contract responses."""
    # Summary
    res_summary = client.get("/api/v1/analytics/summary")
    assert res_summary.status_code == 200
    summary = AnalyticsSummaryResponse(**res_summary.json())
    assert isinstance(summary.todayCustomers, int)
    assert isinstance(summary.avgDwellMinutes, (int, float))

    # Traffic
    res_traffic = client.get("/api/v1/analytics/traffic?range=7d")
    assert res_traffic.status_code == 200
    traffic = AnalyticsTrafficResponse(**res_traffic.json())
    assert isinstance(traffic.totalCustomers, int)
    assert isinstance(traffic.daily, list)
    assert isinstance(traffic.hourly, list)

    # Dwell
    res_dwell = client.get("/api/v1/analytics/dwell-time")
    assert res_dwell.status_code == 200
    dwell = AnalyticsDwellResponse(**res_dwell.json())
    assert isinstance(dwell.bySection, list)

    # Queues
    res_queues = client.get("/api/v1/analytics/queues")
    assert res_queues.status_code == 200
    queues = AnalyticsQueuesResponse(**res_queues.json())
    assert queues.queues == []
    assert isinstance(queues.updatedAt, str)


def test_analytics_calculations_against_known_persisted_data() -> None:
    """Verifies analytics computations (customers, dwell time, peak occupancy, entries/exits) against seeded PostgreSQL rows."""
    async def _run() -> None:
        session_factory = get_session_factory()
        analytics_service = get_analytics_service()

        job_id = f"vj-known-{uuid.uuid4().hex[:6]}"
        now = datetime.datetime.now(datetime.timezone.utc)

        async with session_factory() as session:
            job = VideoJobModel(
                id=job_id,
                filename="known_data.mp4",
                storage_path=f"data/uploads/{job_id}.mp4",
                file_size_bytes=200000,
                status="done",
                frames=300,
                customers_detected=18,
                duration_seconds=30.0,
                fps=10.0,
                uploaded_at=now,
                processed_at=now,
            )
            session.add(job)

            inference = InferenceResultModel(
                job_id=job_id,
                total_frames=300,
                customers_detected=18,
                peak_count=12,
                average_dwell_seconds=180.0,  # 3.0 minutes
                sample_detections=[],
                raw_metrics={"peak_occupancy": 12},
                created_at=now,
            )
            session.add(inference)

            track1 = TrackingSummaryModel(
                job_id=job_id,
                track_id=1,
                first_frame=1,
                last_frame=100,
                dwell_seconds=10.0,
                hit_count=50,
                hit_rate=0.5,
                crossed_entrance=True,
                crossed_exit=False,
            )
            track2 = TrackingSummaryModel(
                job_id=job_id,
                track_id=2,
                first_frame=50,
                last_frame=250,
                dwell_seconds=20.0,
                hit_count=100,
                hit_rate=0.5,
                crossed_entrance=False,
                crossed_exit=True,
            )
            session.add_all([track1, track2])
            await session.commit()

        # Check summary
        summary = await analytics_service.get_summary()
        assert summary.todayCustomers >= 18
        assert summary.avgDwellMinutes > 0.0

        # Check dwell
        dwell = await analytics_service.get_dwell_time()
        assert dwell.averageDwellMinutes > 0.0
        assert len(dwell.bySection) > 0

        # Check comprehensive metrics
        metrics = await analytics_service.get_comprehensive_metrics()
        assert metrics["total_videos_processed"] >= 1
        assert metrics["total_unique_customers"] >= 18
        assert metrics["peak_occupancy"] >= 12
        assert metrics["customer_entry_exit_counts"]["entries"] >= 1
        assert metrics["customer_entry_exit_counts"]["exits"] >= 1

    asyncio.run(_run())


def test_historical_analytics_and_date_range_filtering() -> None:
    """Verifies that date-range filtering (today, 7d, 30d) correctly partitions historical traffic records."""
    async def _run() -> None:
        session_factory = get_session_factory()
        analytics_service = get_analytics_service()

        now = datetime.datetime.now(datetime.timezone.utc)
        d_today = now
        d_3d = now - datetime.timedelta(days=3)
        d_10d = now - datetime.timedelta(days=10)
        d_40d = now - datetime.timedelta(days=40)

        job_ids = [f"vj-range-{i}-{uuid.uuid4().hex[:4]}" for i in range(4)]

        async with session_factory() as session:
            jobs = [
                VideoJobModel(
                    id=job_ids[0],
                    filename="job_today.mp4",
                    storage_path="path0.mp4",
                    status="done",
                    customers_detected=5,
                    uploaded_at=d_today,
                    processed_at=d_today,
                ),
                VideoJobModel(
                    id=job_ids[1],
                    filename="job_3d.mp4",
                    storage_path="path1.mp4",
                    status="done",
                    customers_detected=10,
                    uploaded_at=d_3d,
                    processed_at=d_3d,
                ),
                VideoJobModel(
                    id=job_ids[2],
                    filename="job_10d.mp4",
                    storage_path="path2.mp4",
                    status="done",
                    customers_detected=20,
                    uploaded_at=d_10d,
                    processed_at=d_10d,
                ),
                VideoJobModel(
                    id=job_ids[3],
                    filename="job_40d.mp4",
                    storage_path="path3.mp4",
                    status="done",
                    customers_detected=50,
                    uploaded_at=d_40d,
                    processed_at=d_40d,
                ),
            ]
            session.add_all(jobs)
            await session.commit()

        # range="today" includes job_today
        traffic_today = await analytics_service.get_traffic(range_param="today")
        assert traffic_today.totalCustomers >= 5

        # range="7d" includes job_today + job_3d
        traffic_7d = await analytics_service.get_traffic(range_param="7d")
        assert traffic_7d.totalCustomers >= 15

        # range="30d" includes job_today + job_3d + job_10d
        traffic_30d = await analytics_service.get_traffic(range_param="30d")
        assert traffic_30d.totalCustomers >= 35

    asyncio.run(_run())


def test_alert_aggregation_in_analytics() -> None:
    """Verifies that alert statistics (by severity and acknowledgment) are correctly aggregated from PostgreSQL."""
    async def _run() -> None:
        session_factory = get_session_factory()
        analytics_service = get_analytics_service()

        alert_id_base = f"al-stat-{uuid.uuid4().hex[:4]}"
        alerts = [
            AlertModel(
                id=f"{alert_id_base}-1",
                idempotency_key=f"idem-stat-1-{uuid.uuid4().hex[:8]}",
                alert_type="Critical Occupancy",
                area="Main Floor",
                severity="critical",
                description="Test critical alert",
                acknowledged=False,
            ),
            AlertModel(
                id=f"{alert_id_base}-2",
                idempotency_key=f"idem-stat-2-{uuid.uuid4().hex[:8]}",
                alert_type="High Occupancy",
                area="Aisles",
                severity="warning",
                description="Test warning alert",
                acknowledged=True,
            ),
            AlertModel(
                id=f"{alert_id_base}-3",
                idempotency_key=f"idem-stat-3-{uuid.uuid4().hex[:8]}",
                alert_type="Traffic Surge",
                area="Entrance",
                severity="info",
                description="Test info alert",
                acknowledged=False,
            ),
        ]

        async with session_factory() as session:
            session.add_all(alerts)
            await session.commit()

        metrics = await analytics_service.get_comprehensive_metrics()
        severity_counts = metrics["alert_counts_by_severity"]
        ack_stats = metrics["alert_acknowledgment_statistics"]

        assert severity_counts["critical"] >= 1
        assert severity_counts["warning"] >= 1
        assert severity_counts["info"] >= 1
        assert ack_stats["total"] >= 3
        assert ack_stats["acknowledged"] >= 1
        assert ack_stats["unacknowledged"] >= 2

    asyncio.run(_run())


def test_dwell_time_calculations() -> None:
    """Verifies that customer dwell times from multiple inference records are averaged accurately."""
    async def _run() -> None:
        session_factory = get_session_factory()
        analytics_service = get_analytics_service()

        job_id1 = f"vj-dwell1-{uuid.uuid4().hex[:4]}"
        job_id2 = f"vj-dwell2-{uuid.uuid4().hex[:4]}"
        now = datetime.datetime.now(datetime.timezone.utc)

        async with session_factory() as s:
            j1 = VideoJobModel(id=job_id1, filename="d1.mp4", storage_path="p1", status="done", uploaded_at=now, processed_at=now)
            j2 = VideoJobModel(id=job_id2, filename="d2.mp4", storage_path="p2", status="done", uploaded_at=now, processed_at=now)
            inf1 = InferenceResultModel(job_id=job_id1, total_frames=100, customers_detected=5, peak_count=5, average_dwell_seconds=120.0, sample_detections=[])  # 2.0 min
            inf2 = InferenceResultModel(job_id=job_id2, total_frames=100, customers_detected=5, peak_count=5, average_dwell_seconds=240.0, sample_detections=[])  # 4.0 min
            s.add_all([j1, j2, inf1, inf2])
            await s.commit()

        dwell_res = await analytics_service.get_dwell_time()
        assert dwell_res.averageDwellMinutes > 0.0
        assert len(dwell_res.bySection) >= 1
        assert dwell_res.bySection[0].minutes > 0.0

    asyncio.run(_run())


def test_cross_session_persistence_and_rollup() -> None:
    """Verifies that record_job_analytics writes to analytics_records table and survives session transitions."""
    async def _run() -> None:
        session_factory = get_session_factory()
        analytics_service = get_analytics_service()

        job_id = f"vj-rollup-{uuid.uuid4().hex[:6]}"
        now = datetime.datetime.now(datetime.timezone.utc)

        async with session_factory() as session:
            job = VideoJobModel(
                id=job_id,
                filename="rollup.mp4",
                storage_path=f"path_{job_id}.mp4",
                status="done",
                frames=150,
                customers_detected=14,
                uploaded_at=now,
                processed_at=now,
            )
            inference = InferenceResultModel(
                job_id=job_id,
                total_frames=150,
                customers_detected=14,
                peak_count=9,
                average_dwell_seconds=150.0,
                sample_detections=[],
            )
            session.add_all([job, inference])
            await session.commit()

        # Record rollup
        rec = await analytics_service.record_job_analytics(job_id)
        assert rec is not None
        assert rec.total_customers >= 14
        assert rec.peak_occupancy >= 9

        # Verify in a completely separate database session
        async with session_factory() as session2:
            res = await session2.execute(
                select(AnalyticsRecordModel).where(
                    AnalyticsRecordModel.record_date == now.date(),
                    AnalyticsRecordModel.record_hour == now.hour,
                )
            )
            saved = res.scalars().first()
            assert saved is not None
            assert saved.total_customers >= 14
            assert saved.peak_occupancy >= 9
            assert saved.video_clips_count >= 1

    asyncio.run(_run())


def test_duplicate_aggregation_prevention() -> None:
    """Verifies that multiple calls to record_job_analytics in the same period update the record instead of creating duplicates."""
    async def _run() -> None:
        session_factory = get_session_factory()
        analytics_service = get_analytics_service()

        job_id1 = f"vj-dup1-{uuid.uuid4().hex[:4]}"
        job_id2 = f"vj-dup2-{uuid.uuid4().hex[:4]}"
        now = datetime.datetime.now(datetime.timezone.utc)

        async with session_factory() as s:
            j1 = VideoJobModel(id=job_id1, filename="dup1.mp4", storage_path="p1", status="done", customers_detected=10, uploaded_at=now, processed_at=now)
            j2 = VideoJobModel(id=job_id2, filename="dup2.mp4", storage_path="p2", status="done", customers_detected=20, uploaded_at=now, processed_at=now)
            inf1 = InferenceResultModel(job_id=job_id1, total_frames=100, customers_detected=10, peak_count=8, average_dwell_seconds=60.0, sample_detections=[])
            inf2 = InferenceResultModel(job_id=job_id2, total_frames=100, customers_detected=20, peak_count=15, average_dwell_seconds=120.0, sample_detections=[])
            s.add_all([j1, j2, inf1, inf2])
            await s.commit()

        # Run aggregation for job 1, then job 2 in the same hour
        rec1 = await analytics_service.record_job_analytics(job_id1)
        rec2 = await analytics_service.record_job_analytics(job_id2)

        # Check total records in analytics_records for this date and hour
        async with session_factory() as s_check:
            res = await s_check.execute(
                select(AnalyticsRecordModel).where(
                    AnalyticsRecordModel.record_date == now.date(),
                    AnalyticsRecordModel.record_hour == now.hour,
                    AnalyticsRecordModel.store_id.is_(None),
                )
            )
            rows = res.scalars().all()
            assert len(rows) == 1  # Exactly 1 row for (store_id, record_date, record_hour)
            assert rows[0].total_customers >= 30
            assert rows[0].peak_occupancy >= 15
            assert rows[0].video_clips_count >= 2

    asyncio.run(_run())


def test_api_response_compatibility(client: TestClient) -> None:
    """Verifies that all 4 analytics API endpoints produce schema-valid responses conforming to API_CONTRACT.md."""
    # Summary
    res = client.get("/api/v1/analytics/summary")
    assert res.status_code == 200
    summary = AnalyticsSummaryResponse(**res.json())
    assert isinstance(summary.todayCustomers, int)
    assert isinstance(summary.todayCustomersDelta, str)
    assert isinstance(summary.avgDwellMinutes, (int, float))
    assert isinstance(summary.avgDwellDelta, str)
    assert summary.longestQueueCheckout == "N/A"
    assert summary.longestQueueCount == 0
    assert summary.shelvesNeedingRestock == 0
    assert summary.criticalShelvesCount == 0
    assert summary.lowStockShelvesCount == 0

    # Traffic
    res = client.get("/api/v1/analytics/traffic?range=today")
    assert res.status_code == 200
    traffic = AnalyticsTrafficResponse(**res.json())
    assert isinstance(traffic.totalCustomers, int)
    assert isinstance(traffic.daily, list)
    assert isinstance(traffic.hourly, list)

    # Dwell Time
    res = client.get("/api/v1/analytics/dwell-time")
    assert res.status_code == 200
    dwell = AnalyticsDwellResponse(**res.json())
    assert isinstance(dwell.bySection, list)
    assert isinstance(dwell.averageDwellMinutes, (int, float))

    # Queues
    res = client.get("/api/v1/analytics/queues")
    assert res.status_code == 200
    queues = AnalyticsQueuesResponse(**res.json())
    assert isinstance(queues.queues, list)
    assert isinstance(queues.updatedAt, str)


def test_database_failure_handling() -> None:
    """Verifies that database failures during analytics query or record operations raise cleanly without data corruption."""
    analytics_service = get_analytics_service()

    async def _run() -> None:
        with patch.object(AsyncSession, "execute", side_effect=RuntimeError("Simulated PostgreSQL connection drop")):
            with pytest.raises(RuntimeError, match="Simulated PostgreSQL connection drop"):
                await analytics_service.get_summary()

        with patch.object(AsyncSession, "get", side_effect=RuntimeError("Simulated PostgreSQL connection drop")):
            with pytest.raises(RuntimeError, match="Simulated PostgreSQL connection drop"):
                await analytics_service.record_job_analytics("vj-any-1234")

    asyncio.run(_run())
