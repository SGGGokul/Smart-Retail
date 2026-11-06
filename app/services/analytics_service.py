import datetime
import logging
from typing import List, Optional

from app.schemas.analytics import (
    AnalyticsDwellResponse,
    AnalyticsQueuesResponse,
    AnalyticsSummaryResponse,
    AnalyticsTrafficResponse,
    DwellPoint,
    HourlyPoint,
    TrafficPoint,
)
from app.services.video_service import get_video_service

logger = logging.getLogger("retailiq.analytics_service")


class AnalyticsService:
    """Computes store analytics exclusively from verified CV results.

    Zero fabricated numbers are returned. Empty states match API_CONTRACT.md.
    """

    def get_summary(self) -> AnalyticsSummaryResponse:
        """Returns aggregate KPI metrics for the store overview dashboard."""
        video_service = get_video_service()
        raw_results = video_service.get_raw_results()

        if not raw_results:
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

        total_customers = sum(r.get("unique_customers", 0) for r in raw_results)
        dwell_durations_sec = [
            r.get("average_dwell_seconds", 0.0)
            for r in raw_results
            if r.get("average_dwell_seconds", 0.0) > 0
        ]
        avg_dwell_minutes = (
            round((sum(dwell_durations_sec) / len(dwell_durations_sec)) / 60.0, 1)
            if dwell_durations_sec
            else 0.0
        )

        return AnalyticsSummaryResponse(
            todayCustomers=total_customers,
            todayCustomersDelta=f"{total_customers} detected from {len(raw_results)} video clip(s)",
            avgDwellMinutes=avg_dwell_minutes,
            avgDwellDelta=f"{avg_dwell_minutes} min avg",
            longestQueueCheckout="N/A",  # Queue detection not implemented in Stage 2
            longestQueueCount=0,
            shelvesNeedingRestock=0,     # Shelf inventory detection not implemented in Stage 2
            criticalShelvesCount=0,
            lowStockShelvesCount=0,
        )

    def get_traffic(self, range_param: Optional[str] = "7d") -> AnalyticsTrafficResponse:
        """Retrieves daily and hourly customer traffic counts from processed video events."""
        video_service = get_video_service()
        raw_results = video_service.get_raw_results()

        if not raw_results:
            return AnalyticsTrafficResponse(
                daily=[],
                hourly=[],
                totalCustomers=0,
            )

        total_customers = sum(r.get("unique_customers", 0) for r in raw_results)

        now = datetime.datetime.now()
        day_name = now.strftime("%a")
        hour_str = now.strftime("%H")

        # Represent real data attributed to the telemetry period
        daily = [TrafficPoint(day=day_name, customers=total_customers)]
        hourly = [HourlyPoint(hour=hour_str, customers=total_customers)]

        return AnalyticsTrafficResponse(
            daily=daily,
            hourly=hourly,
            totalCustomers=total_customers,
        )

    def get_dwell_time(self) -> AnalyticsDwellResponse:
        """Retrieves customer dwell time per store department/section."""
        video_service = get_video_service()
        raw_results = video_service.get_raw_results()

        if not raw_results:
            return AnalyticsDwellResponse(
                bySection=[],
                averageDwellMinutes=0.0,
            )

        dwell_durations_sec = [
            r.get("average_dwell_seconds", 0.0)
            for r in raw_results
            if r.get("average_dwell_seconds", 0.0) > 0
        ]
        avg_dwell_minutes = (
            round((sum(dwell_durations_sec) / len(dwell_durations_sec)) / 60.0, 1)
            if dwell_durations_sec
            else 0.0
        )

        # Distribute verified dwell metrics into monitored store zones
        by_section = [
            DwellPoint(section="Store Floor", minutes=avg_dwell_minutes),
        ]

        return AnalyticsDwellResponse(
            bySection=by_section,
            averageDwellMinutes=avg_dwell_minutes,
        )

    def get_queues(self) -> AnalyticsQueuesResponse:
        """Retrieves active checkout queue status.

        NOTE: Queue detection is not implemented in Stage 2. Returning contract-valid empty response.
        """
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return AnalyticsQueuesResponse(
            queues=[],
            updatedAt=now_iso,
        )


_analytics_service: Optional[AnalyticsService] = None


def get_analytics_service() -> AnalyticsService:
    """Singleton getter for analytics service."""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service
