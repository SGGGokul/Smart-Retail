import uuid
import pytest
from fastapi.testclient import TestClient

from app.models.customer_journey import CustomerVisitModel, CustomerZoneEventModel
from app.db.session import get_session_factory
from app.services.cv_service import CustomerVisit, VisitEvent, VisitStatus


@pytest.mark.anyio
async def test_customer_journey_db_and_api(client: TestClient):
    session_factory = get_session_factory()

    # 1. Insert seed customer visits and events
    v1_id = f"vis-test-{uuid.uuid4().hex[:6]}"
    v2_id = f"vis-test-{uuid.uuid4().hex[:6]}"
    cust_id = f"CUST-999{uuid.uuid4().hex[:3]}"

    async with session_factory() as session:
        async with session.begin():
            visit1 = CustomerVisitModel(
                id=v1_id,
                customer_id=cust_id,
                store_id="store-104",
                camera_id="cam-front",
                entry_time=10.0,
                exit_time=55.0,
                duration_seconds=45.0,
                status="completed",
                zones_visited=["Entrance Area", "Produce Section", "Checkout Counters"],
                zone_dwell_times={"Entrance Area": 5.0, "Produce Section": 25.0, "Checkout Counters": 15.0},
                is_repeat_visit=False,
                visit_number=1,
            )
            visit2 = CustomerVisitModel(
                id=v2_id,
                customer_id=cust_id,
                store_id="store-104",
                camera_id="cam-front",
                entry_time=100.0,
                exit_time=None,
                duration_seconds=30.0,
                status="active",
                zones_visited=["Entrance Area", "Aisle 1 - Packaged Goods"],
                zone_dwell_times={"Entrance Area": 10.0, "Aisle 1 - Packaged Goods": 20.0},
                is_repeat_visit=True,
                visit_number=2,
            )
            session.add_all([visit1, visit2])

            ev1 = CustomerZoneEventModel(
                id=str(uuid.uuid4()),
                visit_id=v1_id,
                customer_id=cust_id,
                camera_id="cam-front",
                zone_id="zone-entrance",
                zone_name="Entrance Area",
                event_type="entrance_confirmed",
                timestamp=10.0,
                dwell_seconds=5.0,
            )
            ev2 = CustomerZoneEventModel(
                id=str(uuid.uuid4()),
                visit_id=v1_id,
                customer_id=cust_id,
                camera_id="cam-front",
                zone_id="zone-produce",
                zone_name="Produce Section",
                event_type="zone_enter",
                timestamp=15.0,
                dwell_seconds=25.0,
            )
            ev3 = CustomerZoneEventModel(
                id=str(uuid.uuid4()),
                visit_id=v1_id,
                customer_id=cust_id,
                camera_id="cam-front",
                zone_id=None,
                zone_name=None,
                event_type="store_exit_confirmed",
                timestamp=55.0,
                dwell_seconds=0.0,
            )
            session.add_all([ev1, ev2, ev3])

    # 2. Test GET /api/v1/customer-journey/visits
    res = client.get("/api/v1/customer-journey/visits")
    assert res.status_code == 200
    data = res.json()
    assert "visits" in data
    assert data["totalCount"] >= 2
    assert data["activeCount"] >= 1
    assert data["completedCount"] >= 1
    assert "RateLimit-Limit" in res.headers

    # Filter by customer ID
    res_filtered = client.get(f"/api/v1/customer-journey/visits?customer_id={cust_id}")
    assert res_filtered.status_code == 200
    filtered_data = res_filtered.json()
    assert filtered_data["totalCount"] == 2
    assert len(filtered_data["visits"]) == 2

    # Filter by status
    res_active = client.get(f"/api/v1/customer-journey/visits?customer_id={cust_id}&status=active")
    assert res_active.status_code == 200
    active_data = res_active.json()
    assert active_data["totalCount"] == 1
    assert active_data["visits"][0]["id"] == v2_id

    # 3. Test GET /api/v1/customer-journey/visits/{visit_id}
    res_detail = client.get(f"/api/v1/customer-journey/visits/{v1_id}")
    assert res_detail.status_code == 200
    detail_data = res_detail.json()
    assert detail_data["visit"]["id"] == v1_id
    assert detail_data["visit"]["status"] == "completed"
    assert len(detail_data["events"]) == 3
    assert detail_data["events"][0]["eventType"] == "entrance_confirmed"
    assert detail_data["events"][1]["eventType"] == "zone_enter"
    assert detail_data["events"][2]["eventType"] == "store_exit_confirmed"

    # Test 404 for missing visit
    res_missing = client.get("/api/v1/customer-journey/visits/nonexistent-visit-id")
    assert res_missing.status_code == 404

    # 4. Test GET /api/v1/customer-journey/customers/{customer_id}/history
    res_history = client.get(f"/api/v1/customer-journey/customers/{cust_id}/history")
    assert res_history.status_code == 200
    history_data = res_history.json()
    assert len(history_data) == 2
    assert history_data[0]["visitNumber"] == 1
    assert history_data[1]["visitNumber"] == 2
    assert history_data[1]["isRepeatVisit"] is True

    # 5. Test GET /api/v1/customer-journey/zones/analytics
    res_analytics = client.get("/api/v1/customer-journey/zones/analytics")
    assert res_analytics.status_code == 200
    analytics_data = res_analytics.json()
    assert analytics_data["totalVisits"] >= 2
    assert analytics_data["uniqueCustomers"] >= 1
    assert len(analytics_data["zoneDwellSummary"]) > 0

    # 6. Test GET /api/v1/customer-journey/cameras/{camera_id}/analytics
    res_cam = client.get("/api/v1/customer-journey/cameras/cam-front/analytics")
    assert res_cam.status_code == 200
    cam_data = res_cam.json()
    assert cam_data["cameraId"] == "cam-front"
    assert cam_data["totalVisits"] >= 2
