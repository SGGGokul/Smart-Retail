from concurrent.futures import ThreadPoolExecutor
import pytest
from app.services.visit_service import (
    AtomicSequenceIdGenerator,
    CustomerVisit,
    VisitEvent,
    VisitService,
    VisitStatus,
)
from app.services.zone_service import CrossingDirection, ZoneEvent


@pytest.fixture
def visit_service() -> VisitService:
    service = VisitService(default_timeout_seconds=60.0)
    service.register_entrance_line(line_id="line-entrance", camera_id="cam-01")
    service.register_exit_line(line_id="line-exit", camera_id="cam-01")
    return service


# ---------------------------------------------------------------------------
# 1. Customer ID Generation (Sequential and Concurrent)
# ---------------------------------------------------------------------------
def test_sequential_customer_id_generation():
    """Generates sequential customer IDs in CUST-XXXXXX format without gaps."""
    gen = AtomicSequenceIdGenerator(start_val=1)
    ids = [gen.next_id() for _ in range(5)]
    assert ids == [
        "CUST-000001",
        "CUST-000002",
        "CUST-000003",
        "CUST-000004",
        "CUST-000005",
    ]


def test_concurrent_customer_id_generation():
    """Thread-safe generation produces 100 strictly unique IDs under concurrent access."""
    gen = AtomicSequenceIdGenerator(start_val=1)

    def fetch_id(_: int) -> str:
        return gen.next_id()

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(fetch_id, range(100)))

    # All 100 generated IDs must be strictly unique
    assert len(results) == 100
    assert len(set(results)) == 100
    assert "CUST-000001" in results
    assert "CUST-000100" in results


# ---------------------------------------------------------------------------
# 2. Confirmed Entrance, First-Time Customer & Duplicate Entrance
# ---------------------------------------------------------------------------
def test_first_time_customer_confirmed_entrance(visit_service: VisitService):
    """Crossing the entrance line allocates CUST-000001 and begins an ACTIVE visit."""
    event = ZoneEvent(
        event_type="boundary_crossed",
        tracker_id=10,
        camera_id="cam-01",
        timestamp=100.0,
        frame_idx=10,
        line_id="line-entrance",
        crossing_direction=CrossingDirection.INGRESS,
    )
    ve = visit_service.process_zone_event(event)

    assert ve is not None
    assert ve.event_type == "entrance_confirmed"
    assert ve.customer_id == "CUST-000001"

    visit = visit_service.get_active_visit_by_customer("CUST-000001")
    assert visit is not None
    assert visit.status == VisitStatus.ACTIVE
    assert visit.entry_time == 100.0
    assert visit.is_repeat_visit is False
    assert visit.visit_number == 1


def test_duplicate_entrance_event_is_ignored(visit_service: VisitService):
    """Crossing the entrance line again while visit is ACTIVE is ignored to prevent duplicate visits."""
    event = ZoneEvent(
        event_type="boundary_crossed",
        tracker_id=10,
        camera_id="cam-01",
        timestamp=100.0,
        frame_idx=10,
        line_id="line-entrance",
        crossing_direction=CrossingDirection.INGRESS,
    )
    ve1 = visit_service.process_zone_event(event)
    assert ve1 is not None

    # Customer pauses or steps back across entrance boundary 2 seconds later
    event_repeat = ZoneEvent(
        event_type="boundary_crossed",
        tracker_id=10,
        camera_id="cam-01",
        timestamp=102.0,
        frame_idx=30,
        line_id="line-entrance",
        crossing_direction=CrossingDirection.INGRESS,
    )
    ve2 = visit_service.process_zone_event(event_repeat)

    # Must be dropped without creating a secondary visit
    assert ve2 is None
    all_visits = visit_service.get_all_visits()
    assert len(all_visits) == 1


# ---------------------------------------------------------------------------
# 3. Zone Transitions and Rule: Zone Exit != Store Exit
# ---------------------------------------------------------------------------
def test_zone_transitions_append_to_active_visit(visit_service: VisitService):
    """Zone enter and exit events record journey milestones without closing the store visit."""
    # Entrance
    visit_service.process_zone_event(
        ZoneEvent(
            event_type="boundary_crossed",
            tracker_id=20,
            camera_id="cam-01",
            timestamp=10.0,
            frame_idx=1,
            line_id="line-entrance",
            crossing_direction=CrossingDirection.INGRESS,
        )
    )

    # Enter Produce zone
    ve_enter = visit_service.process_zone_event(
        ZoneEvent(
            event_type="zone_enter",
            tracker_id=20,
            camera_id="cam-01",
            timestamp=15.0,
            frame_idx=50,
            zone_id="z-produce",
            zone_name="Produce",
        )
    )
    assert ve_enter is not None
    assert ve_enter.event_type == "zone_enter"
    assert ve_enter.zone_name == "Produce"

    # Exit Produce zone (dwell = 25.0s)
    ve_exit = visit_service.process_zone_event(
        ZoneEvent(
            event_type="zone_exit",
            tracker_id=20,
            camera_id="cam-01",
            timestamp=40.0,
            frame_idx=300,
            zone_id="z-produce",
            zone_name="Produce",
            dwell_seconds=25.0,
        )
    )
    assert ve_exit is not None
    assert ve_exit.event_type == "zone_exit"
    assert ve_exit.dwell_seconds == 25.0

    # CRITICAL CHECK: Visit MUST STILL BE ACTIVE!
    visit = visit_service.get_active_visit_by_customer("CUST-000001")
    assert visit is not None
    assert visit.status == VisitStatus.ACTIVE
    assert visit.current_zone_id is None
    assert visit.zone_dwell_times["z-produce"] == 25.0
    assert visit.zones_visited == ["Produce"]


# ---------------------------------------------------------------------------
# 4. Confirmed Store Exit Closes Visit
# ---------------------------------------------------------------------------
def test_confirmed_store_exit_completes_visit(visit_service: VisitService):
    """Crossing the exit boundary completes the visit and calculates total duration."""
    # Entrance at t=10.0
    visit_service.process_zone_event(
        ZoneEvent(
            event_type="boundary_crossed",
            tracker_id=30,
            camera_id="cam-01",
            timestamp=10.0,
            frame_idx=1,
            line_id="line-entrance",
            crossing_direction=CrossingDirection.INGRESS,
        )
    )

    # Confirmed Exit at t=70.0 (duration = 60.0s)
    exit_ev = visit_service.process_zone_event(
        ZoneEvent(
            event_type="boundary_crossed",
            tracker_id=30,
            camera_id="cam-01",
            timestamp=70.0,
            frame_idx=600,
            line_id="line-exit",
            crossing_direction=CrossingDirection.EGRESS,
        )
    )
    assert exit_ev is not None
    assert exit_ev.event_type == "store_exit_confirmed"

    # Visit status should be COMPLETED
    visit = visit_service.get_visit(exit_ev.visit_id)
    assert visit is not None
    assert visit.status == VisitStatus.COMPLETED
    assert visit.exit_time == 70.0
    assert visit.duration_seconds == 60.0

    # Active customer mapping must be cleared
    assert visit_service.get_active_visit_by_customer(visit.customer_id) is None


def test_duplicate_exit_event_is_ignored(visit_service: VisitService):
    """Crossing exit boundary when no visit is active produces no events."""
    event = ZoneEvent(
        event_type="boundary_crossed",
        tracker_id=999,
        camera_id="cam-01",
        timestamp=500.0,
        frame_idx=5000,
        line_id="line-exit",
        crossing_direction=CrossingDirection.EGRESS,
    )
    res = visit_service.process_zone_event(event)
    assert res is None


# ---------------------------------------------------------------------------
# 5. Repeat Visits for Same Customer
# ---------------------------------------------------------------------------
def test_repeat_visit_increment_and_persistence(visit_service: VisitService):
    """A customer with a completed visit who re-enters gets visit_number=2 and is_repeat_visit=True."""
    # Visit 1: Enter at t=0, Exit at t=50
    visit_service.process_zone_event(
        ZoneEvent(
            event_type="boundary_crossed",
            tracker_id=1,
            camera_id="cam-01",
            timestamp=0.0,
            frame_idx=0,
            line_id="line-entrance",
            crossing_direction=CrossingDirection.INGRESS,
        )
    )
    visit_service.process_zone_event(
        ZoneEvent(
            event_type="boundary_crossed",
            tracker_id=1,
            camera_id="cam-01",
            timestamp=50.0,
            frame_idx=500,
            line_id="line-exit",
            crossing_direction=CrossingDirection.EGRESS,
        )
    )

    # Visit 2: Same customer CUST-000001 recognized via ReID re-enters at t=500
    ve2 = visit_service.process_zone_event(
        event=ZoneEvent(
            event_type="boundary_crossed",
            tracker_id=2,  # Different ByteTrack tracker ID!
            camera_id="cam-01",
            timestamp=500.0,
            frame_idx=5000,
            line_id="line-entrance",
            crossing_direction=CrossingDirection.INGRESS,
        ),
        matched_customer_id="CUST-000001",
    )
    assert ve2 is not None
    assert ve2.customer_id == "CUST-000001"

    # Verify visit history
    history = visit_service.get_customer_history("CUST-000001")
    assert len(history) == 2
    assert history[0].visit_number == 1
    assert history[0].is_repeat_visit is False
    assert history[0].status == VisitStatus.COMPLETED

    assert history[1].visit_number == 2
    assert history[1].is_repeat_visit is True
    assert history[1].status == VisitStatus.ACTIVE


# ---------------------------------------------------------------------------
# 6. Temporary Tracking Loss & Tracking Resumed
# ---------------------------------------------------------------------------
def test_tracking_loss_does_not_close_visit(visit_service: VisitService):
    """Detector losing track (occlusion) records tracking_lost event but preserves visit as ACTIVE."""
    visit_service.process_zone_event(
        ZoneEvent(
            event_type="boundary_crossed",
            tracker_id=5,
            camera_id="cam-01",
            timestamp=10.0,
            frame_idx=1,
            line_id="line-entrance",
            crossing_direction=CrossingDirection.INGRESS,
        )
    )

    # Tracking lost at t=20.0
    lost_ev = visit_service.handle_tracking_loss(camera_id="cam-01", tracker_id=5, timestamp=20.0)
    assert lost_ev is not None
    assert lost_ev.event_type == "tracking_lost"

    # Visit MUST STILL BE ACTIVE!
    visit = visit_service.get_active_visit_by_customer("CUST-000001")
    assert visit is not None
    assert visit.status == VisitStatus.ACTIVE

    # Tracking resumed at t=25.0
    resumed_ev = visit_service.handle_tracking_resumed(camera_id="cam-01", tracker_id=5, timestamp=25.0)
    assert resumed_ev is not None
    assert resumed_ev.event_type == "tracking_resumed"
    assert visit.status == VisitStatus.ACTIVE


# ---------------------------------------------------------------------------
# 7. Inactivity Timeout (Distinguished from Confirmed Exit)
# ---------------------------------------------------------------------------
def test_inactivity_timeout_marks_timed_out_not_completed(visit_service: VisitService):
    """Sessions exceeding timeout are marked TIMED_OUT, not COMPLETED or physically exited."""
    visit_service.process_zone_event(
        ZoneEvent(
            event_type="boundary_crossed",
            tracker_id=8,
            camera_id="cam-01",
            timestamp=10.0,
            frame_idx=1,
            line_id="line-entrance",
            crossing_direction=CrossingDirection.INGRESS,
        )
    )

    # Fast forward by 65s (timeout configured at 60s)
    timed_out = visit_service.check_inactivity_timeouts(current_timestamp=75.0)
    assert len(timed_out) == 1
    assert timed_out[0].status == VisitStatus.TIMED_OUT
    assert timed_out[0].exit_time is None  # NOT a confirmed physical exit!
    assert timed_out[0].duration_seconds == 0.0  # Last seen was entrance at 10.0


# ---------------------------------------------------------------------------
# 8. Incomplete Sessions on Pipeline Conclusion
# ---------------------------------------------------------------------------
def test_pipeline_conclusion_marks_incomplete_sessions(visit_service: VisitService):
    """Remaining active sessions at video stream termination are cleanly marked INCOMPLETE."""
    visit_service.process_zone_event(
        ZoneEvent(
            event_type="boundary_crossed",
            tracker_id=12,
            camera_id="cam-01",
            timestamp=0.0,
            frame_idx=1,
            line_id="line-entrance",
            crossing_direction=CrossingDirection.INGRESS,
        )
    )

    incomplete = visit_service.end_incomplete_sessions(final_timestamp=120.0)
    assert len(incomplete) == 1
    assert incomplete[0].status == VisitStatus.INCOMPLETE
    assert incomplete[0].duration_seconds == 120.0


# ---------------------------------------------------------------------------
# 9. Uncertain Identity Matching Isolation
# ---------------------------------------------------------------------------
def test_uncertain_identity_does_not_merge_customer_history(visit_service: VisitService):
    """Uncertain identity match is flagged and does not merge into verified customer history."""
    # Create verified customer CUST-000001
    visit_service.process_zone_event(
        ZoneEvent(
            event_type="boundary_crossed",
            tracker_id=1,
            camera_id="cam-01",
            timestamp=0.0,
            frame_idx=0,
            line_id="line-entrance",
            crossing_direction=CrossingDirection.INGRESS,
        )
    )

    # Observation with low ReID confidence / uncertain match
    ve_uncertain = visit_service.process_zone_event(
        event=ZoneEvent(
            event_type="boundary_crossed",
            tracker_id=2,
            camera_id="cam-01",
            timestamp=10.0,
            frame_idx=100,
            line_id="line-entrance",
            crossing_direction=CrossingDirection.INGRESS,
        ),
        matched_customer_id="CUST-000001",
        is_uncertain_match=True,  # Low confidence match
    )

    assert ve_uncertain is not None
    # Must allocate a separate ID (CUST-000002) and NOT merge into CUST-000001!
    assert ve_uncertain.customer_id == "CUST-000002"

    visit_uncertain = visit_service.get_visit(ve_uncertain.visit_id)
    assert visit_uncertain is not None
    assert visit_uncertain.is_uncertain_match is True

    # Customer 1's history must remain untainted (only 1 visit)
    c1_history = visit_service.get_customer_history("CUST-000001")
    assert len(c1_history) == 1
