"""Customer Visit and Persistent Anonymous ID Lifecycle Service.

Manages pseudonymous customer ID generation (CUST-000001), visit session lifecycles,
entrance/exit event processing, zone transitions, repeat visits, inactivity timeouts,
and uncertain identity isolation.
"""

from dataclasses import dataclass, field
import enum
import logging
import threading
from typing import Any, Dict, List, Optional, Protocol, Set, Tuple
import uuid

from app.models.customer_journey import CustomerVisitModel, CustomerZoneEventModel
from app.services.zone_service import CrossingDirection, ZoneEvent
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("retailiq.visit_service")


class VisitStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    TIMED_OUT = "timed_out"
    INCOMPLETE = "incomplete"


class CustomerIdGenerator(Protocol):
    """Protocol for atomic, concurrency-safe customer ID generation."""
    def next_id(self) -> str:
        ...


class AtomicSequenceIdGenerator:
    """Thread-safe, monotonic sequential customer ID generator.

    Produces persistent pseudonymous IDs formatted as CUST-000001, CUST-000002...
    Guarantees atomic increments without race conditions or ID duplication.
    """

    def __init__(self, start_val: int = 1, prefix: str = "CUST-", digits: int = 6) -> None:
        self._current = start_val
        self._prefix = prefix
        self._digits = digits
        self._lock = threading.Lock()

    def next_id(self) -> str:
        with self._lock:
            val = self._current
            self._current += 1
            return f"{self._prefix}{val:0{self._digits}d}"

    def reset(self, start_val: int = 1) -> None:
        with self._lock:
            self._current = start_val


@dataclass
class VisitEvent:
    """Detailed event within a customer's visit journey."""
    event_id: str
    visit_id: str
    customer_id: str
    camera_id: str
    event_type: str  # 'entrance_confirmed', 'zone_enter', 'zone_exit', 'store_exit_confirmed', 'tracking_lost', 'tracking_resumed'
    timestamp: float
    zone_id: Optional[str] = None
    zone_name: Optional[str] = None
    dwell_seconds: float = 0.0
    confidence: float = 1.0


@dataclass
class CustomerVisit:
    """A customer's visit session in the store."""
    visit_id: str
    customer_id: str
    store_id: str
    entry_time: float
    status: VisitStatus = VisitStatus.ACTIVE
    exit_time: Optional[float] = None
    duration_seconds: float = 0.0
    cameras_seen: Set[str] = field(default_factory=set)
    zones_visited: List[str] = field(default_factory=list)
    zone_dwell_times: Dict[str, float] = field(default_factory=dict)
    current_zone_id: Optional[str] = None
    last_seen_time: float = 0.0
    is_repeat_visit: bool = False
    visit_number: int = 1
    is_uncertain_match: bool = False
    journey_events: List[VisitEvent] = field(default_factory=list)
    visitor_id: Optional[str] = None
    local_date: Optional[str] = None

    @property
    def total_observed_dwell_seconds(self) -> float:
        """Sum of all observed zone dwell durations."""
        return sum(self.zone_dwell_times.values())


class VisitService:
    """Visit lifecycle management and anonymous customer tracking service.

    Translates ZoneService spatial events into store visits and customer journeys.
    Enforces that tracking loss or zone exit never terminates a store visit.
    """

    def __init__(
        self,
        id_generator: Optional[CustomerIdGenerator] = None,
        default_timeout_seconds: float = 1800.0,  # 30 minutes
        store_id: str = "store-104",
    ) -> None:
        self.id_generator: CustomerIdGenerator = id_generator or AtomicSequenceIdGenerator()
        self.timeout_seconds = default_timeout_seconds
        self.store_id = store_id

        # Thread safety lock
        self._lock = threading.Lock()

        # Configured entrance and exit boundary lines: camera_id -> Set[line_id]
        self._entrance_lines: Dict[str, Set[str]] = {}
        self._exit_lines: Dict[str, Set[str]] = {}

        # Active tracker to visit mapping: (camera_id, tracker_id) -> visit_id
        self._tracker_to_visit: Dict[Tuple[str, int], str] = {}

        # Active customer to visit mapping: customer_id -> visit_id
        self._customer_to_active_visit: Dict[str, str] = {}

        # Visit repository: visit_id -> CustomerVisit
        self._visits: Dict[str, CustomerVisit] = {}

        # Customer visit history: customer_id -> List[visit_id] (all visits past & present)
        self._customer_history: Dict[str, List[str]] = {}

    def register_entrance_line(self, line_id: str, camera_id: str = "default") -> None:
        """Register a boundary tripwire line as a store entrance."""
        with self._lock:
            if camera_id not in self._entrance_lines:
                self._entrance_lines[camera_id] = set()
            self._entrance_lines[camera_id].add(line_id)

    def register_exit_line(self, line_id: str, camera_id: str = "default") -> None:
        """Register a boundary tripwire line as a store exit."""
        with self._lock:
            if camera_id not in self._exit_lines:
                self._exit_lines[camera_id] = set()
            self._exit_lines[camera_id].add(line_id)

    def is_entrance_line(self, line_id: str, camera_id: str = "default") -> bool:
        return line_id in self._entrance_lines.get(camera_id, set())

    def is_exit_line(self, line_id: str, camera_id: str = "default") -> bool:
        return line_id in self._exit_lines.get(camera_id, set())

    def bind_tracker_to_customer(self, camera_id: str, tracker_id: int, customer_id: str) -> None:
        """Associate a camera-specific tracker ID with an existing customer ID."""
        with self._lock:
            active_visit_id = self._customer_to_active_visit.get(customer_id)
            if active_visit_id:
                self._tracker_to_visit[(camera_id, tracker_id)] = active_visit_id
                visit = self._visits.get(active_visit_id)
                if visit:
                    visit.cameras_seen.add(camera_id)

    def process_zone_event(
        self,
        event: ZoneEvent,
        matched_customer_id: Optional[str] = None,
        is_uncertain_match: bool = False,
    ) -> Optional[VisitEvent]:
        """Translate a ZoneEvent into an updated CustomerVisit state and journey event.

        Args:
            event: Spatial ZoneEvent emitted by ZoneService.
            matched_customer_id: Optional persistent customer ID if identified via ReID.
            is_uncertain_match: If True, flags the observation as uncertain and avoids
                                merging with verified customer history.

        Returns:
            Emitted VisitEvent or None if event was a duplicate / filtered.
        """
        with self._lock:
            cam_id = event.camera_id
            t_id = event.tracker_id
            tracker_key = (cam_id, t_id)
            current_time = event.timestamp

            active_visit_id = self._tracker_to_visit.get(tracker_key)
            visit = self._visits.get(active_visit_id) if active_visit_id else None

            # ------------------------------------------------------------------
            # 1. Boundary Crossed Events (Entrance & Exit)
            # ------------------------------------------------------------------
            if event.event_type == "boundary_crossed" and event.line_id:
                # Case 1A: Entrance Boundary Crossing
                if self.is_entrance_line(event.line_id, cam_id) and event.crossing_direction == CrossingDirection.INGRESS:
                    # Prevent duplicate entrance events if tracker already has an active visit
                    if visit and visit.status == VisitStatus.ACTIVE:
                        logger.debug(f"Tracker {t_id} on {cam_id} crossed entrance again; ignoring duplicate.")
                        return None

                    # Resolve Customer ID & Repeat Visit Status
                    if is_uncertain_match:
                        # Uncertain identity: do NOT merge with verified history; allocate dedicated unmerged ID
                        customer_id = self.id_generator.next_id()
                        repeat = False
                        visit_num = 1
                    elif matched_customer_id:
                        customer_id = matched_customer_id
                        past_visits = self._customer_history.get(customer_id, [])
                        repeat = len(past_visits) > 0
                        visit_num = len(past_visits) + 1
                    else:
                        customer_id = self.id_generator.next_id()
                        repeat = False
                        visit_num = 1

                    # Create New Active Visit
                    visit_id = f"vis-{uuid.uuid4().hex[:8]}"

                    # Integrate with store-day daily visitor identity lifecycle
                    from app.services.identity_service import get_identity_service
                    identity_svc = get_identity_service()
                    local_date = identity_svc.get_store_local_date(self.store_id, timestamp=current_time)
                    daily_vis, is_daily_return, _ = identity_svc.resolve_or_create_daily_visitor(
                        store_id=self.store_id,
                        local_date=local_date,
                        camera_id=cam_id,
                        tracker_id=t_id,
                        timestamp=current_time,
                        is_uncertain=is_uncertain_match,
                    )
                    identity_svc.bind_session_to_visitor(daily_vis, visit_id)

                    new_visit = CustomerVisit(
                        visit_id=visit_id,
                        customer_id=customer_id,
                        store_id=self.store_id,
                        entry_time=current_time,
                        last_seen_time=current_time,
                        status=VisitStatus.ACTIVE,
                        is_repeat_visit=repeat or is_daily_return,
                        visit_number=visit_num,
                        is_uncertain_match=is_uncertain_match,
                        visitor_id=daily_vis.visitor_id,
                        local_date=local_date,
                    )
                    new_visit.cameras_seen.add(cam_id)

                    v_event = VisitEvent(
                        event_id=str(uuid.uuid4()),
                        visit_id=visit_id,
                        customer_id=customer_id,
                        camera_id=cam_id,
                        event_type="entrance_confirmed",
                        timestamp=current_time,
                    )
                    new_visit.journey_events.append(v_event)

                    # Update mappings
                    self._visits[visit_id] = new_visit
                    self._tracker_to_visit[tracker_key] = visit_id
                    self._customer_to_active_visit[customer_id] = visit_id
                    if customer_id not in self._customer_history:
                        self._customer_history[customer_id] = []
                    self._customer_history[customer_id].append(visit_id)

                    return v_event

                # Case 1B: Exit Boundary Crossing (Confirmed Store Exit)
                elif self.is_exit_line(event.line_id, cam_id) and event.crossing_direction == CrossingDirection.EGRESS:
                    if not visit or visit.status != VisitStatus.ACTIVE:
                        logger.debug(f"Exit crossed by unassociated tracker {t_id} on {cam_id}.")
                        return None

                    # Close the visit as COMPLETED
                    visit.status = VisitStatus.COMPLETED
                    visit.exit_time = current_time
                    visit.last_seen_time = current_time
                    visit.duration_seconds = max(0.0, current_time - visit.entry_time)

                    if visit.visitor_id and visit.local_date:
                        from app.services.identity_service import get_identity_service
                        identity_svc = get_identity_service()
                        daily_vis = identity_svc.get_visitor(visit.store_id, visit.local_date, visit.visitor_id)
                        if daily_vis:
                            identity_svc.close_visitor_session(daily_vis, visit.visit_id, visit.duration_seconds)

                    v_event = VisitEvent(
                        event_id=str(uuid.uuid4()),
                        visit_id=visit.visit_id,
                        customer_id=visit.customer_id,
                        camera_id=cam_id,
                        event_type="store_exit_confirmed",
                        timestamp=current_time,
                    )
                    visit.journey_events.append(v_event)

                    # Clean up active mappings
                    self._customer_to_active_visit.pop(visit.customer_id, None)
                    self._tracker_to_visit.pop(tracker_key, None)

                    return v_event

            # ------------------------------------------------------------------
            # 2. Zone Enter & Zone Exit Events
            # ------------------------------------------------------------------
            if not visit or visit.status != VisitStatus.ACTIVE:
                # If tracker enters a zone before crossing an entrance line, start an ad-hoc visit
                # (e.g. video begins with customer already inside the store)
                if event.event_type == "zone_enter":
                    customer_id = matched_customer_id if (matched_customer_id and not is_uncertain_match) else self.id_generator.next_id()
                    visit_id = f"vis-{uuid.uuid4().hex[:8]}"
                    past_visits = self._customer_history.get(customer_id, [])
                    visit = CustomerVisit(
                        visit_id=visit_id,
                        customer_id=customer_id,
                        store_id=self.store_id,
                        entry_time=current_time,
                        last_seen_time=current_time,
                        status=VisitStatus.ACTIVE,
                        is_repeat_visit=len(past_visits) > 0,
                        visit_number=len(past_visits) + 1,
                        is_uncertain_match=is_uncertain_match,
                    )
                    visit.cameras_seen.add(cam_id)
                    self._visits[visit_id] = visit
                    self._tracker_to_visit[tracker_key] = visit_id
                    self._customer_to_active_visit[customer_id] = visit_id
                    if customer_id not in self._customer_history:
                        self._customer_history[customer_id] = []
                    self._customer_history[customer_id].append(visit_id)
                else:
                    return None

            # Update visit heartbeat
            visit.last_seen_time = current_time
            visit.cameras_seen.add(cam_id)

            if event.event_type == "zone_enter":
                visit.current_zone_id = event.zone_id
                if event.zone_name and (not visit.zones_visited or visit.zones_visited[-1] != event.zone_name):
                    visit.zones_visited.append(event.zone_name)

                v_event = VisitEvent(
                    event_id=str(uuid.uuid4()),
                    visit_id=visit.visit_id,
                    customer_id=visit.customer_id,
                    camera_id=cam_id,
                    event_type="zone_enter",
                    timestamp=current_time,
                    zone_id=event.zone_id,
                    zone_name=event.zone_name,
                )
                visit.journey_events.append(v_event)
                return v_event

            elif event.event_type == "zone_exit":
                # CRITICAL: Zone exit DOES NOT end the store visit!
                if event.zone_id:
                    visit.zone_dwell_times[event.zone_id] = (
                        visit.zone_dwell_times.get(event.zone_id, 0.0) + event.dwell_seconds
                    )
                if visit.current_zone_id == event.zone_id:
                    visit.current_zone_id = None

                v_event = VisitEvent(
                    event_id=str(uuid.uuid4()),
                    visit_id=visit.visit_id,
                    customer_id=visit.customer_id,
                    camera_id=cam_id,
                    event_type="zone_exit",
                    timestamp=current_time,
                    zone_id=event.zone_id,
                    zone_name=event.zone_name,
                    dwell_seconds=event.dwell_seconds,
                )
                visit.journey_events.append(v_event)
                return v_event

            return None

    def handle_tracking_loss(self, camera_id: str, tracker_id: int, timestamp: float) -> Optional[VisitEvent]:
        """Record detection dropout.

        CRITICAL: Tracking loss DOES NOT end the store visit. It simply logs
        that the customer is unobserved (e.g. occlusion or blind spot).
        """
        with self._lock:
            tracker_key = (camera_id, tracker_id)
            active_visit_id = self._tracker_to_visit.get(tracker_key)
            if not active_visit_id:
                return None

            visit = self._visits.get(active_visit_id)
            if not visit or visit.status != VisitStatus.ACTIVE:
                return None

            v_event = VisitEvent(
                event_id=str(uuid.uuid4()),
                visit_id=visit.visit_id,
                customer_id=visit.customer_id,
                camera_id=camera_id,
                event_type="tracking_lost",
                timestamp=timestamp,
            )
            visit.journey_events.append(v_event)
            return v_event

    def handle_tracking_resumed(self, camera_id: str, tracker_id: int, timestamp: float) -> Optional[VisitEvent]:
        """Record customer re-observation after temporary loss."""
        with self._lock:
            tracker_key = (camera_id, tracker_id)
            active_visit_id = self._tracker_to_visit.get(tracker_key)
            if not active_visit_id:
                return None

            visit = self._visits.get(active_visit_id)
            if not visit or visit.status != VisitStatus.ACTIVE:
                return None

            visit.last_seen_time = timestamp
            v_event = VisitEvent(
                event_id=str(uuid.uuid4()),
                visit_id=visit.visit_id,
                customer_id=visit.customer_id,
                camera_id=camera_id,
                event_type="tracking_resumed",
                timestamp=timestamp,
            )
            visit.journey_events.append(v_event)
            return v_event

    def check_inactivity_timeouts(self, current_timestamp: float) -> List[CustomerVisit]:
        """Inspect all active visits and mark sessions exceeding inactivity timeout.

        CRITICAL: Inactivity timeout marks the visit as TIMED_OUT, explicitly
        distinguishing observed dwell from estimated dwell, and NOT as a confirmed exit.
        """
        timed_out_visits: List[CustomerVisit] = []
        with self._lock:
            for visit in list(self._visits.values()):
                if visit.status == VisitStatus.ACTIVE:
                    inactive_seconds = current_timestamp - visit.last_seen_time
                    if inactive_seconds >= self.timeout_seconds:
                        visit.status = VisitStatus.TIMED_OUT
                        # Duration capped at last observed time
                        visit.duration_seconds = max(0.0, visit.last_seen_time - visit.entry_time)

                        # Clean up active references
                        self._customer_to_active_visit.pop(visit.customer_id, None)
                        # Remove tracker mappings referencing this visit
                        self._tracker_to_visit = {
                            k: v for k, v in self._tracker_to_visit.items() if v != visit.visit_id
                        }

                        timed_out_visits.append(visit)
                        logger.info(
                            f"Visit {visit.visit_id} for customer {visit.customer_id} timed out "
                            f"after {inactive_seconds:.1f}s of inactivity."
                        )

        return timed_out_visits

    def end_incomplete_sessions(self, final_timestamp: float) -> List[CustomerVisit]:
        """Mark remaining active sessions as INCOMPLETE when stream/pipeline concludes."""
        incomplete: List[CustomerVisit] = []
        with self._lock:
            for visit in list(self._visits.values()):
                if visit.status == VisitStatus.ACTIVE:
                    visit.status = VisitStatus.INCOMPLETE
                    visit.duration_seconds = max(0.0, final_timestamp - visit.entry_time)
                    self._customer_to_active_visit.pop(visit.customer_id, None)
                    incomplete.append(visit)

            self._tracker_to_visit.clear()

        return incomplete

    def get_visit(self, visit_id: str) -> Optional[CustomerVisit]:
        with self._lock:
            return self._visits.get(visit_id)

    def get_active_visit_by_customer(self, customer_id: str) -> Optional[CustomerVisit]:
        with self._lock:
            visit_id = self._customer_to_active_visit.get(customer_id)
            return self._visits.get(visit_id) if visit_id else None

    def get_customer_history(self, customer_id: str) -> List[CustomerVisit]:
        with self._lock:
            visit_ids = self._customer_history.get(customer_id, [])
            return [self._visits[vid] for vid in visit_ids if vid in self._visits]

    def get_all_visits(self) -> List[CustomerVisit]:
        with self._lock:
            return list(self._visits.values())

    def record_persisted_visit(self, visit: CustomerVisit) -> None:
        """Register a visit in the in-memory cache."""
        with self._lock:
            self._visits[visit.visit_id] = visit
            if visit.customer_id not in self._customer_history:
                self._customer_history[visit.customer_id] = []
            if visit.visit_id not in self._customer_history[visit.customer_id]:
                self._customer_history[visit.customer_id].append(visit.visit_id)

    async def list_visits_from_db(
        self,
        session: AsyncSession,
        camera_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[CustomerVisitModel], int, int, int]:
        """Fetch paginated customer visits and status counts from PostgreSQL."""
        filters = []
        if camera_id:
            filters.append(CustomerVisitModel.camera_id == camera_id)
        if customer_id:
            filters.append(CustomerVisitModel.customer_id == customer_id)
        if status:
            filters.append(CustomerVisitModel.status == status)

        # Count total, active, completed
        base_where = and_(*filters) if filters else True

        total_stmt = select(func.count(CustomerVisitModel.id)).where(base_where)
        active_stmt = select(func.count(CustomerVisitModel.id)).where(
            and_(*(filters + [CustomerVisitModel.status == "active"])) if filters else (CustomerVisitModel.status == "active")
        )
        completed_stmt = select(func.count(CustomerVisitModel.id)).where(
            and_(*(filters + [CustomerVisitModel.status == "completed"])) if filters else (CustomerVisitModel.status == "completed")
        )

        total_count = (await session.execute(total_stmt)).scalar() or 0
        active_count = (await session.execute(active_stmt)).scalar() or 0
        completed_count = (await session.execute(completed_stmt)).scalar() or 0

        # Query paginated rows
        stmt = (
            select(CustomerVisitModel)
            .where(base_where)
            .order_by(CustomerVisitModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        visits = list(result.scalars().all())

        return visits, total_count, active_count, completed_count

    async def get_visit_detail_from_db(
        self,
        session: AsyncSession,
        visit_id: str,
    ) -> Optional[Tuple[CustomerVisitModel, List[CustomerZoneEventModel]]]:
        """Fetch an individual visit with its complete chronological event timeline."""
        visit = await session.get(CustomerVisitModel, visit_id)
        if not visit:
            return None

        stmt = (
            select(CustomerZoneEventModel)
            .where(CustomerZoneEventModel.visit_id == visit_id)
            .order_by(CustomerZoneEventModel.timestamp.asc())
        )
        result = await session.execute(stmt)
        events = list(result.scalars().all())
        return visit, events

    async def get_customer_history_from_db(
        self,
        session: AsyncSession,
        customer_id: str,
    ) -> List[CustomerVisitModel]:
        """Fetch complete visit history for a persistent customer ID."""
        stmt = (
            select(CustomerVisitModel)
            .where(CustomerVisitModel.customer_id == customer_id)
            .order_by(CustomerVisitModel.entry_time.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_journey_analytics_from_db(
        self,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        """Aggregate store-level customer journey analytics, zone dwell metrics, and transitions."""
        total_stmt = select(func.count(CustomerVisitModel.id))
        unique_cust_stmt = select(func.count(func.distinct(CustomerVisitModel.customer_id)))
        avg_dwell_stmt = select(func.avg(CustomerVisitModel.duration_seconds))

        total_visits = (await session.execute(total_stmt)).scalar() or 0
        unique_customers = (await session.execute(unique_cust_stmt)).scalar() or 0
        avg_dwell = (await session.execute(avg_dwell_stmt)).scalar() or 0.0

        # Load visits for zone dwell and transition computation
        stmt = select(CustomerVisitModel.zones_visited, CustomerVisitModel.zone_dwell_times)
        res = await session.execute(stmt)
        rows = res.all()

        zone_stats: Dict[str, Dict[str, float]] = {}
        transitions: Dict[Tuple[str, str], int] = {}

        for zones_visited, dwell_times in rows:
            if isinstance(dwell_times, dict):
                for z_name, d_time in dwell_times.items():
                    if z_name not in zone_stats:
                        zone_stats[z_name] = {"totalVisits": 0, "totalDwell": 0.0}
                    zone_stats[z_name]["totalVisits"] += 1
                    zone_stats[z_name]["totalDwell"] += float(d_time)

            if isinstance(zones_visited, list) and len(zones_visited) > 1:
                for i in range(len(zones_visited) - 1):
                    pair = (zones_visited[i], zones_visited[i + 1])
                    if pair[0] != pair[1]:
                        transitions[pair] = transitions.get(pair, 0) + 1

        zone_dwell_summary = [
            {
                "zoneName": name,
                "totalVisits": int(data["totalVisits"]),
                "avgDwellSeconds": round(data["totalDwell"] / max(1, data["totalVisits"]), 1),
                "totalDwellSeconds": round(data["totalDwell"], 1),
            }
            for name, data in zone_stats.items()
        ]
        zone_dwell_summary.sort(key=lambda x: x["totalVisits"], reverse=True)

        popular_transitions = [
            {"fromZone": k[0], "toZone": k[1], "count": count}
            for k, count in sorted(transitions.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        return {
            "totalVisits": total_visits,
            "uniqueCustomers": unique_customers,
            "avgDwellSeconds": round(float(avg_dwell), 1),
            "zoneDwellSummary": zone_dwell_summary,
            "popularTransitions": popular_transitions,
        }

    async def get_camera_analytics_from_db(
        self,
        session: AsyncSession,
        camera_id: str,
    ) -> Dict[str, Any]:
        """Aggregate analytics specific to a CCTV camera stream."""
        total_stmt = select(func.count(CustomerVisitModel.id)).where(CustomerVisitModel.camera_id == camera_id)
        active_stmt = select(func.count(CustomerVisitModel.id)).where(
            and_(CustomerVisitModel.camera_id == camera_id, CustomerVisitModel.status == "active")
        )
        avg_dwell_stmt = select(func.avg(CustomerVisitModel.duration_seconds)).where(CustomerVisitModel.camera_id == camera_id)
        repeats_stmt = select(func.count(CustomerVisitModel.id)).where(
            and_(CustomerVisitModel.camera_id == camera_id, CustomerVisitModel.is_repeat_visit.is_(True))
        )

        total = (await session.execute(total_stmt)).scalar() or 0
        active = (await session.execute(active_stmt)).scalar() or 0
        avg_dwell = (await session.execute(avg_dwell_stmt)).scalar() or 0.0
        repeats = (await session.execute(repeats_stmt)).scalar() or 0

        return {
            "cameraId": camera_id,
            "totalVisits": total,
            "activeVisits": active,
            "avgDwellSeconds": round(float(avg_dwell), 1),
            "repeatVisits": repeats,
        }

    def clear(self) -> None:
        """Reset state for tests."""
        with self._lock:
            self._entrance_lines.clear()
            self._exit_lines.clear()
            self._tracker_to_visit.clear()
            self._customer_to_active_visit.clear()
            self._visits.clear()
            self._customer_history.clear()
            try:
                from app.services.identity_service import get_identity_service
                get_identity_service().clear()
            except Exception:
                pass


_visit_service: Optional[VisitService] = None


def get_visit_service() -> VisitService:
    """Singleton getter for VisitService."""
    global _visit_service
    if _visit_service is None:
        _visit_service = VisitService()
    return _visit_service
