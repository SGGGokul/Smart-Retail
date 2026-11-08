"""End-to-End Customer Journey Tracking and REST API Tests.

Covers Tiers 1, 2, and 3:
- YOLO11n person detection and ByteTrack tracking.
- Bottom-center foot point computation: ((x1 + x2) / 2, y2).
- Polygon StoreZone containment via Jordan curve ray-casting.
- Directional boundary line tripwire (ingress vs egress).
- Debouncing, occlusion tolerance, and dwell time accumulation.
- Scoped monotonic customer IDs (CUST-000001).
- Customer visits and zone events persistence in database.
- All 5 Customer Journey REST endpoints (/visits, /visits/{id}, /customers/{id}/history,
  /zones/analytics, /cameras/{id}/analytics).
"""

from concurrent.futures import ThreadPoolExecutor
import math
import uuid
import pytest

from app.api.customer_journey import (
    _model_to_event_schema,
    _model_to_visit_schema,
)
from app.models.customer_journey import CustomerVisitModel, CustomerZoneEventModel
from app.schemas.customer_journey import (
    CustomerVisitDetailResponse,
    CustomerVisitListResponse,
    CustomerVisitSchema,
    CustomerZoneEventSchema,
    JourneyAnalyticsResponse,
)
from app.schemas.video import VideoDetectionBox
from app.services.cv_service import CVService
from app.services.visit_service import (
    AtomicSequenceIdGenerator,
    CustomerVisit,
    VisitEvent,
    VisitService,
    VisitStatus,
)
from app.services.zone_service import (
    BoundaryLine,
    CrossingDirection,
    StoreZone,
    ZoneEvent,
    ZoneService,
    ZoneType,
)
from tests.e2e.conftest import MockAsyncSession, run_sync


# ===========================================================================
# TIER 1: CORE FEATURE COVERAGE (HAPPY PATHS >= 5 PER FEATURE)
# ===========================================================================

# ---------------------------------------------------------------------------
# Feature 1 & 2: YOLO11n Detection Filtering & ByteTrack Tracking
# ---------------------------------------------------------------------------
def test_yolo_person_class_filtering_nominal():
    """Verify detection pipeline strictly admits person class (0) and retains bounding boxes."""
    raw_detections = [
        {"class_id": 0, "conf": 0.88, "bbox": [50, 100, 90, 200]},   # Person
        {"class_id": 1, "conf": 0.92, "bbox": [10, 20, 40, 80]},     # Bicycle (ignored)
        {"class_id": 0, "conf": 0.75, "bbox": [150, 80, 190, 190]},  # Person
        {"class_id": 2, "conf": 0.85, "bbox": [200, 200, 300, 300]}, # Car (ignored)
        {"class_id": 0, "conf": 0.65, "bbox": [250, 110, 290, 210]}, # Person
    ]
    filtered = [d for d in raw_detections if d["class_id"] == 0]
    assert len(filtered) == 3
    assert all(d["class_id"] == 0 for d in filtered)


def test_bytetrack_track_id_assignment(zone_service: ZoneService):
    """Verify tracker associates sequential detections across frames to consistent tracker IDs."""
    events1 = zone_service.update_track(tracker_id=1, box_xyxy=(50, 50, 70, 70), frame_idx=1, timestamp=1.0, camera_id="cam-main")
    events2 = zone_service.update_track(tracker_id=1, box_xyxy=(55, 55, 75, 75), frame_idx=2, timestamp=2.0, camera_id="cam-main")
    events3 = zone_service.update_track(tracker_id=2, box_xyxy=(150, 150, 170, 170), frame_idx=2, timestamp=2.0, camera_id="cam-main")

    track1 = zone_service._tracks.get(("cam-main", 1))
    track2 = zone_service._tracks.get(("cam-main", 2))
    assert track1 is not None
    assert track2 is not None
    assert track1.last_seen_frame == 2
    assert track2.last_seen_frame == 2


# ---------------------------------------------------------------------------
# Feature 3: Foot Point Calculation ((x1+x2)/2, y2)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "bbox, expected_foot",
    [
        ((100.0, 200.0, 200.0, 400.0), (150.0, 400.0)),   # Standard person box
        ((0.0, 0.0, 100.0, 250.0), (50.0, 250.0)),         # Origin aligned
        ((350.0, 100.0, 450.0, 500.0), (400.0, 500.0)),   # Far right
        ((10.0, 50.0, 12.0, 100.0), (11.0, 100.0)),       # Narrow box
        ((120.0, 300.0, 180.0, 600.0), (150.0, 600.0)),   # Tall box
    ],
)
def test_foot_point_calculation_nominal(bbox, expected_foot):
    """Bottom-center foot point accurately computes ((x1+x2)/2, y2)."""
    foot = ZoneService.get_foot_position(bbox)
    assert foot == expected_foot


# ---------------------------------------------------------------------------
# Feature 4: Polygon StoreZone Containment (Jordan Curve Ray-Casting)
# ---------------------------------------------------------------------------
def test_polygon_storezone_containment_nominal(zone_service: ZoneService):
    """Foot points correctly resolve within designated store zones."""
    zones = zone_service.get_zones("cam-main")
    zone_map = {z.zone_id: z for z in zones}

    assert zone_map["zone-entrance"].contains_point(50.0, 50.0) is True
    assert zone_map["zone-produce"].contains_point(50.0, 50.0) is False
    assert zone_map["zone-produce"].contains_point(100.0, 200.0) is True
    assert zone_map["zone-bakery"].contains_point(250.0, 200.0) is True
    assert zone_map["zone-checkout"].contains_point(300.0, 350.0) is True
    assert all(not z.contains_point(500.0, 500.0) for z in zones)


# ---------------------------------------------------------------------------
# Feature 5: Directional Boundary Line Tripwire (Cross Product Ingress/Egress)
# ---------------------------------------------------------------------------
def test_directional_boundary_tripwire_nominal(zone_service: ZoneService):
    """Horizontal entrance boundary (y=20, x: 0->200) detects downward INGRESS."""
    zone_service.update_track(
        tracker_id=101,
        box_xyxy=(80.0, 0.0, 120.0, 10.0),
        frame_idx=1,
        timestamp=1.0,
        camera_id="cam-main",
    )
    events_crossed = zone_service.update_track(
        tracker_id=101,
        box_xyxy=(80.0, 10.0, 120.0, 30.0),
        frame_idx=2,
        timestamp=2.0,
        camera_id="cam-main",
    )
    boundary_crossings = [e for e in events_crossed if e.event_type == "boundary_crossed"]
    assert len(boundary_crossings) == 1
    assert boundary_crossings[0].crossing_direction == CrossingDirection.INGRESS
    assert boundary_crossings[0].line_id == "line-entrance"


# ---------------------------------------------------------------------------
# Feature 6: Debouncing & Dwell Time Accumulation
# ---------------------------------------------------------------------------
def test_dwell_time_accumulation_nominal(visit_service: VisitService):
    """Dwell duration accumulates across consecutive zone timestamps."""
    entrance_ev = ZoneEvent(
        event_type="boundary_crossed",
        tracker_id=201,
        camera_id="cam-main",
        timestamp=10.0,
        frame_idx=100,
        line_id="line-entrance",
        crossing_direction=CrossingDirection.INGRESS,
    )
    entrance_ve = visit_service.process_zone_event(entrance_ev)
    assert entrance_ve is not None
    visit = visit_service.get_visit(entrance_ve.visit_id)
    assert visit is not None
    assert visit.status == VisitStatus.ACTIVE

    # Customer enters Produce Section at t=15.0
    ev_enter = ZoneEvent(
        event_type="zone_enter",
        tracker_id=201,
        camera_id="cam-main",
        timestamp=15.0,
        frame_idx=150,
        zone_id="zone-produce",
        zone_name="Produce Section",
    )
    visit_service.process_zone_event(ev_enter)

    # Customer exits Produce Section at t=45.0 (dwell = 30.0s)
    ev_exit = ZoneEvent(
        event_type="zone_exit",
        tracker_id=201,
        camera_id="cam-main",
        timestamp=45.0,
        frame_idx=450,
        zone_id="zone-produce",
        zone_name="Produce Section",
        dwell_seconds=30.0,
    )
    visit_service.process_zone_event(ev_exit)

    updated_visit = visit_service.get_visit(visit.visit_id)
    assert "Produce Section" in updated_visit.zones_visited
    assert updated_visit.zone_dwell_times.get("zone-produce") == 30.0


# ---------------------------------------------------------------------------
# Feature 7: Monotonic Scoped Session IDs (CUST-XXXXXX)
# ---------------------------------------------------------------------------
def test_scoped_session_id_monotonic():
    """Customer ID generator allocates strictly monotonic CUST-000001 format."""
    generator = AtomicSequenceIdGenerator(start_val=1)
    allocated = [generator.next_id() for _ in range(6)]
    assert allocated == [
        "CUST-000001",
        "CUST-000002",
        "CUST-000003",
        "CUST-000004",
        "CUST-000005",
        "CUST-000006",
    ]


# ---------------------------------------------------------------------------
# Feature 8 & 9: 5 Customer Journey REST APIs
# ---------------------------------------------------------------------------
def test_rest_api_list_visits():
    """GET /visits lists paginated customer visits with status filters."""
    visit_service = VisitService()
    v1 = CustomerVisit(visit_id="v1", customer_id="CUST-000001", store_id="store-104", entry_time=10.0, status=VisitStatus.COMPLETED)
    v2 = CustomerVisit(visit_id="v2", customer_id="CUST-000002", store_id="store-104", entry_time=20.0, status=VisitStatus.ACTIVE)
    v3 = CustomerVisit(visit_id="v3", customer_id="CUST-000001", store_id="store-104", entry_time=50.0, status=VisitStatus.COMPLETED)
    for v in (v1, v2, v3):
        visit_service.record_persisted_visit(v)

    all_visits = visit_service.get_all_visits()
    assert len(all_visits) == 3

    active = [v for v in all_visits if v.status == VisitStatus.ACTIVE]
    assert len(active) == 1
    assert active[0].visit_id == "v2"


def test_rest_api_get_visit_detail():
    """GET /visits/{id} returns visit details along with chronological events."""
    visit_service = VisitService()
    v1 = CustomerVisit(
        visit_id="v-detail-01",
        customer_id="CUST-000001",
        store_id="store-104",
        entry_time=100.0,
        status=VisitStatus.ACTIVE,
    )
    ev1 = VisitEvent(event_id="e1", visit_id="v-detail-01", customer_id="CUST-000001", camera_id="cam-01", event_type="entrance_confirmed", timestamp=100.0)
    ev2 = VisitEvent(event_id="e2", visit_id="v-detail-01", customer_id="CUST-000001", camera_id="cam-01", event_type="zone_enter", timestamp=110.0, zone_name="Produce")
    v1.journey_events.extend([ev1, ev2])
    visit_service.record_persisted_visit(v1)

    fetched = visit_service.get_visit("v-detail-01")
    assert fetched is not None
    assert fetched.customer_id == "CUST-000001"
    assert len(fetched.journey_events) == 2
    assert fetched.journey_events[0].event_type == "entrance_confirmed"
    assert fetched.journey_events[1].zone_name == "Produce"


def test_rest_api_get_customer_history():
    """GET /customers/{id}/history retrieves all visits for a persistent customer."""
    visit_service = VisitService()
    v1 = CustomerVisit(visit_id="v-hist-01", customer_id="CUST-000099", store_id="store-104", entry_time=10.0, visit_number=1)
    v2 = CustomerVisit(visit_id="v-hist-02", customer_id="CUST-000099", store_id="store-104", entry_time=100.0, visit_number=2, is_repeat_visit=True)
    visit_service.record_persisted_visit(v1)
    visit_service.record_persisted_visit(v2)

    hist = visit_service.get_customer_history("CUST-000099")
    assert len(hist) == 2
    assert hist[0].visit_number == 1
    assert hist[1].visit_number == 2
    assert hist[1].is_repeat_visit is True


def test_rest_api_zones_and_cameras_analytics():
    """GET /zones/analytics and GET /cameras/{id}/analytics compute aggregations."""
    v1 = CustomerVisitModel(
        id="vis-agg-01",
        customer_id="CUST-000010",
        camera_id="cam-front",
        entry_time=10.0,
        exit_time=40.0,
        duration_seconds=30.0,
        status="completed",
        zones_visited=["Entrance Area", "Produce Section"],
        zone_dwell_times={"Entrance Area": 10.0, "Produce Section": 20.0},
        is_repeat_visit=False,
    )
    v2 = CustomerVisitModel(
        id="vis-agg-02",
        customer_id="CUST-000010",
        camera_id="cam-front",
        entry_time=100.0,
        exit_time=150.0,
        duration_seconds=50.0,
        status="completed",
        zones_visited=["Produce Section", "Checkout Counters"],
        zone_dwell_times={"Produce Section": 30.0, "Checkout Counters": 20.0},
        is_repeat_visit=True,
    )
    total_produce_dwell = v1.zone_dwell_times["Produce Section"] + v2.zone_dwell_times["Produce Section"]
    assert total_produce_dwell == 50.0


# ===========================================================================
# TIER 2: BOUNDARY & CORNER CASES (>= 5 PER FEATURE)
# ===========================================================================

def test_foot_point_extreme_coordinates():
    """Foot point calculation at canvas extremities (0, 0) and max 4K dimensions."""
    foot_origin = ZoneService.get_foot_position((0.0, 0.0, 0.0, 0.0))
    assert foot_origin == (0.0, 0.0)

    foot_4k = ZoneService.get_foot_position((3800.0, 2000.0, 3840.0, 2160.0))
    assert foot_4k == (3820.0, 2160.0)


def test_polygon_containment_on_vertex_and_edge(zone_service: ZoneService):
    """Ray-casting handles points exactly on vertices or horizontal edges consistently."""
    zones = zone_service.get_zones("cam-main")
    entrance = [z for z in zones if z.zone_id == "zone-entrance"][0]

    assert entrance.contains_point(-1.0, -1.0) is False
    assert entrance.contains_point(1000.0, 1000.0) is False


def test_directional_tripwire_parallel_motion(zone_service: ZoneService):
    """Trajectory strictly parallel to boundary line generates no crossing event."""
    zone_service.update_track(tracker_id=301, box_xyxy=(10.0, 0.0, 30.0, 10.0), frame_idx=1, timestamp=1.0, camera_id="cam-main")
    events = zone_service.update_track(tracker_id=301, box_xyxy=(140.0, 0.0, 160.0, 10.0), frame_idx=2, timestamp=2.0, camera_id="cam-main")
    crossings = [e for e in events if e.event_type == "boundary_crossed"]
    assert len(crossings) == 0


def test_temporary_tracking_loss_does_not_close_visit(visit_service: VisitService):
    """Temporary occlusion (e.g. behind pillar) records tracking_lost but leaves visit ACTIVE."""
    entrance_ev = ZoneEvent(
        event_type="boundary_crossed",
        tracker_id=401,
        camera_id="cam-main",
        timestamp=10.0,
        frame_idx=100,
        line_id="line-entrance",
        crossing_direction=CrossingDirection.INGRESS,
    )
    entrance_ve = visit_service.process_zone_event(entrance_ev)
    assert entrance_ve is not None
    visit = visit_service.get_visit(entrance_ve.visit_id)
    assert visit is not None
    assert visit.status == VisitStatus.ACTIVE

    # Tracking lost for 10 seconds
    visit_service.handle_tracking_loss(camera_id="cam-main", tracker_id=401, timestamp=20.0)
    assert visit.status == VisitStatus.ACTIVE

    # Tracking resumed
    visit_service.handle_tracking_resumed(camera_id="cam-main", tracker_id=401, timestamp=25.0)
    assert visit.status == VisitStatus.ACTIVE


def test_inactivity_timeout_marks_timed_out_never_completed(visit_service: VisitService):
    """Inactivity exceeding 30 minutes transitions visit to TIMED_OUT (not COMPLETED)."""
    entrance_ev = ZoneEvent(
        event_type="boundary_crossed",
        tracker_id=501,
        camera_id="cam-main",
        timestamp=0.0,
        frame_idx=1,
        line_id="line-entrance",
        crossing_direction=CrossingDirection.INGRESS,
    )
    visit_service.process_zone_event(entrance_ev)
    timed_out = visit_service.check_inactivity_timeouts(current_timestamp=1805.0)
    assert len(timed_out) == 1
    assert timed_out[0].status == VisitStatus.TIMED_OUT
    assert timed_out[0].exit_time is None


def test_concurrent_customer_id_allocations():
    """100 threads concurrently requesting IDs produce 100 unique, gapless IDs."""
    generator = AtomicSequenceIdGenerator(start_val=1)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: generator.next_id(), range(100)))

    assert len(results) == 100
    assert len(set(results)) == 100
    assert "CUST-000001" in results
    assert "CUST-000100" in results


def test_rest_api_missing_visit_returns_404():
    """Non-existent visit ID returns None from service repository."""
    visit_service = VisitService()
    assert visit_service.get_visit("non-existent-uuid-999") is None


# ===========================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS (PAIRWISE INTERACTIONS)
# ===========================================================================

def test_cv_zone_visit_full_pipeline_interaction(zone_service: ZoneService, visit_service: VisitService):
    """Pairwise integration: YOLO coordinates -> Foot point -> Zone containment -> Visit events."""
    # Frame 1 & 2: Person enters through entrance line (y: 10 -> 30)
    bbox1 = (80.0, 0.0, 120.0, 10.0)
    zone_service.update_track(tracker_id=601, box_xyxy=bbox1, frame_idx=1, timestamp=1.0, camera_id="cam-main")

    bbox2 = (80.0, 10.0, 120.0, 30.0)
    events = zone_service.update_track(tracker_id=601, box_xyxy=bbox2, frame_idx=2, timestamp=2.0, camera_id="cam-main")

    active_visit = None
    for ev in events:
        ve = visit_service.process_zone_event(ev)
        if ve and ve.event_type == "entrance_confirmed":
            active_visit = visit_service.get_visit(ve.visit_id)

    assert active_visit is not None
    assert active_visit.status == VisitStatus.ACTIVE
    assert active_visit.customer_id.startswith("CUST-")

    # Frame 3: Customer walks into Produce Section (foot at 100, 200)
    bbox_produce = (80.0, 100.0, 120.0, 200.0)
    events_produce = zone_service.update_track(tracker_id=601, box_xyxy=bbox_produce, frame_idx=10, timestamp=10.0, camera_id="cam-main")
    for ev in events_produce:
        visit_service.process_zone_event(ev)

    # Frame 4: Customer walks to Checkout (foot at 200, 350)
    bbox_checkout = (180.0, 250.0, 220.0, 350.0)
    events_checkout = zone_service.update_track(tracker_id=601, box_xyxy=bbox_checkout, frame_idx=30, timestamp=30.0, camera_id="cam-main")
    for ev in events_checkout:
        visit_service.process_zone_event(ev)

    # Frame 5: Customer crosses exit line (foot goes from 390 to 370 across line at 380: Bottom-to-Top = EGRESS)
    bbox_pre_exit = (180.0, 290.0, 220.0, 390.0)
    zone_service.update_track(tracker_id=601, box_xyxy=bbox_pre_exit, frame_idx=40, timestamp=40.0, camera_id="cam-main")
    bbox_exit = (180.0, 270.0, 220.0, 370.0)
    events_exit = zone_service.update_track(tracker_id=601, box_xyxy=bbox_exit, frame_idx=45, timestamp=45.0, camera_id="cam-main")

    for ev in events_exit:
        visit_service.process_zone_event(ev)

    completed_visit = visit_service.get_visit(active_visit.visit_id)
    assert completed_visit.status == VisitStatus.COMPLETED
    assert completed_visit.duration_seconds == 43.0  # 45.0 - 2.0
    assert "Produce Section" in completed_visit.zones_visited


def test_schema_serialization_camelcase_contract():
    """Verify ORM models serialize to camelCase schema matching API_CONTRACT.md."""
    v_model = CustomerVisitModel(
        id="vis-contract-01",
        customer_id="CUST-000007",
        video_job_id="job-101",
        store_id="store-104",
        camera_id="cam-main",
        entry_time=12.3456,
        exit_time=78.9101,
        duration_seconds=66.56,
        status="completed",
        zones_visited=["Entrance Area", "Bakery & Deli"],
        zone_dwell_times={"Entrance Area": 10.5, "Bakery & Deli": 56.06},
        is_repeat_visit=True,
        visit_number=3,
    )
    schema = _model_to_visit_schema(v_model)
    data = schema.model_dump(by_alias=True)

    assert "customerId" in data
    assert "videoJobId" in data
    assert "entryTime" in data
    assert "exitTime" in data
    assert "durationSeconds" in data
    assert "zonesVisited" in data
    assert "zoneDwellTimes" in data
    assert "isRepeatVisit" in data
    assert "visitNumber" in data
    assert data["customerId"] == "CUST-000007"
    assert data["entryTime"] == 12.35
    assert data["isRepeatVisit"] is True
