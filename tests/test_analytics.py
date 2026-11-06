from fastapi.testclient import TestClient
from app.schemas.analytics import (
    AnalyticsDwellResponse,
    AnalyticsQueuesResponse,
    AnalyticsSummaryResponse,
    AnalyticsTrafficResponse,
)


def test_analytics_summary_schema(client: TestClient) -> None:
    """GET /api/v1/analytics/summary must strictly match contract schema."""
    response = client.get("/api/v1/analytics/summary")
    assert response.status_code == 200
    data = response.json()
    validated = AnalyticsSummaryResponse(**data)
    assert isinstance(validated.todayCustomers, int)
    assert isinstance(validated.avgDwellMinutes, (int, float))
    assert isinstance(validated.longestQueueCheckout, str)
    assert validated.longestQueueCount == 0
    assert validated.shelvesNeedingRestock == 0
    assert validated.criticalShelvesCount == 0


def test_analytics_traffic_schema(client: TestClient) -> None:
    """GET /api/v1/analytics/traffic must return daily, hourly, and totalCustomers."""
    response = client.get("/api/v1/analytics/traffic?range=7d")
    assert response.status_code == 200
    data = response.json()
    validated = AnalyticsTrafficResponse(**data)
    assert isinstance(validated.totalCustomers, int)
    assert isinstance(validated.daily, list)
    assert isinstance(validated.hourly, list)


def test_analytics_dwell_schema(client: TestClient) -> None:
    """GET /api/v1/analytics/dwell-time must return bySection and averageDwellMinutes."""
    response = client.get("/api/v1/analytics/dwell-time")
    assert response.status_code == 200
    data = response.json()
    validated = AnalyticsDwellResponse(**data)
    assert isinstance(validated.bySection, list)
    assert isinstance(validated.averageDwellMinutes, (int, float))


def test_analytics_queues_schema(client: TestClient) -> None:
    """GET /api/v1/analytics/queues must return valid queues list and updatedAt."""
    response = client.get("/api/v1/analytics/queues")
    assert response.status_code == 200
    data = response.json()
    validated = AnalyticsQueuesResponse(**data)
    assert isinstance(validated.queues, list)
    assert isinstance(validated.updatedAt, str)
