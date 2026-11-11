import pytest
from app.services.zone_service import (
    BoundaryLine,
    CrossingDirection,
    StoreZone,
    ZoneEvent,
    ZoneService,
    ZoneType,
)


@pytest.fixture
def zone_service() -> ZoneService:
    service = ZoneService(max_missed_frames=10, min_zone_dwell_seconds=0.2)
    return service


# ---------------------------------------------------------------------------
# 1. Polygon Geometry & Point-in-Polygon Tests
# ---------------------------------------------------------------------------
def test_convex_polygon_containment():
    """Convex rectangular polygon zone correctly identifies interior vs exterior."""
    rect_zone = StoreZone(
        zone_id="zone-produce",
        name="Produce",
        zone_type=ZoneType.DEPARTMENT,
        polygon=[(100.0, 100.0), (300.0, 100.0), (300.0, 300.0), (100.0, 300.0)],
    )

    # Interior point
    assert rect_zone.contains_point(200.0, 200.0) is True
    # Exterior points
    assert rect_zone.contains_point(50.0, 200.0) is False   # Left
    assert rect_zone.contains_point(350.0, 200.0) is False  # Right
    assert rect_zone.contains_point(200.0, 50.0) is False   # Above
    assert rect_zone.contains_point(200.0, 350.0) is False  # Below


def test_concave_l_shaped_polygon():
    """Non-convex (L-shaped) zone correctly identifies interior vs concavity."""
    l_zone = StoreZone(
        zone_id="zone-aisle1",
        name="Aisle 1",
        zone_type=ZoneType.AISLE,
        polygon=[
            (0.0, 0.0),
            (200.0, 0.0),
            (200.0, 100.0),
            (100.0, 100.0),
            (100.0, 200.0),
            (0.0, 200.0),
        ],
    )

    # Point in upper arm of L
    assert l_zone.contains_point(150.0, 50.0) is True
    # Point in lower arm of L
    assert l_zone.contains_point(50.0, 150.0) is True
    # Point in the 'cutout' concavity (150, 150) -> inside bounding box but outside polygon!
    assert l_zone.contains_point(150.0, 150.0) is False


def test_polygon_validation_requires_at_least_three_vertices():
    with pytest.raises(ValueError, match="at least 3 polygon vertices"):
        StoreZone(
            zone_id="invalid",
            name="Degenerate",
            zone_type=ZoneType.GENERAL,
            polygon=[(0.0, 0.0), (10.0, 10.0)],
        )


# ---------------------------------------------------------------------------
# 2. Boundary Tripwire Line Crossing Tests
# ---------------------------------------------------------------------------
def test_directional_boundary_line_crossing():
    """Horizontal boundary line distinguishes between Ingress and Egress movement."""
    # Line from (100, 200) to (300, 200)
    boundary = BoundaryLine(
        line_id="line-entrance",
        name="Store Main Entrance",
        p1=(100.0, 200.0),
        p2=(300.0, 200.0),
    )

    # Top-to-Bottom trajectory crossing line
    # From (200, 150) to (200, 250)
    crossed, direction = boundary.intersects_trajectory((200.0, 150.0), (200.0, 250.0))
    assert crossed is True
    assert direction == CrossingDirection.INGRESS

    # Bottom-to-Top trajectory crossing line
    # From (200, 250) to (200, 150)
    crossed_rev, direction_rev = boundary.intersects_trajectory((200.0, 250.0), (200.0, 150.0))
    assert crossed_rev is True
    assert direction_rev == CrossingDirection.EGRESS

    # Parallel movement that does not intersect
    no_cross, _ = boundary.intersects_trajectory((100.0, 150.0), (300.0, 150.0))
    assert no_cross is False


# ---------------------------------------------------------------------------
# 3. Zone Tracking Lifecycle, Repeated Detections, and Transitions
# ---------------------------------------------------------------------------
def test_repeated_detections_prevent_duplicate_zone_enter(zone_service: ZoneService):
    """Consecutive frames within the same zone emit exactly one zone_enter event."""
    bakery_zone = StoreZone(
        zone_id="zone-bakery",
        name="Bakery",
        zone_type=ZoneType.DEPARTMENT,
        polygon=[(100.0, 100.0), (400.0, 100.0), (400.0, 400.0), (100.0, 400.0)],
        camera_id="cam-01",
    )
    zone_service.register_zone(bakery_zone)

    # Frame 1: Person enters Bakery (bounding box foot at (200, 200))
    box = (150.0, 100.0, 250.0, 200.0)  # foot_x = 200, foot_y = 200
    events_1 = zone_service.update_track(tracker_id=101, box_xyxy=box, frame_idx=1, timestamp=0.1, camera_id="cam-01")
    assert len(events_1) == 1
    assert events_1[0].event_type == "zone_enter"
    assert events_1[0].zone_id == "zone-bakery"

    # Frames 2 to 10: Person lingers inside Bakery
    for f in range(2, 11):
        ts = f * 0.1
        box = (150.0 + f, 100.0, 250.0 + f, 200.0)  # Still inside bakery
        events = zone_service.update_track(tracker_id=101, box_xyxy=box, frame_idx=f, timestamp=ts, camera_id="cam-01")
        # MUST NOT fire duplicate zone_enter events!
        assert len(events) == 0


def test_zone_transition_emits_exit_and_enter(zone_service: ZoneService):
    """Moving directly from Produce into Bakery emits zone_exit followed by zone_enter."""
    produce = StoreZone(
        zone_id="zone-produce",
        name="Produce",
        zone_type=ZoneType.DEPARTMENT,
        polygon=[(0.0, 0.0), (200.0, 0.0), (200.0, 200.0), (0.0, 200.0)],
        camera_id="cam-01",
    )
    bakery = StoreZone(
        zone_id="zone-bakery",
        name="Bakery",
        zone_type=ZoneType.DEPARTMENT,
        polygon=[(200.0, 0.0), (400.0, 0.0), (400.0, 200.0), (200.0, 200.0)],
        camera_id="cam-01",
    )
    zone_service.register_zone(produce)
    zone_service.register_zone(bakery)

    # 1. Start in Produce
    box_produce = (50.0, 50.0, 150.0, 100.0)  # foot at (100, 100)
    e1 = zone_service.update_track(tracker_id=1, box_xyxy=box_produce, frame_idx=1, timestamp=0.0, camera_id="cam-01")
    assert len(e1) == 1
    assert e1[0].event_type == "zone_enter"
    assert e1[0].zone_id == "zone-produce"

    # Stay for 1 second to satisfy min dwell
    box_produce_2 = (60.0, 50.0, 160.0, 100.0)
    zone_service.update_track(tracker_id=1, box_xyxy=box_produce_2, frame_idx=30, timestamp=1.0, camera_id="cam-01")

    # 2. Step across into Bakery
    box_bakery = (250.0, 50.0, 350.0, 100.0)  # foot at (300, 100)
    e2 = zone_service.update_track(tracker_id=1, box_xyxy=box_bakery, frame_idx=60, timestamp=2.0, camera_id="cam-01")
    assert len(e2) == 2
    # First event: exit Produce with dwell ~2.0s
    assert e2[0].event_type == "zone_exit"
    assert e2[0].zone_id == "zone-produce"
    assert e2[0].dwell_seconds >= 1.0

    # Second event: enter Bakery
    assert e2[1].event_type == "zone_enter"
    assert e2[1].zone_id == "zone-bakery"


# ---------------------------------------------------------------------------
# 4. Occlusion Handling & Temporary Detection Loss
# ---------------------------------------------------------------------------
def test_temporary_disappearance_retains_zone(zone_service: ZoneService):
    """Temporary detection dropout (under max_missed_frames) does not trigger premature exit."""
    dairy = StoreZone(
        zone_id="zone-dairy",
        name="Dairy",
        zone_type=ZoneType.DEPARTMENT,
        polygon=[(100.0, 100.0), (300.0, 100.0), (300.0, 300.0), (100.0, 300.0)],
        camera_id="cam-01",
    )
    zone_service.register_zone(dairy)

    # Track enters Dairy
    box = (150.0, 100.0, 250.0, 200.0)
    zone_service.update_track(tracker_id=42, box_xyxy=box, frame_idx=10, timestamp=1.0, camera_id="cam-01")

    # Missed for 5 frames (< max_missed_frames = 10)
    for f in range(11, 16):
        events = zone_service.handle_missed_detections(
            current_frame=f,
            current_timestamp=f * 0.1,
            camera_id="cam-01",
            active_tracker_ids=set(),
        )
        assert len(events) == 0, f"Premature exit fired at frame {f}"

    # Track reappears in Dairy at frame 16
    events_reappear = zone_service.update_track(
        tracker_id=42,
        box_xyxy=box,
        frame_idx=16,
        timestamp=1.6,
        camera_id="cam-01",
    )
    # Still inside, no new entry event should be generated
    assert len(events_reappear) == 0


def test_prolonged_disappearance_triggers_zone_exit(zone_service: ZoneService):
    """Disappearance exceeding max_missed_frames closes active zone and emits zone_exit."""
    checkout = StoreZone(
        zone_id="zone-checkout",
        name="Checkout",
        zone_type=ZoneType.CHECKOUT,
        polygon=[(100.0, 100.0), (300.0, 100.0), (300.0, 300.0), (100.0, 300.0)],
        camera_id="cam-01",
    )
    zone_service.register_zone(checkout)

    # Track enters checkout at t=1.0s, stays until t=3.0s
    box = (150.0, 100.0, 250.0, 200.0)
    zone_service.update_track(tracker_id=99, box_xyxy=box, frame_idx=1, timestamp=1.0, camera_id="cam-01")
    zone_service.update_track(tracker_id=99, box_xyxy=box, frame_idx=60, timestamp=3.0, camera_id="cam-01")

    # Now misses 12 consecutive frames (> max_missed_frames = 10)
    exit_events: list[ZoneEvent] = []
    for f in range(61, 75):
        events = zone_service.handle_missed_detections(
            current_frame=f,
            current_timestamp=3.0 + (f - 60) * 0.1,
            camera_id="cam-01",
            active_tracker_ids=set(),
        )
        exit_events.extend(events)

    assert len(exit_events) == 1
    assert exit_events[0].event_type == "zone_exit"
    assert exit_events[0].zone_id == "zone-checkout"
    assert exit_events[0].dwell_seconds == 2.0  # Duration from t=1.0 to t=3.0


# ---------------------------------------------------------------------------
# 5. Multi-Camera Independent Tracking
# ---------------------------------------------------------------------------
def test_multi_camera_independent_tracking(zone_service: ZoneService):
    """Same tracker ID on different cameras tracks independently without collision."""
    entrance_cam1 = StoreZone(
        zone_id="cam1-entrance",
        name="Entrance",
        zone_type=ZoneType.ENTRANCE,
        polygon=[(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)],
        camera_id="cam-01",
    )
    dairy_cam2 = StoreZone(
        zone_id="cam2-dairy",
        name="Dairy",
        zone_type=ZoneType.DEPARTMENT,
        polygon=[(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)],
        camera_id="cam-02",
    )
    zone_service.register_zone(entrance_cam1)
    zone_service.register_zone(dairy_cam2)

    box = (20.0, 20.0, 80.0, 80.0)

    # Track 1 on Camera 1 enters Entrance
    e_cam1 = zone_service.update_track(tracker_id=1, box_xyxy=box, frame_idx=1, timestamp=0.5, camera_id="cam-01")
    assert len(e_cam1) == 1
    assert e_cam1[0].zone_id == "cam1-entrance"

    # Track 1 on Camera 2 enters Dairy
    e_cam2 = zone_service.update_track(tracker_id=1, box_xyxy=box, frame_idx=1, timestamp=0.5, camera_id="cam-02")
    assert len(e_cam2) == 1
    assert e_cam2[0].zone_id == "cam2-dairy"


# ---------------------------------------------------------------------------
# 6. Full Supermarket Example Layout
# ---------------------------------------------------------------------------
def test_full_supermarket_standard_zones(zone_service: ZoneService):
    """Registers all 8 standard supermarket zones and navigates a customer journey."""
    standard_zones = [
        StoreZone("z-entrance", "Entrance", ZoneType.ENTRANCE, [(0, 0), (100, 0), (100, 100), (0, 100)], "cam-all"),
        StoreZone("z-produce", "Produce", ZoneType.DEPARTMENT, [(100, 0), (200, 0), (200, 100), (100, 100)], "cam-all"),
        StoreZone("z-bakery", "Bakery", ZoneType.DEPARTMENT, [(200, 0), (300, 0), (300, 100), (200, 100)], "cam-all"),
        StoreZone("z-aisle1", "Aisle 1", ZoneType.AISLE, [(0, 100), (100, 100), (100, 200), (0, 200)], "cam-all"),
        StoreZone("z-aisle2", "Aisle 2", ZoneType.AISLE, [(100, 100), (200, 100), (200, 200), (100, 200)], "cam-all"),
        StoreZone("z-dairy", "Dairy", ZoneType.DEPARTMENT, [(200, 100), (300, 100), (300, 200), (200, 200)], "cam-all"),
        StoreZone("z-checkout", "Checkout", ZoneType.CHECKOUT, [(0, 200), (150, 200), (150, 300), (0, 300)], "cam-all"),
        StoreZone("z-exit", "Exit", ZoneType.EXIT, [(150, 200), (300, 200), (300, 300), (150, 300)], "cam-all"),
    ]
    for z in standard_zones:
        zone_service.register_zone(z)

    # Journey: Entrance -> Produce -> Bakery -> Dairy -> Checkout -> Exit
    journey_coords = [
        (50.0, 50.0, "z-entrance"),
        (150.0, 50.0, "z-produce"),
        (250.0, 50.0, "z-bakery"),
        (250.0, 150.0, "z-dairy"),
        (50.0, 250.0, "z-checkout"),
        (200.0, 250.0, "z-exit"),
    ]

    visited_zones: list[str] = []
    t = 0.0
    for idx, (x, y, expected_zone) in enumerate(journey_coords):
        t += 1.0
        # foot at (x, y)
        box = (x - 20, y - 40, x + 20, y)
        events = zone_service.update_track(tracker_id=7, box_xyxy=box, frame_idx=idx * 30, timestamp=t, camera_id="cam-all")
        for ev in events:
            if ev.event_type == "zone_enter" and ev.zone_id:
                visited_zones.append(ev.zone_id)

    assert visited_zones == ["z-entrance", "z-produce", "z-bakery", "z-dairy", "z-checkout", "z-exit"]
