"""Store Zone and Boundary Crossing Tracking Service.

Provides spatial geometry, polygon-based zone definitions, directional boundary
line-crossing detection, dwell-time calculation, occlusion debouncing, and
event dispatching for retail computer-vision streams.
"""

from dataclasses import dataclass, field
import enum
import logging
import math
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("retailiq.zone_service")


class ZoneType(str, enum.Enum):
    ENTRANCE = "entrance"
    EXIT = "exit"
    AISLE = "aisle"
    DEPARTMENT = "department"
    CHECKOUT = "checkout"
    GENERAL = "general"


class CrossingDirection(str, enum.Enum):
    INGRESS = "ingress"  # Entering through boundary line
    EGRESS = "egress"    # Exiting through boundary line
    UNKNOWN = "unknown"


@dataclass
class StoreZone:
    """Configurable polygon-based store zone."""
    zone_id: str
    name: str
    zone_type: ZoneType
    polygon: List[Tuple[float, float]]  # List of (x, y) vertices
    camera_id: Optional[str] = None
    store_id: Optional[str] = None
    min_dwell_seconds: float = 0.5  # Filter micro-jitter / grazing boundaries

    def __post_init__(self) -> None:
        if len(self.polygon) < 3:
            raise ValueError(f"Zone '{self.name}' must have at least 3 polygon vertices.")
        # Precompute bounding box for O(1) early rejection in point_in_polygon
        xs = [p[0] for p in self.polygon]
        ys = [p[1] for p in self.polygon]
        self._min_x = min(xs)
        self._max_x = max(xs)
        self._min_y = min(ys)
        self._max_y = max(ys)

    def contains_point(self, x: float, y: float) -> bool:
        """Ray-casting algorithm to test whether (x, y) falls inside the polygon."""
        # 1. Bounding box fast-rejection
        if x < self._min_x or x > self._max_x or y < self._min_y or y > self._max_y:
            return False

        # 2. Jordan curve theorem ray casting
        inside = False
        n = len(self.polygon)
        j = n - 1
        for i in range(n):
            xi, yi = self.polygon[i]
            xj, yj = self.polygon[j]

            # Check if point is on a horizontal segment or intersects ray to the right
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
                inside = not inside
            j = i

        return inside


@dataclass
class BoundaryLine:
    """Directional tripwire boundary line segment for entry/exit counting."""
    line_id: str
    name: str
    p1: Tuple[float, float]  # (x1, y1)
    p2: Tuple[float, float]  # (x2, y2)
    line_type: str = "entry_exit"  # 'entry', 'exit', or 'entry_exit'
    camera_id: Optional[str] = None

    def intersects_trajectory(
        self,
        prev_pos: Tuple[float, float],
        curr_pos: Tuple[float, float],
    ) -> Tuple[bool, CrossingDirection]:
        """Check if person movement segment (prev -> curr) intersects this boundary line.

        Returns (intersected, direction) where direction is INGRESS or EGRESS.
        """
        x1, y1 = self.p1
        x2, y2 = self.p2
        x3, y3 = prev_pos
        x4, y4 = curr_pos

        def ccw(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
            return (cy - ay) * (bx - ax) - (by - ay) * (cx - ax)

        d1 = ccw(x1, y1, x2, y2, x3, y3)
        d2 = ccw(x1, y1, x2, y2, x4, y4)
        d3 = ccw(x3, y3, x4, y4, x1, y1)
        d4 = ccw(x3, y3, x4, y4, x2, y2)

        # Segments intersect if endpoints lie on opposite sides
        if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
           ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
            # Determine direction: cross product of line vector (p1 -> p2) and trajectory (p3 -> p4)
            line_dx = x2 - x1
            line_dy = y2 - y1
            traj_dx = x4 - x3
            traj_dy = y4 - y3
            cross = line_dx * traj_dy - line_dy * traj_dx
            # Positive cross product = Left-to-Right crossing (Ingress), Negative = Right-to-Left (Egress)
            direction = CrossingDirection.INGRESS if cross > 0 else CrossingDirection.EGRESS
            return True, direction

        return False, CrossingDirection.UNKNOWN


@dataclass
class ZoneEvent:
    """Discrete spatial tracking event."""
    event_type: str  # 'zone_enter', 'zone_exit', 'boundary_crossed'
    tracker_id: int
    camera_id: str
    timestamp: float
    frame_idx: int
    zone_id: Optional[str] = None
    zone_name: Optional[str] = None
    dwell_seconds: float = 0.0
    crossing_direction: Optional[CrossingDirection] = None
    line_id: Optional[str] = None


@dataclass
class TrackState:
    """Internal temporal tracking state for a single ByteTrack ID."""
    tracker_id: int
    camera_id: str
    current_zone_id: Optional[str] = None
    current_zone_name: Optional[str] = None
    zone_entered_at: Optional[float] = None
    zone_entered_frame: Optional[int] = None
    last_seen_at: float = 0.0
    last_seen_frame: int = 0
    last_position: Optional[Tuple[float, float]] = None
    missed_frames: int = 0
    # Map of zone_id -> cumulative dwell seconds
    zone_dwell_times: Dict[str, float] = field(default_factory=dict)
    # Set of line_ids crossed to avoid duplicate jitter
    crossed_lines: Set[str] = field(default_factory=set)


class ZoneService:
    """Multi-camera store zone tracking service.

    Maintains active track states, detects zone entries/exits, calculates
    zone dwell durations, handles occlusion dropouts, and prevents duplicate triggers.
    """

    def __init__(
        self,
        max_missed_frames: int = 25,  # ~1.0 - 1.5 seconds tolerance for occlusion
        min_zone_dwell_seconds: float = 0.5,
    ) -> None:
        self.max_missed_frames = max_missed_frames
        self.min_zone_dwell_seconds = min_zone_dwell_seconds
        # Registered zones: camera_id -> List[StoreZone]
        self._zones: Dict[str, List[StoreZone]] = {}
        # Registered boundary lines: camera_id -> List[BoundaryLine]
        self._lines: Dict[str, List[BoundaryLine]] = {}
        # Active track states: (camera_id, tracker_id) -> TrackState
        self._tracks: Dict[Tuple[str, int], TrackState] = {}

    def register_zone(self, zone: StoreZone) -> None:
        """Register a polygon-based store zone."""
        cam_id = zone.camera_id or "default"
        if cam_id not in self._zones:
            self._zones[cam_id] = []
        # Prevent duplicate zone IDs for the same camera
        self._zones[cam_id] = [z for z in self._zones[cam_id] if z.zone_id != zone.zone_id]
        self._zones[cam_id].append(zone)

    def register_boundary_line(self, line: BoundaryLine) -> None:
        """Register a tripwire boundary line."""
        cam_id = line.camera_id or "default"
        if cam_id not in self._lines:
            self._lines[cam_id] = []
        self._lines[cam_id] = [l for l in self._lines[cam_id] if l.line_id != line.line_id]
        self._lines[cam_id].append(line)

    def get_zones(self, camera_id: str = "default") -> List[StoreZone]:
        """Return registered zones for a camera."""
        return self._zones.get(camera_id, [])

    def get_boundary_lines(self, camera_id: str = "default") -> List[BoundaryLine]:
        """Return registered boundary lines for a camera."""
        return self._lines.get(camera_id, [])

    def clear(self, camera_id: Optional[str] = None) -> None:
        """Reset tracks and optionally zones for a camera or all cameras."""
        if camera_id is not None:
            self._zones.pop(camera_id, None)
            self._lines.pop(camera_id, None)
            self._tracks = {k: v for k, v in self._tracks.items() if k[0] != camera_id}
        else:
            self._zones.clear()
            self._lines.clear()
            self._tracks.clear()

    @staticmethod
    def get_foot_position(box_xyxy: Tuple[float, float, float, float]) -> Tuple[float, float]:
        """Extract person ground foot point from bounding box (x1, y1, x2, y2)."""
        x1, y1, x2, y2 = box_xyxy
        foot_x = (x1 + x2) / 2.0
        foot_y = y2
        return foot_x, foot_y

    def update_track(
        self,
        tracker_id: int,
        box_xyxy: Tuple[float, float, float, float],
        frame_idx: int,
        timestamp: float,
        camera_id: str = "default",
    ) -> List[ZoneEvent]:
        """Update track position from person detection box and return emitted zone events.

        Args:
            tracker_id: Local ByteTrack tracker ID.
            box_xyxy: (x1, y1, x2, y2) bounding box.
            frame_idx: Video frame index.
            timestamp: Video timestamp in seconds.
            camera_id: CCTV camera identifier.

        Returns:
            List of ZoneEvents triggered in this frame update.
        """
        events: List[ZoneEvent] = []
        foot_pos = self.get_foot_position(box_xyxy)
        key = (camera_id, tracker_id)

        # Retrieve or initialize track state
        if key not in self._tracks:
            state = TrackState(
                tracker_id=tracker_id,
                camera_id=camera_id,
                last_seen_at=timestamp,
                last_seen_frame=frame_idx,
                last_position=foot_pos,
            )
            self._tracks[key] = state
        else:
            state = self._tracks[key]
            state.missed_frames = 0

        prev_pos = state.last_position
        state.last_position = foot_pos
        state.last_seen_at = timestamp
        state.last_seen_frame = frame_idx

        # 1. Boundary Tripwire Line Crossing Detection
        if prev_pos is not None:
            lines = self._lines.get(camera_id, [])
            for line in lines:
                crossed, direction = line.intersects_trajectory(prev_pos, foot_pos)
                if crossed:
                    # Prevent rapid oscillation on boundary
                    crossing_key = f"{line.line_id}_{direction.value}"
                    if crossing_key not in state.crossed_lines:
                        state.crossed_lines.add(crossing_key)
                        events.append(
                            ZoneEvent(
                                event_type="boundary_crossed",
                                tracker_id=tracker_id,
                                camera_id=camera_id,
                                timestamp=timestamp,
                                frame_idx=frame_idx,
                                line_id=line.line_id,
                                crossing_direction=direction,
                            )
                        )

        # 2. Polygon Zone Membership Detection
        zones = self._zones.get(camera_id, [])
        matched_zone: Optional[StoreZone] = None
        for zone in zones:
            if zone.contains_point(foot_pos[0], foot_pos[1]):
                matched_zone = zone
                break

        current_zone_id = state.current_zone_id
        new_zone_id = matched_zone.zone_id if matched_zone else None
        new_zone_name = matched_zone.name if matched_zone else None

        # Transition Case A: Moved to a different zone or exited previous zone
        if new_zone_id != current_zone_id:
            # Emit zone_exit for previous zone if minimum dwell threshold was met
            if current_zone_id is not None and state.zone_entered_at is not None:
                dwell = max(0.0, timestamp - state.zone_entered_at)
                state.zone_dwell_times[current_zone_id] = (
                    state.zone_dwell_times.get(current_zone_id, 0.0) + dwell
                )
                if dwell >= self.min_zone_dwell_seconds:
                    events.append(
                        ZoneEvent(
                            event_type="zone_exit",
                            tracker_id=tracker_id,
                            camera_id=camera_id,
                            zone_id=current_zone_id,
                            zone_name=state.current_zone_name,
                            timestamp=timestamp,
                            frame_idx=frame_idx,
                            dwell_seconds=round(dwell, 2),
                        )
                    )

            # Emit zone_enter for new zone
            if new_zone_id is not None and matched_zone is not None:
                state.current_zone_id = new_zone_id
                state.current_zone_name = new_zone_name
                state.zone_entered_at = timestamp
                state.zone_entered_frame = frame_idx

                events.append(
                    ZoneEvent(
                        event_type="zone_enter",
                        tracker_id=tracker_id,
                        camera_id=camera_id,
                        zone_id=new_zone_id,
                        zone_name=new_zone_name,
                        timestamp=timestamp,
                        frame_idx=frame_idx,
                    )
                )
            else:
                state.current_zone_id = None
                state.current_zone_name = None
                state.zone_entered_at = None
                state.zone_entered_frame = None

        return events

    def handle_missed_detections(
        self,
        current_frame: int,
        current_timestamp: float,
        camera_id: str = "default",
        active_tracker_ids: Optional[Set[int]] = None,
    ) -> List[ZoneEvent]:
        """Check for tracks missing in current frame.

        Maintains zone occupancy during temporary occlusion. Emits zone_exit
        only when missed frames exceed max_missed_frames threshold.
        """
        events: List[ZoneEvent] = []
        active_ids = active_tracker_ids or set()
        keys_to_remove: List[Tuple[str, int]] = []

        for (cam, tid), state in self._tracks.items():
            if cam != camera_id:
                continue

            if tid not in active_ids:
                state.missed_frames += 1

                # If missed frames exceeded threshold, conclude track & close active zone
                if state.missed_frames > self.max_missed_frames:
                    if state.current_zone_id is not None and state.zone_entered_at is not None:
                        dwell = max(0.0, state.last_seen_at - state.zone_entered_at)
                        state.zone_dwell_times[state.current_zone_id] = (
                            state.zone_dwell_times.get(state.current_zone_id, 0.0) + dwell
                        )
                        if dwell >= self.min_zone_dwell_seconds:
                            events.append(
                                ZoneEvent(
                                    event_type="zone_exit",
                                    tracker_id=tid,
                                    camera_id=cam,
                                    zone_id=state.current_zone_id,
                                    zone_name=state.current_zone_name,
                                    timestamp=state.last_seen_at,
                                    frame_idx=state.last_seen_frame,
                                    dwell_seconds=round(dwell, 2),
                                )
                            )
                        state.current_zone_id = None
                        state.zone_entered_at = None
                    keys_to_remove.append((cam, tid))

        for k in keys_to_remove:
            self._tracks.pop(k, None)

        return events

    def end_video(self, final_timestamp: float, camera_id: str = "default") -> List[ZoneEvent]:
        """Flush all remaining tracks at video stream conclusion."""
        events: List[ZoneEvent] = []
        keys_to_remove = [k for k in self._tracks.keys() if k[0] == camera_id]

        for k in keys_to_remove:
            state = self._tracks[k]
            if state.current_zone_id is not None and state.zone_entered_at is not None:
                dwell = max(0.0, state.last_seen_at - state.zone_entered_at)
                state.zone_dwell_times[state.current_zone_id] = (
                    state.zone_dwell_times.get(state.current_zone_id, 0.0) + dwell
                )
                events.append(
                    ZoneEvent(
                        event_type="zone_exit",
                        tracker_id=state.tracker_id,
                        camera_id=camera_id,
                        zone_id=state.current_zone_id,
                        zone_name=state.current_zone_name,
                        timestamp=state.last_seen_at,
                        frame_idx=state.last_seen_frame,
                        dwell_seconds=round(dwell, 2),
                    )
                )
            self._tracks.pop(k, None)

        return events

    def get_track_dwell_summary(self, camera_id: str, tracker_id: int) -> Dict[str, float]:
        """Return cumulative dwell seconds per zone for a track."""
        state = self._tracks.get((camera_id, tracker_id))
        if not state:
            return {}
        return dict(state.zone_dwell_times)


_zone_service: Optional[ZoneService] = None


def get_zone_service() -> ZoneService:
    """Singleton getter for ZoneService."""
    global _zone_service
    if _zone_service is None:
        _zone_service = ZoneService()
    return _zone_service
