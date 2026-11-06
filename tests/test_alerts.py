from fastapi.testclient import TestClient
from app.schemas.alerts import AlertsResponse
from app.services.rule_engine import get_rule_engine


def test_alerts_list_schema(client: TestClient) -> None:
    """GET /api/v1/alerts must conform to AlertsResponse schema."""
    response = client.get("/api/v1/alerts")
    assert response.status_code == 200
    data = response.json()
    validated = AlertsResponse(**data)
    assert isinstance(validated.alerts, list)
    assert isinstance(validated.totalCount, int)
    assert isinstance(validated.unacknowledgedCount, int)


def test_alert_rule_trigger_and_patch(client: TestClient) -> None:
    """RuleEngine alerts can be retrieved and patched via PATCH /api/v1/alerts/{id}."""
    rule_engine = get_rule_engine()
    # Trigger rule via verified CV data
    rule_engine.evaluate_cv_results({
        "peak_occupancy": 28,  # Triggers critical occupancy alert
        "average_dwell_seconds": 150.0,  # Triggers dwell alert
        "entries": 5,
        "unique_customers": 10,
    })

    list_res = client.get("/api/v1/alerts?severity=critical")
    assert list_res.status_code == 200
    alerts = list_res.json()["alerts"]
    assert len(alerts) > 0
    target_alert = alerts[0]
    alert_id = target_alert["id"]
    assert target_alert["severity"] == "critical"
    assert target_alert["acknowledged"] is False

    # Patch alert acknowledgment
    patch_res = client.patch(
        f"/api/v1/alerts/{alert_id}",
        json={"acknowledged": True, "notes": "Security notified"},
    )
    assert patch_res.status_code == 200
    patched_data = patch_res.json()
    assert patched_data["id"] == alert_id
    assert patched_data["acknowledged"] is True


def test_alert_not_found(client: TestClient) -> None:
    """PATCH /api/v1/alerts/{id} returns 404 for nonexistent alert."""
    response = client.patch(
        "/api/v1/alerts/al-nonexistent",
        json={"acknowledged": True},
    )
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "RESOURCE_NOT_FOUND"
