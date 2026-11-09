"""Shelf Monitoring, Product Tracking, Customer-Shelf Interaction & Temporal Pickup/Return Service.

Implements:
- Polygon-based shelf zone definition and geometric occupancy calculation.
- Product detection and tracking inside shelf zones across consecutive video frames.
- Customer approach and reaching interaction detection.
- Temporal pickup state machine (candidate, confirmed, rejected, uncertain).
- Temporal return state machine with pickup linkage.
- Employee restocking differentiation.
- Unified retail event emission and daily visitor identity association.
"""

from dataclasses import dataclass, field
import datetime
import enum
import logging
import math
import threading
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

logger = logging.getLogger("retailiq.shelf_service")


class ShelfEventStatus(str, enum.Enum):
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"


@dataclass
class ShelfBay:
    """Configurable retail shelf bay with polygon boundaries and product capacity."""
    shelf_id: str
    store_id: str
    camera_id: str
    name: str
    aisle: str
    tier_count: int
    polygon: List[Tuple[float, float]]  # [(x1, y1), (x2, y2), ...]
    interaction_polygon: Optional[List[Tuple[float, float]]] = None
    configured_capacity: int = 20
    product_classes: List[str] = field(default_factory=lambda: ["bottle", "cup", "can", "packaged_good"])

    def __post_init__(self) -> None:
        if len(self.polygon) < 3:
            raise ValueError(f"Shelf polygon for '{self.name}' must have at least 3 vertices.")
        xs = [p[0] for p in self.polygon]
        ys = [p[1] for p in self.polygon]
        self._min_x, self._max_x = min(xs), max(xs)
        self._min_y, self._max_y = min(ys), max(ys)

        # Precompute interaction bounding box if interaction polygon provided
        if self.interaction_polygon and len(self.interaction_polygon) >= 3:
            ixs = [p[0] for p in self.interaction_polygon]
            iys = [p[1] for p in self.interaction_polygon]
            self._int_min_x, self._int_max_x = min(ixs), max(ixs)
            self._int_min_y, self._int_max_y = min(iys), max(iys)
        else:
            # Default interaction zone: expanded bounding box by 50px around shelf
            self._int_min_x = self._min_x - 50.0
            self._int_max_x = self._max_x + 50.0
            self._int_min_y = self._min_y - 20.0
            self._int_max_y = self._max_y + 80.0

    def contains_point(self, x: float, y: float) -> bool:
        """Ray-casting algorithm to test whether (x, y) is inside the shelf polygon."""
        if x < self._min_x or x > self._max_x or y < self._min_y or y > self._max_y:
            return False
        inside = False
        n = len(self.polygon)
        j = n - 1
        for i in range(n):
            xi, yi = self.polygon[i]
            xj, yj = self.polygon[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
                inside = not inside
            j = i
        return inside

    def in_interaction_zone(self, x: float, y: float) -> bool:
        """Test whether customer coordinates fall within the approach/interaction area."""
        if x < self._int_min_x or x > self._int_max_x or y < self._int_min_y or y > self._int_max_y:
            return False
        if not self.interaction_polygon:
            return True
        inside = False
        n = len(self.interaction_polygon)
        j = n - 1
        for i in range(n):
            xi, yi = self.interaction_polygon[i]
            xj, yj = self.interaction_polygon[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
                inside = not inside
            j = i
        return inside


@dataclass
class ShelfProductItem:
    """Tracked product unit inside a shelf zone."""
    item_id: str
    product_class: str
    center: Tuple[float, float]
    box_xyxy: Tuple[float, float, float, float]
    first_seen_frame: int
    last_seen_frame: int
    consecutive_missing_frames: int = 0
    is_stable: bool = False


@dataclass
class PickupCandidate:
    """Temporal candidate state for product pickup."""
    candidate_id: str
    shelf_id: str
    item_id: str
    product_class: str
    original_position: Tuple[float, float]
    initial_timestamp: float
    initial_frame: int
    visitor_id: Optional[str]
    session_id: Optional[str]
    camera_id: str
    customer_tracker_id: Optional[int]
    confidence: float
    status: ShelfEventStatus = ShelfEventStatus.CANDIDATE
    frames_missing: int = 0


@dataclass
class ReturnCandidate:
    """Temporal candidate state for product return."""
    candidate_id: str
    shelf_id: str
    item_id: str
    product_class: str
    position: Tuple[float, float]
    initial_timestamp: float
    initial_frame: int
    visitor_id: Optional[str]
    session_id: Optional[str]
    camera_id: str
    customer_tracker_id: Optional[int]
    confidence: float
    status: ShelfEventStatus = ShelfEventStatus.CANDIDATE
    frames_present: int = 0
    matched_pickup_id: Optional[str] = None


@dataclass
class ShelfState:
    """Dynamic runtime state of a shelf bay."""
    bay: ShelfBay
    current_occupancy: int = 0
    smoothed_occupancy: float = 0.0
    fill_percentage: int = 0
    status: str = "ok"  # "ok", "low", "critical"
    empty_positions: int = 0
    active_products: Dict[str, ShelfProductItem] = field(default_factory=dict)
    active_customers_in_zone: Set[int] = field(default_factory=set)  # tracker_ids
    reaching_customers: Set[int] = field(default_factory=set)  # tracker_ids
    open_pickup_candidates: Dict[str, PickupCandidate] = field(default_factory=dict)
    open_return_candidates: Dict[str, ReturnCandidate] = field(default_factory=dict)
    last_updated_timestamp: float = 0.0


@dataclass
class RetailEvent:
    """Standardized event emitted by RetailIQ intelligence pipeline."""
    event_id: str
    store_id: str
    camera_id: str
    event_type: str
    timestamp: float
    confidence: float = 1.0
    confirmation_status: str = "confirmed"  # "candidate", "confirmed", "rejected", "uncertain"
    visitor_id: Optional[str] = None
    session_id: Optional[str] = None
    shelf_id: Optional[str] = None
    zone_id: Optional[str] = None
    product_id: Optional[str] = None
    product_class: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    related_event_id: Optional[str] = None
    idempotency_key: Optional[str] = None


class ShelfService:
    """Service managing shelf zones, occupancy, customer interaction, and pickup/return state machines."""

    CONFIRMATION_FRAMES = 5  # Number of frames product must stay absent/present to confirm
    OCCLUSION_TOLERANCE_FRAMES = 3  # Frames allowed before treating missing box as pickup candidate
    MAX_REACHING_DISTANCE = 40.0  # Pixel distance threshold between customer upper box and shelf

    def __init__(self, smoothing_alpha: float = 0.3) -> None:
        self.smoothing_alpha = smoothing_alpha
        self._lock = threading.Lock()
        # Registered shelf bays: (store_id, shelf_id) -> ShelfState
        self._shelves: Dict[Tuple[str, str], ShelfState] = {}
        # Chronological confirmed events
        self._events: List[RetailEvent] = []
        # Index of verified pickups for return linkage: (shelf_id, product_class) -> List[RetailEvent]
        self._confirmed_pickups: List[RetailEvent] = []

    def register_shelf_bay(self, bay: ShelfBay) -> None:
        """Register a physical shelf bay for continuous tracking."""
        with self._lock:
            key = (bay.store_id, bay.shelf_id)
            self._shelves[key] = ShelfState(bay=bay)

    def get_shelf_state(self, store_id: str, shelf_id: str) -> Optional[ShelfState]:
        with self._lock:
            return self._shelves.get((store_id, shelf_id))

    def list_shelves(self, store_id: str = "store-104", status_filter: Optional[str] = None) -> List[ShelfState]:
        with self._lock:
            results = [s for (s_id, _), s in self._shelves.items() if s_id == store_id]
            if status_filter and status_filter != "all":
                results = [s for s in results if s.status == status_filter]
            return results

    def process_frame_shelf_analytics(
        self,
        store_id: str,
        camera_id: str,
        frame_idx: int,
        timestamp: float,
        detected_products: List[Tuple[str, float, Tuple[float, float, float, float]]],
        # List of (class_name, confidence, (x1, y1, x2, y2))
        detected_persons: List[Tuple[int, Tuple[float, float, float, float], Optional[str], Optional[str]]],
        # List of (tracker_id, (x1, y1, x2, y2), visitor_id, session_id)
    ) -> List[RetailEvent]:
        """Evaluate spatial shelf occupancy, customer interaction, and pickup/return state machines."""
        emitted_events: List[RetailEvent] = []

        with self._lock:
            target_shelves = [
                s for (s_id, _), s in self._shelves.items()
                if s_id == store_id and s.bay.camera_id == camera_id
            ]

            for shelf_state in target_shelves:
                bay = shelf_state.bay
                shelf_id = bay.shelf_id

                # -------------------------------------------------------------
                # 1. Evaluate Customer Proximity & Reaching Interaction
                # -------------------------------------------------------------
                current_in_zone_trackers: Set[int] = set()
                current_reaching_trackers: Set[int] = set()
                tracker_to_visitor: Dict[int, Tuple[Optional[str], Optional[str]]] = {}

                for tracker_id, p_box, v_id, s_id in detected_persons:
                    px1, py1, px2, py2 = p_box
                    foot_x = (px1 + px2) / 2.0
                    foot_y = py2
                    hand_center_y = py1 + (py2 - py1) * 0.4  # Upper torso / hand reach height
                    tracker_to_visitor[tracker_id] = (v_id, s_id)

                    # A. Approach Check (foot or center inside interaction polygon)
                    if bay.in_interaction_zone(foot_x, foot_y) or bay.in_interaction_zone((px1 + px2) / 2.0, hand_center_y):
                        current_in_zone_trackers.add(tracker_id)

                        # B. Reaching Check (customer box intersects or approaches shelf bay)
                        # Test if any edge of customer bounding box penetrates or is within MAX_REACHING_DISTANCE of shelf
                        overlap_x = max(0.0, min(px2, bay._max_x) - max(px1, bay._min_x))
                        overlap_y = max(0.0, min(py2, bay._max_y) - max(py1, bay._min_y))
                        is_reaching = (overlap_x > 0 and overlap_y > 0) or (
                            abs(foot_x - (bay._min_x + bay._max_x) / 2.0) < (bay._max_x - bay._min_x) / 2.0 + 30.0
                            and abs(hand_center_y - (bay._min_y + bay._max_y) / 2.0) < (bay._max_y - bay._min_y) / 2.0 + 30.0
                        )

                        if is_reaching:
                            current_reaching_trackers.add(tracker_id)

                # Emit customer approach events
                for tracker_id in current_in_zone_trackers - shelf_state.active_customers_in_zone:
                    v_id, s_id = tracker_to_visitor.get(tracker_id, (None, None))
                    ev = RetailEvent(
                        event_id=f"ev-appr-{uuid.uuid4().hex[:8]}",
                        store_id=store_id,
                        camera_id=camera_id,
                        event_type="customer_approached_shelf",
                        timestamp=timestamp,
                        shelf_id=shelf_id,
                        visitor_id=v_id,
                        session_id=s_id,
                        evidence={"tracker_id": tracker_id, "frame_idx": frame_idx},
                    )
                    emitted_events.append(ev)

                # Emit customer reaching events
                for tracker_id in current_reaching_trackers - shelf_state.reaching_customers:
                    v_id, s_id = tracker_to_visitor.get(tracker_id, (None, None))
                    ev = RetailEvent(
                        event_id=f"ev-rch-{uuid.uuid4().hex[:8]}",
                        store_id=store_id,
                        camera_id=camera_id,
                        event_type="customer_reached_shelf",
                        timestamp=timestamp,
                        shelf_id=shelf_id,
                        visitor_id=v_id,
                        session_id=s_id,
                        evidence={"tracker_id": tracker_id, "frame_idx": frame_idx},
                    )
                    emitted_events.append(ev)

                shelf_state.active_customers_in_zone = current_in_zone_trackers
                shelf_state.reaching_customers = current_reaching_trackers

                # -------------------------------------------------------------
                # 2. Product Detection & Geometric Occupancy Calculation
                # -------------------------------------------------------------
                matched_in_shelf_products: Dict[str, Tuple[str, Tuple[float, float], Tuple[float, float, float, float]]] = {}

                for idx, (p_class, p_conf, p_box) in enumerate(detected_products):
                    x1, y1, x2, y2 = p_box
                    cx = (x1 + x2) / 2.0
                    cy = (y1 + y2) / 2.0

                    # Item must fall inside the shelf polygon
                    if bay.contains_point(cx, cy):
                        # Unique spatial key per product detection in shelf
                        grid_x = int((cx - bay._min_x) / 15.0)
                        grid_y = int((cy - bay._min_y) / 15.0)
                        spatial_key = f"{p_class}-g{grid_x}_{grid_y}_{idx}"
                        matched_in_shelf_products[spatial_key] = (p_class, (cx, cy), p_box)

                observed_count = len(matched_in_shelf_products)

                # Temporal smoothing (Exponential Moving Average)
                if shelf_state.smoothed_occupancy == 0.0:
                    shelf_state.smoothed_occupancy = float(observed_count)
                else:
                    shelf_state.smoothed_occupancy = (
                        self.smoothing_alpha * float(observed_count)
                        + (1.0 - self.smoothing_alpha) * shelf_state.smoothed_occupancy
                    )

                shelf_state.current_occupancy = round(shelf_state.smoothed_occupancy)
                cap = max(1, bay.configured_capacity)
                shelf_state.fill_percentage = min(100, int((shelf_state.current_occupancy / cap) * 100))
                shelf_state.empty_positions = max(0, bay.configured_capacity - shelf_state.current_occupancy)

                # Categorize stock status
                prev_status = shelf_state.status
                if shelf_state.fill_percentage < 40:
                    shelf_state.status = "critical"
                elif shelf_state.fill_percentage <= 70:
                    shelf_state.status = "low"
                else:
                    shelf_state.status = "ok"

                if prev_status != shelf_state.status:
                    if shelf_state.status == "critical":
                        ev_type = "shelf_out_of_stock" if shelf_state.fill_percentage == 0 else "shelf_low_stock"
                    elif shelf_state.status == "low":
                        ev_type = "shelf_low_stock"
                    else:
                        ev_type = "shelf_occupancy_changed"

                    emitted_events.append(
                        RetailEvent(
                            event_id=f"ev-st-{uuid.uuid4().hex[:8]}",
                            store_id=store_id,
                            camera_id=camera_id,
                            event_type=ev_type,
                            timestamp=timestamp,
                            shelf_id=shelf_id,
                            evidence={
                                "fillPercentage": shelf_state.fill_percentage,
                                "currentOccupancy": shelf_state.current_occupancy,
                                "emptyPositions": shelf_state.empty_positions,
                            },
                        )
                    )

                # -------------------------------------------------------------
                # 3. Temporal Product Tracking & Return Candidate Detection
                # -------------------------------------------------------------
                for spatial_key, (p_class, center, p_box) in matched_in_shelf_products.items():
                    if spatial_key in shelf_state.active_products:
                        item = shelf_state.active_products[spatial_key]
                        item.last_seen_frame = frame_idx
                        item.consecutive_missing_frames = 0
                        if (frame_idx - item.first_seen_frame) >= self.CONFIRMATION_FRAMES:
                            item.is_stable = True
                    elif spatial_key in shelf_state.open_return_candidates:
                        # Ongoing candidate handled below
                        pass
                    else:
                        # New item appeared in shelf: check if customer is interacting (skip initial inventory frames <= 2)
                        if frame_idx > 2 and (shelf_state.reaching_customers or shelf_state.active_customers_in_zone):
                            int_tid = list(shelf_state.reaching_customers)[0] if shelf_state.reaching_customers else list(shelf_state.active_customers_in_zone)[0]
                            v_id, s_id = tracker_to_visitor.get(int_tid, (None, None))
                            matched_pk_id = None
                            for pk_ev in reversed(self._confirmed_pickups):
                                if pk_ev.shelf_id == shelf_id and pk_ev.product_class == p_class:
                                    if v_id and pk_ev.visitor_id == v_id:
                                        matched_pk_id = pk_ev.event_id
                                        break
                                    elif matched_pk_id is None:
                                        matched_pk_id = pk_ev.event_id

                            ret_cand = ReturnCandidate(
                                candidate_id=f"ret-cand-{uuid.uuid4().hex[:6]}",
                                shelf_id=shelf_id,
                                item_id=spatial_key,
                                product_class=p_class,
                                position=center,
                                initial_timestamp=timestamp,
                                initial_frame=frame_idx,
                                visitor_id=v_id,
                                session_id=s_id,
                                camera_id=camera_id,
                                customer_tracker_id=int_tid,
                                confidence=0.88,
                                status=ShelfEventStatus.CANDIDATE,
                                frames_present=1,
                                matched_pickup_id=matched_pk_id,
                            )
                            shelf_state.open_return_candidates[spatial_key] = ret_cand
                            emitted_events.append(
                                RetailEvent(
                                    event_id=f"ev-rcan-{uuid.uuid4().hex[:8]}",
                                    store_id=store_id,
                                    camera_id=camera_id,
                                    event_type="product_return_candidate",
                                    timestamp=timestamp,
                                    confidence=ret_cand.confidence,
                                    confirmation_status="candidate",
                                    visitor_id=v_id,
                                    session_id=s_id,
                                    shelf_id=shelf_id,
                                    product_id=spatial_key,
                                    product_class=p_class,
                                    related_event_id=matched_pk_id,
                                    evidence={"position": center, "matchedPickup": matched_pk_id},
                                )
                            )
                        else:
                            # Restocking or initial inventory load: register into active_products
                            shelf_state.active_products[spatial_key] = ShelfProductItem(
                                item_id=spatial_key,
                                product_class=p_class,
                                center=center,
                                box_xyxy=p_box,
                                first_seen_frame=frame_idx,
                                last_seen_frame=frame_idx,
                                is_stable=(frame_idx <= 2),
                            )

                # Progress open return candidates
                for spatial_key, ret_cand in list(shelf_state.open_return_candidates.items()):
                    if spatial_key not in matched_in_shelf_products:
                        ret_cand.status = ShelfEventStatus.REJECTED
                        shelf_state.open_return_candidates.pop(spatial_key, None)
                    else:
                        ret_cand.frames_present += 1
                        if ret_cand.frames_present >= self.CONFIRMATION_FRAMES:
                            ret_cand.status = ShelfEventStatus.CONFIRMED
                            conf_ret_ev = RetailEvent(
                                event_id=f"ev-ret-{uuid.uuid4().hex[:8]}",
                                store_id=store_id,
                                camera_id=camera_id,
                                event_type="product_returned",
                                timestamp=timestamp,
                                confidence=ret_cand.confidence,
                                confirmation_status="confirmed",
                                visitor_id=ret_cand.visitor_id,
                                session_id=ret_cand.session_id,
                                shelf_id=shelf_id,
                                product_id=spatial_key,
                                product_class=ret_cand.product_class,
                                related_event_id=ret_cand.matched_pickup_id,
                                evidence={
                                    "position": ret_cand.position,
                                    "durationFrames": ret_cand.frames_present,
                                },
                            )
                            emitted_events.append(conf_ret_ev)
                            shelf_state.open_return_candidates.pop(spatial_key, None)
                            shelf_state.active_products[spatial_key] = ShelfProductItem(
                                item_id=spatial_key,
                                product_class=ret_cand.product_class,
                                center=ret_cand.position,
                                box_xyxy=(ret_cand.position[0] - 10, ret_cand.position[1] - 10, ret_cand.position[0] + 10, ret_cand.position[1] + 10),
                                first_seen_frame=frame_idx,
                                last_seen_frame=frame_idx,
                                is_stable=True,
                            )

                # -------------------------------------------------------------
                # 4. Temporal Product Pickup State Machine
                # -------------------------------------------------------------
                # Check for stably present items that disappeared in this frame
                for spatial_key, item in list(shelf_state.active_products.items()):
                    if spatial_key not in matched_in_shelf_products:
                        item.consecutive_missing_frames += 1

                        # Candidate trigger: stable item missing + at least one customer was reaching
                        if item.consecutive_missing_frames >= self.OCCLUSION_TOLERANCE_FRAMES:
                            if spatial_key not in shelf_state.open_pickup_candidates and item.is_stable:
                                # Determine interacting customer
                                int_tid = list(shelf_state.reaching_customers)[0] if shelf_state.reaching_customers else None
                                v_id, s_id = tracker_to_visitor.get(int_tid, (None, None)) if int_tid is not None else (None, None)

                                # If multiple customers reaching simultaneously, mark as UNCERTAIN
                                is_ambiguous = len(shelf_state.reaching_customers) > 1
                                cand_status = ShelfEventStatus.UNCERTAIN if is_ambiguous else ShelfEventStatus.CANDIDATE

                                cand = PickupCandidate(
                                    candidate_id=f"pkp-cand-{uuid.uuid4().hex[:6]}",
                                    shelf_id=shelf_id,
                                    item_id=spatial_key,
                                    product_class=item.product_class,
                                    original_position=item.center,
                                    initial_timestamp=timestamp,
                                    initial_frame=frame_idx,
                                    visitor_id=v_id,
                                    session_id=s_id,
                                    camera_id=camera_id,
                                    customer_tracker_id=int_tid,
                                    confidence=0.75 if is_ambiguous else 0.92,
                                    status=cand_status,
                                    frames_missing=item.consecutive_missing_frames,
                                )
                                shelf_state.open_pickup_candidates[spatial_key] = cand

                                # Emit candidate event
                                emitted_events.append(
                                    RetailEvent(
                                        event_id=f"ev-pcan-{uuid.uuid4().hex[:8]}",
                                        store_id=store_id,
                                        camera_id=camera_id,
                                        event_type="product_pickup_candidate",
                                        timestamp=timestamp,
                                        confidence=cand.confidence,
                                        confirmation_status=cand.status.value,
                                        visitor_id=v_id,
                                        session_id=s_id,
                                        shelf_id=shelf_id,
                                        product_id=spatial_key,
                                        product_class=item.product_class,
                                        evidence={"position": item.center, "framesMissing": cand.frames_missing},
                                    )
                                )

                # Progress open pickup candidates
                for spatial_key, cand in list(shelf_state.open_pickup_candidates.items()):
                    if spatial_key in matched_in_shelf_products:
                        # Item reappeared: REJECT pickup candidate (was momentary occlusion or item touched and left)
                        cand.status = ShelfEventStatus.REJECTED
                        shelf_state.open_pickup_candidates.pop(spatial_key, None)
                    else:
                        cand.frames_missing += 1
                        if cand.frames_missing >= (self.CONFIRMATION_FRAMES + self.OCCLUSION_TOLERANCE_FRAMES):
                            # CONFIRM pickup
                            cand.status = ShelfEventStatus.CONFIRMED
                            conf_ev = RetailEvent(
                                event_id=f"ev-pkup-{uuid.uuid4().hex[:8]}",
                                store_id=store_id,
                                camera_id=camera_id,
                                event_type="product_picked_up",
                                timestamp=timestamp,
                                confidence=cand.confidence,
                                confirmation_status="confirmed",
                                visitor_id=cand.visitor_id,
                                session_id=cand.session_id,
                                shelf_id=shelf_id,
                                product_id=spatial_key,
                                product_class=cand.product_class,
                                evidence={
                                    "originalPosition": cand.original_position,
                                    "durationFrames": cand.frames_missing,
                                },
                            )
                            emitted_events.append(conf_ev)
                            self._confirmed_pickups.append(conf_ev)
                            shelf_state.open_pickup_candidates.pop(spatial_key, None)
                            shelf_state.active_products.pop(spatial_key, None)

                shelf_state.last_updated_timestamp = timestamp

            self._events.extend(emitted_events)

        return emitted_events

    def get_timeline_events(
        self,
        store_id: Optional[str] = None,
        camera_id: Optional[str] = None,
        shelf_id: Optional[str] = None,
        visitor_id: Optional[str] = None,
        event_type: Optional[str] = None,
        confirmation_status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[RetailEvent], int]:
        """Query unified event timeline with multifaceted filtering."""
        with self._lock:
            filtered = self._events
            if store_id:
                filtered = [e for e in filtered if e.store_id == store_id]
            if camera_id:
                filtered = [e for e in filtered if e.camera_id == camera_id]
            if shelf_id:
                filtered = [e for e in filtered if e.shelf_id == shelf_id]
            if visitor_id:
                filtered = [e for e in filtered if e.visitor_id == visitor_id]
            if event_type:
                filtered = [e for e in filtered if e.event_type == event_type]
            if confirmation_status:
                filtered = [e for e in filtered if e.confirmation_status == confirmation_status]

            total = len(filtered)
            paginated = sorted(filtered, key=lambda x: x.timestamp, reverse=True)[offset : offset + limit]
            return paginated, total

    def get_shelf_metrics(self, store_id: str = "store-104") -> Dict[str, Any]:
        """Aggregate shelf monitoring metrics."""
        with self._lock:
            shelves = [s for (s_id, _), s in self._shelves.items() if s_id == store_id]
            if not shelves:
                return {
                    "shelfOccupancyPercentage": 0,
                    "emptyPositions": 0,
                    "lowStockCount": 0,
                    "outOfStockCount": 0,
                    "pickupCandidates": 0,
                    "confirmedPickups": 0,
                    "returnCandidates": 0,
                    "confirmedReturns": 0,
                    "customerShelfInteractions": 0,
                }

            total_cap = sum(s.bay.configured_capacity for s in shelves)
            total_occ = sum(s.current_occupancy for s in shelves)
            overall_pct = int((total_occ / max(1, total_cap)) * 100)
            empty_pos = sum(s.empty_positions for s in shelves)
            low_stock = sum(1 for s in shelves if s.status == "low")
            critical_stock = sum(1 for s in shelves if s.status == "critical")

            # Count event occurrences
            pickups = sum(1 for e in self._events if e.store_id == store_id and e.event_type == "product_picked_up")
            pickup_cands = sum(1 for e in self._events if e.store_id == store_id and e.event_type == "product_pickup_candidate")
            returns = sum(1 for e in self._events if e.store_id == store_id and e.event_type == "product_returned")
            return_cands = sum(1 for e in self._events if e.store_id == store_id and e.event_type == "product_return_candidate")
            interactions = sum(
                1 for e in self._events
                if e.store_id == store_id and e.event_type in ("customer_approached_shelf", "customer_reached_shelf")
            )

            return {
                "shelfOccupancyPercentage": overall_pct,
                "emptyPositions": empty_pos,
                "lowStockCount": low_stock,
                "outOfStockCount": critical_stock,
                "pickupCandidates": pickup_cands,
                "confirmedPickups": pickups,
                "returnCandidates": return_cands,
                "confirmedReturns": returns,
                "customerShelfInteractions": interactions,
            }

    def clear(self) -> None:
        """Reset state for tests."""
        with self._lock:
            self._shelves.clear()
            self._events.clear()
            self._confirmed_pickups.clear()


_shelf_service: Optional[ShelfService] = None


def get_shelf_service() -> ShelfService:
    global _shelf_service
    if _shelf_service is None:
        _shelf_service = ShelfService()
    return _shelf_service


def seed_default_supermarket_bays(shelf_service: ShelfService, store_id: str = "store-104", camera_id: str = "cam-main") -> None:
    """Seed standard supermarket shelf bays matching video zones."""
    produce_bay = ShelfBay(
        shelf_id="shelf-produce-1",
        store_id=store_id,
        camera_id=camera_id,
        name="Organic Produce & Fruit Displays",
        aisle="Aisle 1",
        tier_count=3,
        polygon=[(50.0, 50.0), (300.0, 50.0), (300.0, 200.0), (50.0, 200.0)],
        interaction_polygon=[(20.0, 20.0), (330.0, 20.0), (330.0, 260.0), (20.0, 260.0)],
        configured_capacity=24,
        product_classes=["apple", "banana", "orange", "bottle"],
    )
    bakery_bay = ShelfBay(
        shelf_id="shelf-bakery-1",
        store_id=store_id,
        camera_id=camera_id,
        name="Artisan Bakery & Pastry Case",
        aisle="Aisle 2",
        tier_count=3,
        polygon=[(350.0, 50.0), (600.0, 50.0), (600.0, 200.0), (350.0, 200.0)],
        interaction_polygon=[(320.0, 20.0), (630.0, 20.0), (630.0, 260.0), (320.0, 260.0)],
        configured_capacity=20,
        product_classes=["sandwich", "cake", "donut"],
    )
    dairy_bay = ShelfBay(
        shelf_id="shelf-dairy-1",
        store_id=store_id,
        camera_id=camera_id,
        name="Dairy & Refrigerated Beverages",
        aisle="Aisle 3",
        tier_count=4,
        polygon=[(50.0, 250.0), (300.0, 250.0), (300.0, 420.0), (50.0, 420.0)],
        interaction_polygon=[(20.0, 220.0), (330.0, 220.0), (330.0, 460.0), (20.0, 460.0)],
        configured_capacity=30,
        product_classes=["bottle", "cup", "can"],
    )
    packaged_bay = ShelfBay(
        shelf_id="shelf-packaged-1",
        store_id=store_id,
        camera_id=camera_id,
        name="Canned Goods & Dry Pasta Bay",
        aisle="Aisle 4",
        tier_count=3,
        polygon=[(350.0, 250.0), (600.0, 250.0), (600.0, 420.0), (350.0, 420.0)],
        interaction_polygon=[(320.0, 220.0), (630.0, 220.0), (630.0, 460.0), (320.0, 460.0)],
        configured_capacity=25,
        product_classes=["can", "box", "packaged_good"],
    )
    shelf_service.register_shelf_bay(produce_bay)
    shelf_service.register_shelf_bay(bakery_bay)
    shelf_service.register_shelf_bay(dairy_bay)
    shelf_service.register_shelf_bay(packaged_bay)
