"""Unified Customer Intelligence & Daily Visitor Identity Lifecycle Service.

Implements the three-level identity hierarchy:
1. Person detection: Detection bounding box in video frame.
2. Camera-level track: Composite (camera_id + tracker_id + lifetime).
3. Store-day global visitor identity: Scoped strictly to (store_id + local_calendar_date).

Visit sessions represent separate entrance-to-exit journeys. Same-day returning
visitors reuse their daily visitor identity with an incremented visit number and a new session.
New local calendar days generate fresh anonymous identities.
Cross-camera Re-ID is supported using anonymous appearance feature embeddings.
"""

from dataclasses import dataclass, field
import datetime
import enum
import logging
import math
import threading
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid
import zoneinfo

import cv2
import numpy as np

logger = logging.getLogger("retailiq.identity_service")


class ConfirmationStatus(str, enum.Enum):
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"


@dataclass
class AppearanceEmbedding:
    """Anonymized, privacy-preserving visual appearance vector.

    Constructed from normalized multi-tier spatial color histograms (upper torso + lower body).
    Retained strictly during the same-day matching period in memory.
    """
    vector: np.ndarray  # Normalized float32 vector
    created_at: float
    camera_id: str

    def cosine_similarity(self, other: "AppearanceEmbedding") -> float:
        """Compute cosine similarity between two appearance vectors in range [0, 1]."""
        dot = float(np.dot(self.vector, other.vector))
        norm_a = float(np.linalg.norm(self.vector))
        norm_b = float(np.linalg.norm(other.vector))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        sim = dot / (norm_a * norm_b)
        return max(0.0, min(1.0, sim))


@dataclass
class DailyVisitor:
    """Store-day global visitor identity scoped to (store_id, local_calendar_date)."""
    visitor_id: str
    store_id: str
    local_date: str  # YYYY-MM-DD
    anonymous_label: str  # e.g. DVIS-0001
    first_seen_at: float
    last_seen_at: float
    total_visits: int = 1
    total_dwell_seconds: float = 0.0
    cameras_seen: Set[str] = field(default_factory=set)
    active_session_id: Optional[str] = None
    session_ids: List[str] = field(default_factory=list)
    appearance_embeddings: List[AppearanceEmbedding] = field(default_factory=list)

    @property
    def latest_embedding(self) -> Optional[AppearanceEmbedding]:
        return self.appearance_embeddings[-1] if self.appearance_embeddings else None


@dataclass
class TrackCompositeKey:
    """Camera-level track identity."""
    camera_id: str
    tracker_id: int

    def __hash__(self) -> int:
        return hash((self.camera_id, self.tracker_id))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, TrackCompositeKey):
            return False
        return self.camera_id == other.camera_id and self.tracker_id == other.tracker_id


class IdentityService:
    """Thread-safe service managing store-day visitor lifecycles and cross-camera Re-ID."""

    def __init__(
        self,
        default_timezone: str = "Asia/Kolkata",
        reid_similarity_threshold: float = 0.85,
        ambiguity_margin: float = 0.10,
    ) -> None:
        self.default_timezone = default_timezone
        self.reid_similarity_threshold = reid_similarity_threshold
        self.ambiguity_margin = ambiguity_margin
        self._lock = threading.Lock()

        # Counter for anonymous visitor labels per (store_id, local_date): label_seq -> int
        self._daily_counters: Dict[Tuple[str, str], int] = {}

        # Daily visitors: (store_id, local_date, visitor_id) -> DailyVisitor
        self._visitors: Dict[Tuple[str, str, str], DailyVisitor] = {}

        # Active camera track to visitor mapping: (store_id, local_date, camera_id, tracker_id) -> visitor_id
        self._track_to_visitor: Dict[Tuple[str, str, str, int], str] = {}

        # Last observed timestamps per (visitor_id, camera_id) for topological transit checks
        self._visitor_camera_heartbeat: Dict[Tuple[str, str], float] = {}

        # Overlapping camera pairs
        self._overlapping_cameras: Set[Tuple[str, str]] = set()

    def register_overlapping_cameras(self, cam_a: str, cam_b: str) -> None:
        """Register a pair of cameras with overlapping views."""
        with self._lock:
            self._overlapping_cameras.add((cam_a, cam_b))
            self._overlapping_cameras.add((cam_b, cam_a))

    def get_store_local_date(self, store_id: str, tz_name: Optional[str] = None, timestamp: Optional[float] = None) -> str:
        """Calculate store-local calendar date in YYYY-MM-DD based on store IANA timezone."""
        target_tz_str = tz_name or self.default_timezone
        try:
            tz = zoneinfo.ZoneInfo(target_tz_str)
        except Exception:
            tz = zoneinfo.ZoneInfo("Asia/Kolkata")

        if timestamp is not None and timestamp > 1000000000:
            dt = datetime.datetime.fromtimestamp(timestamp, tz=tz)
        else:
            # Relative video timestamp or omitted: evaluate relative to UTC now
            dt = datetime.datetime.now(tz=tz)
        return dt.strftime("%Y-%m-%d")

    def extract_appearance_embedding(
        self,
        frame: Optional[np.ndarray],
        box_xyxy: Tuple[float, float, float, float],
        camera_id: str,
        timestamp: float,
    ) -> Optional[AppearanceEmbedding]:
        """Extract a 128-dimensional normalized spatial-color appearance feature vector.

        Splits person bounding box into upper torso (60%) and lower body (40%) in HSV color
        space. Normalizes vector to unit L2 norm for robust, anonymous cross-camera cosine matching.
        """
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return None

        h, w = frame.shape[:2]
        x1, y1, x2, y2 = [int(v) for v in box_xyxy]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        if x2 - x1 < 10 or y2 - y1 < 10:
            return None

        crop = frame[y1:y2, x1:x2]
        try:
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            crop_h = y2 - y1
            split_y = int(crop_h * 0.6)

            upper_part = hsv[:split_y, :]
            lower_part = hsv[split_y:, :]

            # Upper torso: 8 hue bins x 8 sat bins = 64
            hist_upper = cv2.calcHist([upper_part], [0, 1], None, [8, 8], [0, 180, 0, 256]).flatten()
            # Lower body: 8 hue bins x 8 sat bins = 64
            hist_lower = cv2.calcHist([lower_part], [0, 1], None, [8, 8], [0, 180, 0, 256]).flatten()

            combined = np.concatenate([hist_upper, hist_lower]).astype(np.float32)
            norm = np.linalg.norm(combined)
            if norm > 0:
                combined /= norm

            return AppearanceEmbedding(
                vector=combined,
                created_at=timestamp,
                camera_id=camera_id,
            )
        except Exception as exc:
            logger.debug(f"Failed to extract appearance embedding: {exc}")
            return None

    def create_synthetic_embedding(self, seed: int, camera_id: str = "cam-01", timestamp: float = 0.0) -> AppearanceEmbedding:
        """Generate a deterministic synthetic feature vector for testing."""
        rng = np.random.RandomState(seed)
        vec = rng.randn(128).astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return AppearanceEmbedding(vector=vec, created_at=timestamp, camera_id=camera_id)

    def resolve_or_create_daily_visitor(
        self,
        store_id: str,
        local_date: str,
        camera_id: str,
        tracker_id: int,
        timestamp: float,
        embedding: Optional[AppearanceEmbedding] = None,
        forced_visitor_id: Optional[str] = None,
        is_uncertain: bool = False,
    ) -> Tuple[DailyVisitor, bool, ConfirmationStatus]:
        """Resolve a camera track to a store-day visitor identity or allocate a new one.

        Returns:
            (visitor, is_returning_visitor, confirmation_status)
        """
        with self._lock:
            track_key = (store_id, local_date, camera_id, tracker_id)

            # 1. Check if this camera track is already bound to an active visitor
            existing_vid = self._track_to_visitor.get(track_key)
            if existing_vid:
                visitor_key = (store_id, local_date, existing_vid)
                visitor = self._visitors.get(visitor_key)
                if visitor:
                    visitor.last_seen_at = timestamp
                    visitor.cameras_seen.add(camera_id)
                    if embedding:
                        visitor.appearance_embeddings.append(embedding)
                    self._visitor_camera_heartbeat[(visitor.visitor_id, camera_id)] = timestamp
                    return visitor, False, ConfirmationStatus.CONFIRMED

            # 2. If caller provided explicit match
            if forced_visitor_id:
                visitor_key = (store_id, local_date, forced_visitor_id)
                visitor = self._visitors.get(visitor_key)
                if visitor:
                    visitor.last_seen_at = timestamp
                    visitor.cameras_seen.add(camera_id)
                    if embedding:
                        visitor.appearance_embeddings.append(embedding)
                    self._track_to_visitor[track_key] = visitor.visitor_id
                    self._visitor_camera_heartbeat[(visitor.visitor_id, camera_id)] = timestamp
                    is_return = visitor.active_session_id is None and len(visitor.session_ids) > 0
                    status = ConfirmationStatus.UNCERTAIN if is_uncertain else ConfirmationStatus.CONFIRMED
                    return visitor, is_return, status

            # 3. Multi-Camera Re-ID / Same-Day Return Matching using Appearance Embedding
            matched_visitor: Optional[DailyVisitor] = None
            match_status = ConfirmationStatus.CONFIRMED

            if embedding is not None and not is_uncertain:
                candidates: List[Tuple[float, DailyVisitor]] = []

                for (s_id, l_date, v_id), candidate in self._visitors.items():
                    if s_id != store_id or l_date != local_date:
                        continue

                    # Topological sanity check: If candidate was observed on a different camera at the exact
                    # same timestamp (+- 0.5s) without overlapping view, they cannot be the same physical person
                    simultaneous_conflict = False
                    for (c_vid, c_cam), last_t in self._visitor_camera_heartbeat.items():
                        if c_vid == candidate.visitor_id and c_cam != camera_id:
                            is_overlap = (camera_id, c_cam) in self._overlapping_cameras or (c_cam, camera_id) in self._overlapping_cameras
                            if not is_overlap and abs(timestamp - last_t) < 0.2:
                                simultaneous_conflict = True
                                break

                    if simultaneous_conflict:
                        continue

                    # Compare against candidate's appearance history
                    best_sim = 0.0
                    for cand_emb in candidate.appearance_embeddings:
                        sim = embedding.cosine_similarity(cand_emb)
                        if sim > best_sim:
                            best_sim = sim

                    if best_sim >= self.reid_similarity_threshold:
                        candidates.append((best_sim, candidate))

                if candidates:
                    candidates.sort(key=lambda x: x[0], reverse=True)
                    top_sim, top_cand = candidates[0]

                    # Check for ambiguity: if runner-up is within ambiguity_margin, flag as UNCERTAIN
                    # and do NOT silently merge
                    if len(candidates) > 1 and (top_sim - candidates[1][0]) < self.ambiguity_margin:
                        logger.info(
                            f"Ambiguous Re-ID match for tracker {tracker_id} on {camera_id} between "
                            f"{top_cand.visitor_id} ({top_sim:.3f}) and {candidates[1][1].visitor_id} "
                            f"({candidates[1][0]:.3f}); isolating identity."
                        )
                        match_status = ConfirmationStatus.UNCERTAIN
                    else:
                        matched_visitor = top_cand

            if matched_visitor is not None and match_status == ConfirmationStatus.CONFIRMED:
                matched_visitor.last_seen_at = timestamp
                matched_visitor.cameras_seen.add(camera_id)
                if embedding:
                    matched_visitor.appearance_embeddings.append(embedding)
                self._track_to_visitor[track_key] = matched_visitor.visitor_id
                self._visitor_camera_heartbeat[(matched_visitor.visitor_id, camera_id)] = timestamp
                is_return = matched_visitor.active_session_id is None and len(matched_visitor.session_ids) > 0
                return matched_visitor, is_return, ConfirmationStatus.CONFIRMED

            # 4. Allocate New Daily Visitor Identity scoped to (store_id, local_date)
            counter_key = (store_id, local_date)
            seq = self._daily_counters.get(counter_key, 0) + 1
            self._daily_counters[counter_key] = seq

            clean_date = local_date.replace("-", "")
            visitor_id = f"DVIS-{clean_date}-{uuid.uuid4().hex[:6]}"
            anon_label = f"VIS-{seq:04d}"

            new_visitor = DailyVisitor(
                visitor_id=visitor_id,
                store_id=store_id,
                local_date=local_date,
                anonymous_label=anon_label,
                first_seen_at=timestamp,
                last_seen_at=timestamp,
                total_visits=1,
            )
            new_visitor.cameras_seen.add(camera_id)
            if embedding:
                new_visitor.appearance_embeddings.append(embedding)

            self._visitors[(store_id, local_date, visitor_id)] = new_visitor
            self._track_to_visitor[track_key] = visitor_id
            self._visitor_camera_heartbeat[(visitor_id, camera_id)] = timestamp

            final_status = match_status if match_status == ConfirmationStatus.UNCERTAIN else (ConfirmationStatus.UNCERTAIN if is_uncertain else ConfirmationStatus.CONFIRMED)
            return new_visitor, False, final_status

    def bind_session_to_visitor(self, visitor: DailyVisitor, session_id: str) -> None:
        """Associate an active visit session with the daily visitor."""
        with self._lock:
            visitor.active_session_id = session_id
            if session_id not in visitor.session_ids:
                visitor.session_ids.append(session_id)
                visitor.total_visits = len(visitor.session_ids)

    def close_visitor_session(self, visitor: DailyVisitor, session_id: str, dwell_seconds: float) -> None:
        """Close an active visit session upon verified exit."""
        with self._lock:
            if visitor.active_session_id == session_id:
                visitor.active_session_id = None
            visitor.total_dwell_seconds += max(0.0, dwell_seconds)

    def get_visitor(self, store_id: str, local_date: str, visitor_id: str) -> Optional[DailyVisitor]:
        with self._lock:
            return self._visitors.get((store_id, local_date, visitor_id))

    def list_daily_visitors(self, store_id: str, local_date: str) -> List[DailyVisitor]:
        with self._lock:
            return [
                v for (s, d, _), v in self._visitors.items()
                if s == store_id and d == local_date
            ]

    def clear(self) -> None:
        """Reset state for tests."""
        with self._lock:
            self._daily_counters.clear()
            self._visitors.clear()
            self._track_to_visitor.clear()
            self._visitor_camera_heartbeat.clear()


_identity_service: Optional[IdentityService] = None


def get_identity_service() -> IdentityService:
    global _identity_service
    if _identity_service is None:
        _identity_service = IdentityService()
    return _identity_service
