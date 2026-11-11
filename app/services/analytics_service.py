import asyncio
import concurrent.futures
import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

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
    DwellPoint,
    HourlyPoint,
    QueuePoint,
    TrafficPoint,
)

logger = logging.getLogger("retailiq.analytics_service")


def _run_async(coro: Any) -> Any:
    """Helper to execute an async coroutine synchronously from any context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


class AnalyticsService:
    """Computes store analytics exclusively from verified PostgreSQL records.

    Zero fabricated numbers are returned. Empty states strictly conform to API_CONTRACT.md.
    """

    async def get_summary(
        self,
        store_id: Optional[uuid.UUID] = None,
        session: Optional[AsyncSession] = None,
    ) -> AnalyticsSummaryResponse:
        """Returns aggregate KPI metrics for the store overview dashboard."""
        async def _query(s: AsyncSession) -> AnalyticsSummaryResponse:
            now = datetime.datetime.now(datetime.timezone.utc)
            today_start = datetime.datetime.combine(now.date(), datetime.time.min, tzinfo=datetime.timezone.utc)

            # 1. Total customers and clips for today from completed VideoJob records
            stmt_today = (
                select(
                    func.coalesce(func.sum(VideoJobModel.customers_detected), 0).label("total_cust"),
                    func.count(VideoJobModel.id).label("total_clips"),
                )
                .where(VideoJobModel.status == "done")
                .where(func.coalesce(VideoJobModel.processed_at, VideoJobModel.uploaded_at) >= today_start)
            )
            if store_id is not None:
                stmt_today = stmt_today.where(VideoJobModel.store_id == store_id)

            res_today = await s.execute(stmt_today)
            row_today = res_today.first()
            today_customers = row_today.total_cust if row_today else 0
            today_clips = row_today.total_clips if row_today else 0

            # 2. Today's average dwell time from InferenceResult
            stmt_dwell = (
                select(
                    func.coalesce(func.avg(InferenceResultModel.average_dwell_seconds), 0.0).label("avg_dwell_sec")
                )
                .select_from(InferenceResultModel)
                .join(VideoJobModel, InferenceResultModel.job_id == VideoJobModel.id)
                .where(VideoJobModel.status == "done")
                .where(func.coalesce(VideoJobModel.processed_at, VideoJobModel.uploaded_at) >= today_start)
                .where(InferenceResultModel.average_dwell_seconds > 0)
            )
            if store_id is not None:
                stmt_dwell = stmt_dwell.where(VideoJobModel.store_id == store_id)

            res_dwell = await s.execute(stmt_dwell)
            avg_dwell_sec = float(res_dwell.scalar() or 0.0)
            avg_dwell_minutes = round(avg_dwell_sec / 60.0, 1)

            # If no clips completed today, return contract-valid empty state
            if today_clips == 0 and today_customers == 0:
                return AnalyticsSummaryResponse(
                    todayCustomers=0,
                    todayCustomersDelta="",
                    avgDwellMinutes=0.0,
                    avgDwellDelta="",
                    longestQueueCheckout="N/A",
                    longestQueueCount=0,
                    shelvesNeedingRestock=0,
                    criticalShelvesCount=0,
                    lowStockShelvesCount=0,
                )

            return AnalyticsSummaryResponse(
                todayCustomers=today_customers,
                todayCustomersDelta=f"{today_customers} detected from {today_clips} video clip(s)",
                avgDwellMinutes=avg_dwell_minutes,
                avgDwellDelta=f"{avg_dwell_minutes} min avg",
                longestQueueCheckout="N/A",
                longestQueueCount=0,
                shelvesNeedingRestock=0,
                criticalShelvesCount=0,
                lowStockShelvesCount=0,
            )

        if session is not None:
            return await _query(session)

        session_factory = get_session_factory()
        async with session_factory() as s:
            return await _query(s)

    def get_summary_sync(
        self,
        store_id: Optional[uuid.UUID] = None,
    ) -> AnalyticsSummaryResponse:
        """Synchronous wrapper for get_summary."""
        return _run_async(self.get_summary(store_id=store_id))

    async def get_traffic(
        self,
        range_param: Optional[str] = "7d",
        store_id: Optional[uuid.UUID] = None,
        session: Optional[AsyncSession] = None,
    ) -> AnalyticsTrafficResponse:
        """Retrieves daily and hourly customer traffic counts from persisted PostgreSQL video jobs."""
        async def _query(s: AsyncSession) -> AnalyticsTrafficResponse:
            now = datetime.datetime.now(datetime.timezone.utc)
            today_start = datetime.datetime.combine(now.date(), datetime.time.min, tzinfo=datetime.timezone.utc)

            range_clean = (range_param or "7d").lower().strip()
            if range_clean == "today":
                cutoff = today_start
            elif range_clean == "30d":
                cutoff = today_start - datetime.timedelta(days=30)
            else:  # default 7d
                cutoff = today_start - datetime.timedelta(days=7)

            stmt = (
                select(
                    func.coalesce(VideoJobModel.processed_at, VideoJobModel.uploaded_at).label("job_time"),
                    VideoJobModel.customers_detected,
                )
                .where(VideoJobModel.status == "done")
                .where(func.coalesce(VideoJobModel.processed_at, VideoJobModel.uploaded_at) >= cutoff)
                .order_by("job_time")
            )
            if store_id is not None:
                stmt = stmt.where(VideoJobModel.store_id == store_id)

            res = await s.execute(stmt)
            rows = res.all()

            if not rows:
                return AnalyticsTrafficResponse(
                    daily=[],
                    hourly=[],
                    totalCustomers=0,
                )

            daily_map: Dict[datetime.date, Tuple[str, int]] = {}
            hourly_map: Dict[str, int] = {}
            total_customers = 0

            for r in rows:
                dt: datetime.datetime = r.job_time
                if dt is None:
                    continue
                cust: int = r.customers_detected or 0
                total_customers += cust

                d = dt.date()
                day_name = dt.strftime("%a")
                if d not in daily_map:
                    daily_map[d] = (day_name, 0)
                daily_map[d] = (day_name, daily_map[d][1] + cust)

                h_str = dt.strftime("%H")
                hourly_map[h_str] = hourly_map.get(h_str, 0) + cust

            daily = [TrafficPoint(day=name, customers=c) for name, c in daily_map.values()]
            hourly = [HourlyPoint(hour=h, customers=c) for h, c in sorted(hourly_map.items())]

            return AnalyticsTrafficResponse(
                daily=daily,
                hourly=hourly,
                totalCustomers=total_customers,
            )

        if session is not None:
            return await _query(session)

        session_factory = get_session_factory()
        async with session_factory() as s:
            return await _query(s)

    def get_traffic_sync(
        self,
        range_param: Optional[str] = "7d",
        store_id: Optional[uuid.UUID] = None,
    ) -> AnalyticsTrafficResponse:
        """Synchronous wrapper for get_traffic."""
        return _run_async(self.get_traffic(range_param=range_param, store_id=store_id))

    async def get_dwell_time(
        self,
        store_id: Optional[uuid.UUID] = None,
        session: Optional[AsyncSession] = None,
    ) -> AnalyticsDwellResponse:
        """Retrieves customer dwell time per store section calculated from persisted inference records."""
        async def _query(s: AsyncSession) -> AnalyticsDwellResponse:
            stmt = (
                select(
                    func.coalesce(func.avg(InferenceResultModel.average_dwell_seconds), 0.0).label("avg_sec"),
                    func.count(InferenceResultModel.id).label("cnt"),
                )
                .select_from(InferenceResultModel)
                .join(VideoJobModel, InferenceResultModel.job_id == VideoJobModel.id)
                .where(VideoJobModel.status == "done")
                .where(InferenceResultModel.average_dwell_seconds > 0)
            )
            if store_id is not None:
                stmt = stmt.where(VideoJobModel.store_id == store_id)

            res = await s.execute(stmt)
            row = res.first()
            if not row or row.cnt == 0 or row.avg_sec <= 0:
                return AnalyticsDwellResponse(
                    bySection=[],
                    averageDwellMinutes=0.0,
                )

            avg_minutes = round(float(row.avg_sec) / 60.0, 1)
            by_section = [
                DwellPoint(section="Store Floor", minutes=avg_minutes),
            ]
            return AnalyticsDwellResponse(
                bySection=by_section,
                averageDwellMinutes=avg_minutes,
            )

        if session is not None:
            return await _query(session)

        session_factory = get_session_factory()
        async with session_factory() as s:
            return await _query(s)

    def get_dwell_time_sync(
        self,
        store_id: Optional[uuid.UUID] = None,
    ) -> AnalyticsDwellResponse:
        """Synchronous wrapper for get_dwell_time."""
        return _run_async(self.get_dwell_time(store_id=store_id))

    async def get_queues(self) -> AnalyticsQueuesResponse:
        """Retrieves active checkout queue status.

        Queue detection is not implemented in Stage 2. Returning contract-valid empty response.
        """
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return AnalyticsQueuesResponse(
            queues=[],
            updatedAt=now_iso,
        )

    def get_queues_sync(self) -> AnalyticsQueuesResponse:
        """Synchronous wrapper for get_queues."""
        return _run_async(self.get_queues())

    async def record_job_analytics(
        self,
        job_id: str,
        cv_data: Optional[Dict[str, Any]] = None,
        session: Optional[AsyncSession] = None,
    ) -> Optional[AnalyticsRecordModel]:
        """Persist and update hourly analytics rollup in analytics_records table for the given completed job."""
        async def _record(s: AsyncSession) -> Optional[AnalyticsRecordModel]:
            job = await s.get(VideoJobModel, job_id)
            if not job:
                return None

            job_time = job.processed_at or job.uploaded_at or datetime.datetime.now(datetime.timezone.utc)
            record_date = job_time.date()
            record_hour = job_time.hour
            store_id = job.store_id

            # Calculate hourly aggregates from completed jobs in this hour window
            start_hour = datetime.datetime.combine(record_date, datetime.time(hour=record_hour), tzinfo=datetime.timezone.utc)
            end_hour = start_hour + datetime.timedelta(hours=1)

            stmt_window = (
                select(
                    func.count(VideoJobModel.id).label("clip_count"),
                    func.coalesce(func.sum(VideoJobModel.customers_detected), 0).label("tot_cust"),
                    func.coalesce(func.max(InferenceResultModel.peak_count), 0).label("max_peak"),
                    func.coalesce(func.avg(InferenceResultModel.average_dwell_seconds), 0.0).label("avg_dwell"),
                )
                .select_from(VideoJobModel)
                .outerjoin(InferenceResultModel, VideoJobModel.id == InferenceResultModel.job_id)
                .where(VideoJobModel.status == "done")
                .where(func.coalesce(VideoJobModel.processed_at, VideoJobModel.uploaded_at) >= start_hour)
                .where(func.coalesce(VideoJobModel.processed_at, VideoJobModel.uploaded_at) < end_hour)
            )
            if store_id is not None:
                stmt_window = stmt_window.where(VideoJobModel.store_id == store_id)
            else:
                stmt_window = stmt_window.where(VideoJobModel.store_id.is_(None))

            res_window = await s.execute(stmt_window)
            row = res_window.first()

            clip_count = row.clip_count if row else 1
            total_customers = row.tot_cust if row else job.customers_detected
            peak_occ = row.max_peak if row else 0
            avg_dwell_sec = float(row.avg_dwell) if row else 0.0
            avg_dwell_m = round(avg_dwell_sec / 60.0, 1)

            # Check existing record for (store_id, record_date, record_hour)
            stmt_find = select(AnalyticsRecordModel).where(
                AnalyticsRecordModel.record_date == record_date,
                AnalyticsRecordModel.record_hour == record_hour,
            )
            if store_id is not None:
                stmt_find = stmt_find.where(AnalyticsRecordModel.store_id == store_id)
            else:
                stmt_find = stmt_find.where(AnalyticsRecordModel.store_id.is_(None))

            res_find = await s.execute(stmt_find)
            existing = res_find.scalars().first()

            now_utc = datetime.datetime.now(datetime.timezone.utc)
            if existing:
                existing.total_customers = total_customers
                existing.avg_dwell_minutes = avg_dwell_m
                existing.peak_occupancy = peak_occ
                existing.video_clips_count = clip_count
                existing.updated_at = now_utc
                target_record = existing
            else:
                new_record = AnalyticsRecordModel(
                    store_id=store_id,
                    record_date=record_date,
                    record_hour=record_hour,
                    total_customers=total_customers,
                    avg_dwell_minutes=avg_dwell_m,
                    peak_occupancy=peak_occ,
                    video_clips_count=clip_count,
                    updated_at=now_utc,
                )
                s.add(new_record)
                target_record = new_record

            return target_record

        if session is not None:
            rec = await _record(session)
            await session.commit()
            return rec

        session_factory = get_session_factory()
        async with session_factory() as s:
            async with s.begin():
                rec = await _record(s)
            return rec

    async def get_comprehensive_metrics(
        self,
        store_id: Optional[uuid.UUID] = None,
        session: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """Calculates all 10 Stage 4 Phase 3 metrics directly from persisted PostgreSQL records."""
        async def _calc(s: AsyncSession) -> Dict[str, Any]:
            # 1. Total videos processed
            stmt_vids = select(func.count(VideoJobModel.id)).where(VideoJobModel.status == "done")
            if store_id is not None:
                stmt_vids = stmt_vids.where(VideoJobModel.store_id == store_id)
            total_videos = (await s.execute(stmt_vids)).scalar() or 0

            # 2. Total unique customers detected
            stmt_cust = select(func.coalesce(func.sum(VideoJobModel.customers_detected), 0)).where(VideoJobModel.status == "done")
            if store_id is not None:
                stmt_cust = stmt_cust.where(VideoJobModel.store_id == store_id)
            total_customers = (await s.execute(stmt_cust)).scalar() or 0

            # 3. Customer traffic and visits
            traffic_data = await self.get_traffic(range_param="7d", store_id=store_id, session=s)

            # 4. Peak occupancy
            stmt_peak = (
                select(func.coalesce(func.max(InferenceResultModel.peak_count), 0))
                .select_from(InferenceResultModel)
                .join(VideoJobModel, InferenceResultModel.job_id == VideoJobModel.id)
                .where(VideoJobModel.status == "done")
            )
            if store_id is not None:
                stmt_peak = stmt_peak.where(VideoJobModel.store_id == store_id)
            peak_occupancy = (await s.execute(stmt_peak)).scalar() or 0

            # 5. Average occupancy where reliable data exists
            stmt_avg_occ = (
                select(func.coalesce(func.avg(InferenceResultModel.peak_count), 0.0))
                .select_from(InferenceResultModel)
                .join(VideoJobModel, InferenceResultModel.job_id == VideoJobModel.id)
                .where(VideoJobModel.status == "done")
            )
            if store_id is not None:
                stmt_avg_occ = stmt_avg_occ.where(VideoJobModel.store_id == store_id)
            avg_occupancy = round(float((await s.execute(stmt_avg_occ)).scalar() or 0.0), 1)

            # 6. Average dwell time
            stmt_dwell = (
                select(func.coalesce(func.avg(InferenceResultModel.average_dwell_seconds), 0.0))
                .select_from(InferenceResultModel)
                .join(VideoJobModel, InferenceResultModel.job_id == VideoJobModel.id)
                .where(VideoJobModel.status == "done")
                .where(InferenceResultModel.average_dwell_seconds > 0)
            )
            if store_id is not None:
                stmt_dwell = stmt_dwell.where(VideoJobModel.store_id == store_id)
            avg_dwell_sec = float((await s.execute(stmt_dwell)).scalar() or 0.0)
            avg_dwell_minutes = round(avg_dwell_sec / 60.0, 1)

            # 7. Customer entry and exit counts from tracking summaries
            stmt_entries = (
                select(func.count(TrackingSummaryModel.id))
                .join(VideoJobModel, TrackingSummaryModel.job_id == VideoJobModel.id)
                .where(TrackingSummaryModel.crossed_entrance.is_(True))
            )
            stmt_exits = (
                select(func.count(TrackingSummaryModel.id))
                .join(VideoJobModel, TrackingSummaryModel.job_id == VideoJobModel.id)
                .where(TrackingSummaryModel.crossed_exit.is_(True))
            )
            if store_id is not None:
                stmt_entries = stmt_entries.where(VideoJobModel.store_id == store_id)
                stmt_exits = stmt_exits.where(VideoJobModel.store_id == store_id)
            entries_count = (await s.execute(stmt_entries)).scalar() or 0
            exits_count = (await s.execute(stmt_exits)).scalar() or 0

            # 8. Traffic trends over time
            trends = {
                "daily": [p.model_dump() for p in traffic_data.daily],
                "hourly": [p.model_dump() for p in traffic_data.hourly],
                "total_customers": traffic_data.totalCustomers,
            }

            # 9. Alert counts by severity
            stmt_alerts = select(AlertModel.severity, func.count(AlertModel.id)).group_by(AlertModel.severity)
            if store_id is not None:
                stmt_alerts = stmt_alerts.where(AlertModel.store_id == store_id)
            alert_rows = (await s.execute(stmt_alerts)).all()
            alert_counts_by_severity = {"info": 0, "warning": 0, "critical": 0}
            for sev, count in alert_rows:
                if sev in alert_counts_by_severity:
                    alert_counts_by_severity[sev] = count

            # 10. Alert acknowledgment statistics
            stmt_total_alerts = select(func.count(AlertModel.id))
            stmt_ack_alerts = select(func.count(AlertModel.id)).where(AlertModel.acknowledged.is_(True))
            if store_id is not None:
                stmt_total_alerts = stmt_total_alerts.where(AlertModel.store_id == store_id)
                stmt_ack_alerts = stmt_ack_alerts.where(AlertModel.store_id == store_id)
            total_alerts = (await s.execute(stmt_total_alerts)).scalar() or 0
            ack_alerts = (await s.execute(stmt_ack_alerts)).scalar() or 0
            unack_alerts = total_alerts - ack_alerts

            return {
                "total_videos_processed": total_videos,
                "total_unique_customers": total_customers,
                "customer_traffic_and_visits": trends,
                "peak_occupancy": peak_occupancy,
                "average_occupancy": avg_occupancy,
                "average_dwell_minutes": avg_dwell_minutes,
                "customer_entry_exit_counts": {
                    "entries": entries_count,
                    "exits": exits_count,
                },
                "traffic_trends": trends,
                "alert_counts_by_severity": alert_counts_by_severity,
                "alert_acknowledgment_statistics": {
                    "total": total_alerts,
                    "acknowledged": ack_alerts,
                    "unacknowledged": unack_alerts,
                },
            }

        if session is not None:
            return await _calc(session)

        session_factory = get_session_factory()
        async with session_factory() as s:
            return await _calc(s)


_analytics_service: Optional[AnalyticsService] = None


def get_analytics_service() -> AnalyticsService:
    """Singleton getter for analytics service."""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service
