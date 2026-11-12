"""End-to-end timezone consistency tests for RetailIQ Backend (UTC storage -> Asia/Kolkata display)."""

import asyncio
import datetime
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.health import get_health
from app.api.shelves import _format_shelf_timestamps
from app.core.datetime_utils import (
    ensure_utc,
    format_store_time_hm,
    format_store_uploaded_label,
    get_store_timezone,
    store_day_bounds_utc,
    to_store_tz,
    to_utc_iso,
    utc_now,
)
from app.db.base import Base
from app.models.alert import Alert as AlertModel
from app.models.video import InferenceResult as InferenceResultModel
from app.models.video import VideoJob as VideoJobModel
from app.services.analytics_service import AnalyticsService
from app.services.identity_service import IdentityService
from app.services.rule_engine import RuleEngine
from app.services.video_service import VideoService


def test_datetime_utils_utc_and_ist_conversions() -> None:
    """Verify aware UTC helpers, naive-to-UTC normalization, and IST midnight boundaries."""
    now = utc_now()
    assert now.tzinfo == datetime.timezone.utc

    # Naive datetime is treated as UTC, never silently shifted twice
    naive_dt = datetime.datetime(2026, 11, 12, 4, 55, 15)
    assert ensure_utc(naive_dt) == datetime.datetime(2026, 11, 12, 4, 55, 15, tzinfo=datetime.timezone.utc)
    assert to_utc_iso(naive_dt) == "2026-11-12T04:55:15Z"

    # IST (+05:30) datetime normalizes back to exact UTC instant
    ist_tz = get_store_timezone("Asia/Kolkata")
    ist_dt = datetime.datetime(2026, 11, 12, 10, 25, 15, tzinfo=ist_tz)
    assert to_utc_iso(ist_dt) == "2026-11-12T04:55:15Z"

    # Formatting to Asia/Kolkata
    utc_dt = datetime.datetime(2026, 11, 11, 19, 0, 0, tzinfo=datetime.timezone.utc)
    ref_utc = datetime.datetime(2026, 11, 12, 6, 0, 0, tzinfo=datetime.timezone.utc)  # 11:30 IST Nov 12
    assert format_store_time_hm(utc_dt) == "00:30"
    assert format_store_uploaded_label(utc_dt, reference_utc=ref_utc) == "Today 00:30"

    # Store-local day bounds: 2026-11-12 00:00 IST == 2026-11-11 18:30 UTC
    start_utc, end_utc = store_day_bounds_utc("Asia/Kolkata", reference_utc=ref_utc)
    assert start_utc == datetime.datetime(2026, 11, 11, 18, 30, 0, tzinfo=datetime.timezone.utc)
    assert end_utc == datetime.datetime(2026, 11, 12, 18, 30, 0, tzinfo=datetime.timezone.utc)


def test_video_job_serialization_exposes_utc_iso_and_ist_label() -> None:
    """VideoJob serializer must return UTC ISO uploadedAt/processedAt and IST-converted uploaded label."""
    uploaded_utc = datetime.datetime(2026, 11, 12, 4, 55, 15, tzinfo=datetime.timezone.utc)
    processed_utc = datetime.datetime(2026, 11, 12, 5, 5, 30, tzinfo=datetime.timezone.utc)

    orm_job = VideoJobModel(
        id="vj-tz-01",
        filename="cam_ist.mp4",
        storage_path="data/uploads/cam_ist.mp4",
        status="done",
        frames=100,
        customers_detected=5,
        uploaded_at=uploaded_utc,
        processed_at=processed_utc,
    )

    with patch(
        "app.core.datetime_utils.utc_now",
        return_value=datetime.datetime(2026, 11, 12, 6, 0, 0, tzinfo=datetime.timezone.utc),
    ):
        schema = VideoService._orm_to_schema(orm_job)

    assert schema.uploadedAt == "2026-11-12T04:55:15Z"
    assert schema.processedAt == "2026-11-12T05:05:30Z"
    assert schema.uploaded == "Today 10:25"


def test_alert_serialization_converts_utc_created_at_to_ist() -> None:
    """Alert serializer must derive IST HH:MM from UTC created_at even if legacy time_str was UTC."""
    created_utc = datetime.datetime(2026, 11, 12, 4, 55, 15, tzinfo=datetime.timezone.utc)
    ack_utc = datetime.datetime(2026, 11, 12, 5, 10, 0, tzinfo=datetime.timezone.utc)
    alert_orm = AlertModel(
        id="al-tz-01",
        idempotency_key="key-tz-01",
        alert_type="High Store Occupancy",
        area="Main Floor",
        severity="warning",
        description="Threshold exceeded",
        acknowledged=True,
        time_str="04:55",  # Stale UTC string from pre-fix run
        created_at=created_utc,
        acknowledged_at=ack_utc,
    )

    item = RuleEngine._orm_to_schema(alert_orm)
    assert item.time == "10:25"
    assert item.createdAt == "2026-11-12T04:55:15Z"
    assert item.acknowledgedAt == "2026-11-12T05:10:00Z"


def test_analytics_summary_and_traffic_use_asia_kolkata_day_and_hour_buckets() -> None:
    """Analytics queries filter 'today' from 00:00 IST (18:30 UTC prev day) and bucket hours in IST."""
    class _SyncAsAsyncSession:
        def __init__(self, sync_session: Session) -> None:
            self._s = sync_session

        async def execute(self, stmt):  # type: ignore[no-untyped-def]
            return self._s.execute(stmt)

        async def scalar(self, stmt):  # type: ignore[no-untyped-def]
            return self._s.scalar(stmt)

    async def _run() -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            engine,
            tables=[VideoJobModel.__table__, InferenceResultModel.__table__],
        )
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)

        with session_factory() as sync_session:
            # Job 1: 2026-11-11 18:15 UTC == 2026-11-11 23:45 IST (Wed, previous IST day!)
            j_prev_ist = VideoJobModel(
                id="vj-prev-ist",
                filename="prev.mp4",
                storage_path="p1",
                status="done",
                customers_detected=7,
                uploaded_at=datetime.datetime(2026, 11, 11, 18, 15, 0, tzinfo=datetime.timezone.utc),
                processed_at=datetime.datetime(2026, 11, 11, 18, 15, 0, tzinfo=datetime.timezone.utc),
            )
            # Job 2: 2026-11-11 18:45 UTC == 2026-11-12 00:15 IST (Thu, TODAY in IST!)
            j_today_ist = VideoJobModel(
                id="vj-today-ist",
                filename="today.mp4",
                storage_path="p2",
                status="done",
                customers_detected=12,
                uploaded_at=datetime.datetime(2026, 11, 11, 18, 45, 0, tzinfo=datetime.timezone.utc),
                processed_at=datetime.datetime(2026, 11, 11, 18, 45, 0, tzinfo=datetime.timezone.utc),
            )
            inf = InferenceResultModel(
                job_id="vj-today-ist",
                total_frames=100,
                customers_detected=12,
                peak_count=6,
                average_dwell_seconds=120.0,
                sample_detections=[],
            )
            sync_session.add_all([j_prev_ist, j_today_ist, inf])
            sync_session.commit()

            session = _SyncAsAsyncSession(sync_session)
            svc = AnalyticsService()
            fixed_now = datetime.datetime(2026, 11, 12, 5, 0, 0, tzinfo=datetime.timezone.utc)  # 10:30 IST Thu Nov 12

            with patch("app.core.datetime_utils.utc_now", return_value=fixed_now):
                summary = await svc.get_summary(session=session)  # type: ignore[arg-type]
                traffic_today = await svc.get_traffic(range_param="today", session=session)  # type: ignore[arg-type]
                traffic_7d = await svc.get_traffic(range_param="7d", session=session)  # type: ignore[arg-type]
                queues = await svc.get_queues()

            # Summary "today" counts only IST-today job (12), excluding 23:45 IST yesterday (7)
            assert summary.todayCustomers == 12
            assert summary.avgDwellMinutes == 2.0

            # Traffic "today" buckets at 00 IST on Thu
            assert traffic_today.totalCustomers == 12
            assert [(p.day, p.customers) for p in traffic_today.daily] == [("Thu", 12)]
            assert [(p.hour, p.customers) for p in traffic_today.hourly] == [("00", 12)]

            # Traffic "7d" splits 23:45 IST (Wed) and 00:15 IST (Thu) accurately
            assert traffic_7d.totalCustomers == 19
            assert [(p.day, p.customers) for p in traffic_7d.daily] == [("Wed", 7), ("Thu", 12)]
            assert [(p.hour, p.customers) for p in traffic_7d.hourly] == [("00", 12), ("23", 7)]

            # Queues timestamp includes UTC Z
            assert queues.updatedAt.endswith("Z")

        engine.dispose()

    asyncio.run(_run())


def test_identity_service_defaults_to_asia_kolkata_and_rolls_over_at_ist_midnight() -> None:
    """IdentityService defaults to Asia/Kolkata and rolls over at 18:30 UTC (00:00 IST)."""
    svc = IdentityService()
    assert svc.default_timezone == "Asia/Kolkata"

    ts_before_ist_midnight = datetime.datetime(2026, 11, 11, 18, 25, 0, tzinfo=datetime.timezone.utc).timestamp()
    ts_after_ist_midnight = datetime.datetime(2026, 11, 11, 18, 35, 0, tzinfo=datetime.timezone.utc).timestamp()

    assert svc.get_store_local_date("store-104", timestamp=ts_before_ist_midnight) == "2026-11-11"
    assert svc.get_store_local_date("store-104", timestamp=ts_after_ist_midnight) == "2026-11-12"


def test_shelf_and_health_timestamps() -> None:
    """Health and shelf endpoints format UTC ISO-8601 and IST display labels cleanly."""
    health = get_health()
    assert health.timestamp.endswith("Z")
    parsed_health = datetime.datetime.fromisoformat(health.timestamp.replace("Z", "+00:00"))
    assert parsed_health.tzinfo == datetime.timezone.utc

    epoch_ts = datetime.datetime(2026, 11, 12, 4, 55, 15, tzinfo=datetime.timezone.utc).timestamp()
    label, iso = _format_shelf_timestamps(epoch_ts)
    assert label == "10:25"
    assert iso == "2026-11-12T04:55:15Z"

    assert _format_shelf_timestamps(12.5) == ("Just now", None)
    assert _format_shelf_timestamps(0.0) == ("Pending stream", None)
