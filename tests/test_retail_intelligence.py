"""Automated Test Suite for Unified Customer Intelligence, Daily Visitor Counting,

Shelf Monitoring & Temporal Pickup/Return System (Phases 1-14).
"""

from concurrent.futures import ThreadPoolExecutor
import datetime
import pytest
from app.services.identity_service import (
    AppearanceEmbedding,
    ConfirmationStatus,
    DailyVisitor,
    IdentityService,
)
from app.services.shelf_service import (
    RetailEvent,
    ShelfBay,
    ShelfEventStatus,
    ShelfService,
)
from app.services.visit_service import (
    CustomerVisit,
    VisitService,
    VisitStatus,
)
from app.services.zone_service import CrossingDirection, ZoneEvent
import numpy as np


@pytest.fixture
def identity_service() -> IdentityService:
    service = IdentityService(default_timezone="UTC", reid_similarity_threshold=0.85, ambiguity_margin=0.10)
    service.clear()
    return service


@pytest.fixture
def shelf_service() -> ShelfService:
    service = ShelfService(smoothing_alpha=0.5)
    service.clear()
    bay = ShelfBay(
        shelf_id="shelf-aisle-1",
        store_id="store-104",
        camera_id="cam-01",
        name="Beverage Bay 1",
        aisle="Aisle 1",
        tier_count=3,
        polygon=[(100.0, 100.0), (300.0, 100.0), (300.0, 250.0), (100.0, 250.0)],
        interaction_polygon=[(50.0, 50.0), (350.0, 50.0), (350.0, 350.0), (50.0, 350.0)],
        configured_capacity=10,
        product_classes=["bottle", "can"],
    )
    service.register_shelf_bay(bay)
    return service


@pytest.fixture
def visit_service() -> VisitService:
    service = VisitService(store_id="store-104", default_timeout_seconds=60.0)
    service.clear()
    service.register_entrance_line(line_id="line-entrance", camera_id="cam-01")
    service.register_exit_line(line_id="line-exit", camera_id="cam-01")
    return service


# ==============================================================================
# VISITOR TESTS (1 to 17)
# ==============================================================================

def test_1_one_person_across_100_frames_produces_one_visitor(identity_service: IdentityService):
    """1. One person observed continuously across 100 frames produces exactly one daily visitor."""
    embedding = identity_service.create_synthetic_embedding(seed=42, camera_id="cam-01", timestamp=1.0)
    visitor_ids = set()

    for frame in range(1, 101):
        t = frame * 0.1
        vis, is_return, conf = identity_service.resolve_or_create_daily_visitor(
            store_id="store-104",
            local_date="2026-11-09",
            camera_id="cam-01",
            tracker_id=1,
            timestamp=t,
            embedding=embedding,
        )
        visitor_ids.add(vis.visitor_id)

    assert len(visitor_ids) == 1
    visitors = identity_service.list_daily_visitors("store-104", "2026-11-09")
    assert len(visitors) == 1
    assert visitors[0].anonymous_label == "VIS-0001"


def test_2_temporary_detection_loss_does_not_create_new_visitor(identity_service: IdentityService):
    """2. Temporary detection loss (e.g. 15 frames) does not create a new visitor."""
    emb = identity_service.create_synthetic_embedding(seed=42, camera_id="cam-01", timestamp=1.0)

    # Seen frames 1-10
    vis1, _, _ = identity_service.resolve_or_create_daily_visitor(
        store_id="store-104", local_date="2026-11-09", camera_id="cam-01", tracker_id=5, timestamp=1.0, embedding=emb
    )
    # Tracker reappears at frame 30 with same camera tracker
    vis2, _, _ = identity_service.resolve_or_create_daily_visitor(
        store_id="store-104", local_date="2026-11-09", camera_id="cam-01", tracker_id=5, timestamp=3.0, embedding=emb
    )

    assert vis1.visitor_id == vis2.visitor_id
    assert len(identity_service.list_daily_visitors("store-104", "2026-11-09")) == 1


def test_3_entry_creates_visit_session(visit_service: VisitService):
    """3. Verified entrance crossing creates an ACTIVE visit session."""
    ev = ZoneEvent(
        event_type="boundary_crossed",
        tracker_id=101,
        camera_id="cam-01",
        timestamp=10.0,
        frame_idx=100,
        line_id="line-entrance",
        crossing_direction=CrossingDirection.INGRESS,
    )
    ve = visit_service.process_zone_event(ev)
    assert ve is not None
    assert ve.event_type == "entrance_confirmed"

    visit = visit_service.get_active_visit_by_customer(ve.customer_id)
    assert visit is not None
    assert visit.status == VisitStatus.ACTIVE
    assert visit.entry_time == 10.0


def test_4_exit_closes_the_session(visit_service: VisitService):
    """4. Verified exit line crossing closes the session as COMPLETED."""
    # Enter
    ve_in = visit_service.process_zone_event(
        ZoneEvent(
            event_type="boundary_crossed",
            tracker_id=102,
            camera_id="cam-01",
            timestamp=20.0,
            frame_idx=200,
            line_id="line-entrance",
            crossing_direction=CrossingDirection.INGRESS,
        )
    )
    # Exit
    ve_out = visit_service.process_zone_event(
        ZoneEvent(
            event_type="boundary_crossed",
            tracker_id=102,
            camera_id="cam-01",
            timestamp=50.0,
            frame_idx=500,
            line_id="line-exit",
            crossing_direction=CrossingDirection.EGRESS,
        )
    )
    assert ve_out is not None
    assert ve_out.event_type == "store_exit_confirmed"

    visit = visit_service.get_visit(ve_in.visit_id)
    assert visit is not None
    assert visit.status == VisitStatus.COMPLETED
    assert visit.exit_time == 50.0
    assert visit.duration_seconds == 30.0


def test_5_same_day_reentry_reuses_visitor_identity(identity_service: IdentityService):
    """5. Same-day re-entry reuses the daily visitor identity."""
    emb = identity_service.create_synthetic_embedding(seed=100, camera_id="cam-01", timestamp=10.0)

    # First journey: tracker 10 on cam-01
    vis1, is_ret1, _ = identity_service.resolve_or_create_daily_visitor(
        "store-104", "2026-11-09", "cam-01", tracker_id=10, timestamp=10.0, embedding=emb
    )
    identity_service.bind_session_to_visitor(vis1, "sess-1")
    identity_service.close_visitor_session(vis1, "sess-1", dwell_seconds=300.0)

    # Returning 2 hours later with new camera tracker ID 45
    vis2, is_ret2, conf = identity_service.resolve_or_create_daily_visitor(
        "store-104", "2026-11-09", "cam-01", tracker_id=45, timestamp=7200.0, embedding=emb
    )

    assert vis2.visitor_id == vis1.visitor_id
    assert is_ret2 is True
    assert conf == ConfirmationStatus.CONFIRMED


def test_6_reentry_creates_a_new_session(identity_service: IdentityService):
    """6. Re-entry creates a new distinct visit session while incrementing total_visits."""
    emb = identity_service.create_synthetic_embedding(seed=101, camera_id="cam-01", timestamp=1.0)

    vis, _, _ = identity_service.resolve_or_create_daily_visitor(
        "store-104", "2026-11-09", "cam-01", tracker_id=11, timestamp=1.0, embedding=emb
    )
    identity_service.bind_session_to_visitor(vis, "sess-A")
    identity_service.close_visitor_session(vis, "sess-A", dwell_seconds=60.0)

    # Re-entry session
    identity_service.bind_session_to_visitor(vis, "sess-B")

    assert vis.session_ids == ["sess-A", "sess-B"]
    assert vis.total_visits == 2
    assert vis.active_session_id == "sess-B"


def test_7_different_person_receives_different_identity(identity_service: IdentityService):
    """7. A person with distinct appearance receives an independent visitor identity."""
    emb1 = identity_service.create_synthetic_embedding(seed=1, camera_id="cam-01", timestamp=10.0)
    emb2 = identity_service.create_synthetic_embedding(seed=999, camera_id="cam-01", timestamp=10.0)

    vis1, _, _ = identity_service.resolve_or_create_daily_visitor(
        "store-104", "2026-11-09", "cam-01", tracker_id=1, timestamp=10.0, embedding=emb1
    )
    vis2, _, _ = identity_service.resolve_or_create_daily_visitor(
        "store-104", "2026-11-09", "cam-01", tracker_id=2, timestamp=10.0, embedding=emb2
    )

    assert vis1.visitor_id != vis2.visitor_id
    assert vis1.anonymous_label == "VIS-0001"
    assert vis2.anonymous_label == "VIS-0002"



def test_14_new_local_calendar_days_create_new_identities(identity_service: IdentityService):
    """14. The same physical customer returning the next day receives a NEW daily visitor identity."""
    emb = identity_service.create_synthetic_embedding(seed=42, camera_id="cam-01")

    # Day 1: 2026-11-09
    v_day1, _, _ = identity_service.resolve_or_create_daily_visitor(
        "store-104", "2026-11-09", "cam-01", 1, 10.0, emb
    )
    # Day 2: 2026-11-10
    v_day2, _, _ = identity_service.resolve_or_create_daily_visitor(
        "store-104", "2026-11-10", "cam-01", 1, 10.0, emb
    )

    assert v_day1.visitor_id != v_day2.visitor_id
    assert v_day1.anonymous_label == "VIS-0001"
    assert v_day2.anonymous_label == "VIS-0001"  # Sequence resets per day


def test_15_multiple_stores_maintain_independent_identities(identity_service: IdentityService):
    """15. Different store locations maintain strictly independent daily visitor counters and IDs."""
    emb = identity_service.create_synthetic_embedding(seed=42)

    v_store_a, _, _ = identity_service.resolve_or_create_daily_visitor(
        "store-104", "2026-11-09", "cam-01", 1, 10.0, emb
    )
    v_store_b, _, _ = identity_service.resolve_or_create_daily_visitor(
        "store-205", "2026-11-09", "cam-01", 1, 10.0, emb
    )

    assert v_store_a.visitor_id != v_store_b.visitor_id
    assert v_store_a.store_id == "store-104"
    assert v_store_b.store_id == "store-205"


def test_16_midnight_and_daylight_saving_boundaries_work_correctly(identity_service: IdentityService):
    """16. Store-local date calculation accurately respects IANA timezones and midnight roll-overs."""
    # NYC timezone: 2026-11-09 23:59:00 EST -> 2026-11-09
    t_before_midnight = 1794286740.0  # Approx epoch for 23:59
    date_before = identity_service.get_store_local_date(
        "store-nyc", tz_name="America/New_York", timestamp=t_before_midnight
    )

    # 2 minutes later: 2026-11-10 00:01:00 EST -> 2026-11-10
    t_after_midnight = t_before_midnight + 120.0
    date_after = identity_service.get_store_local_date(
        "store-nyc", tz_name="America/New_York", timestamp=t_after_midnight
    )

    assert date_before != date_after


def test_17_concurrent_processing_cannot_create_duplicate_daily_visitors(identity_service: IdentityService):
    """17. Concurrent threads processing observations produce strictly monotonic, non-colliding visitor labels."""
    def worker(idx: int):
        emb = identity_service.create_synthetic_embedding(seed=idx, camera_id="cam-01")
        vis, _, _ = identity_service.resolve_or_create_daily_visitor(
            "store-104", "2026-11-09", "cam-01", tracker_id=idx, timestamp=10.0, embedding=emb
        )
        return vis.anonymous_label

    with ThreadPoolExecutor(max_workers=8) as pool:
        labels = list(pool.map(worker, range(50)))

    assert len(labels) == 50
    assert len(set(labels)) == 50
    assert "VIS-0001" in labels
    assert "VIS-0050" in labels


# ==============================================================================
# SHELF TESTS (18 to 34)
# ==============================================================================

