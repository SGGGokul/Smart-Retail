import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from app.core.config import get_settings
from app.schemas.video import VideoBox, VideoDetectionBox
from app.services.visit_service import CustomerVisit, VisitEvent, VisitService, VisitStatus
from app.services.zone_service import (
    BoundaryLine,
    CrossingDirection,
    StoreZone,
    ZoneEvent,
    ZoneService,
    ZoneType,
)

logger = logging.getLogger("retailiq.cv_service")

# Prevent Ultralytics auto-telemetry or permission warnings
os.environ.setdefault("YOLO_OFFLINE", "1")


class CVService:
    """Reusable Computer Vision service providing YOLO11n person detection,

    ByteTrack tracking, occupancy, dwell time, and configurable entry/exit zones.
    Reuses algorithms from:
      - run_merl_batch.py
      - customer_count.py
      - customer_dwell_time.py
      - customer_occupancy.py
      - entry_exit_counter.py
    """

    def __init__(self, model_path: Optional[Path] = None) -> None:
        settings = get_settings()
        self.model_path = model_path if model_path is not None else settings.MODEL_PATH

    def process_video(
        self,
        video_path: Path,
        confidence: Optional[float] = None,
        min_track_seconds: Optional[float] = None,
        zone_coords: Optional[Tuple[int, int, int, int]] = None,
        camera_id: str = "cam-main",
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Any]:
        """Process video through YOLO11n + ByteTrack with isolated tracker state.

        Args:
            video_path: Path to target video file.
            confidence: Detection confidence threshold (default: settings.CV_CONFIDENCE).
            min_track_seconds: Minimum duration to count dwell time (default: settings.CV_MIN_TRACK_SECONDS).
            zone_coords: (x1, x2, y1, y2) bounding box for entry/exit zone.
            camera_id: Identifier for the CCTV stream.
            progress_callback: Optional callable receiving (frames_processed, current_unique_customers).

        Returns:
            Dictionary containing comprehensive metrics, detection boxes, and telemetry.
        """
        import cv2
        from ultralytics import YOLO

        settings = get_settings()
        conf = confidence if confidence is not None else settings.CV_CONFIDENCE
        min_duration = min_track_seconds if min_track_seconds is not None else settings.CV_MIN_TRACK_SECONDS

        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Open video and read stream properties
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video file: {video_path.name}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        reported_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        if not fps or fps <= 0:
            fps = 30.0  # fallback standard fps

        # Configurable Entrance/Exit Zone coordinates
        if zone_coords is not None:
            zone_x1, zone_x2, zone_y1, zone_y2 = zone_coords
        else:
            zone_x1 = settings.CV_ZONE_X1
            zone_x2 = settings.CV_ZONE_X2
            zone_y1 = settings.CV_ZONE_Y1
            zone_y2 = settings.CV_ZONE_Y2

        # Initialize spatial ZoneService and anonymous Customer VisitService
        zone_service = ZoneService(max_missed_frames=15, min_zone_dwell_seconds=min_duration)
        visit_service = VisitService(store_id="store-104")

        # 1. Register boundary tripwire lines for store entrance & exit
        line_entrance = BoundaryLine(
            line_id="line-entrance",
            name="Store Entrance Line",
            p1=(float(zone_x2), float(zone_y1)),
            p2=(float(zone_x2), float(zone_y2)),
            camera_id=camera_id,
        )
        line_exit = BoundaryLine(
            line_id="line-exit",
            name="Store Exit Line",
            p1=(float(zone_x1), float(zone_y1)),
            p2=(float(zone_x1), float(zone_y2)),
            camera_id=camera_id,
        )
        zone_service.register_boundary_line(line_entrance)
        zone_service.register_boundary_line(line_exit)
        visit_service.register_entrance_line("line-entrance", camera_id=camera_id)
        visit_service.register_exit_line("line-exit", camera_id=camera_id)

        # 2. Register standard supermarket zones scaled to video frame
        w_f = float(width)
        h_f = float(height)

        entrance_zone = StoreZone(
            zone_id="zone-entrance",
            name="Entrance Area",
            zone_type=ZoneType.ENTRANCE,
            polygon=[
                (float(zone_x1), float(zone_y1)),
                (float(zone_x2), float(zone_y1)),
                (float(zone_x2), float(zone_y2)),
                (float(zone_x1), float(zone_y2)),
            ],
            camera_id=camera_id,
            min_dwell_seconds=min_duration,
        )
        produce_zone = StoreZone(
            zone_id="zone-produce",
            name="Produce Section",
            zone_type=ZoneType.DEPARTMENT,
            polygon=[
                (0.0, 0.0),
                (w_f * 0.45, 0.0),
                (w_f * 0.45, h_f * 0.5),
                (0.0, h_f * 0.5),
            ],
            camera_id=camera_id,
            min_dwell_seconds=min_duration,
        )
        aisle1_zone = StoreZone(
            zone_id="zone-aisle1",
            name="Aisle 1 - Packaged Goods",
            zone_type=ZoneType.AISLE,
            polygon=[
                (w_f * 0.45, 0.0),
                (w_f, 0.0),
                (w_f, h_f * 0.5),
                (w_f * 0.45, h_f * 0.5),
            ],
            camera_id=camera_id,
            min_dwell_seconds=min_duration,
        )
        dairy_zone = StoreZone(
            zone_id="zone-dairy",
            name="Dairy & Refrigerated",
            zone_type=ZoneType.DEPARTMENT,
            polygon=[
                (0.0, h_f * 0.5),
                (w_f * 0.5, h_f * 0.5),
                (w_f * 0.5, h_f),
                (0.0, h_f),
            ],
            camera_id=camera_id,
            min_dwell_seconds=min_duration,
        )
        checkout_zone = StoreZone(
            zone_id="zone-checkout",
            name="Checkout Counters",
            zone_type=ZoneType.CHECKOUT,
            polygon=[
                (w_f * 0.5, h_f * 0.5),
                (w_f, h_f * 0.5),
                (w_f, h_f),
                (w_f * 0.5, h_f),
            ],
            camera_id=camera_id,
            min_dwell_seconds=min_duration,
        )

        zone_service.register_zone(entrance_zone)
        zone_service.register_zone(produce_zone)
        zone_service.register_zone(aisle1_zone)
        zone_service.register_zone(dairy_zone)
        zone_service.register_zone(checkout_zone)

        # CRITICAL: Instantiate fresh YOLO model per job to isolate ByteTrack tracker state
        # Exactly as specified in run_merl_batch.py to prevent ID carry-over between videos
        model = YOLO(str(self.model_path))

        cap = cv2.VideoCapture(str(video_path))

        frame_number = 0
        occupancy_values: List[int] = []
        first_seen: Dict[int, int] = {}
        last_seen: Dict[int, int] = {}
        hit_counts: Dict[int, int] = {}
        previous_positions: Dict[int, Tuple[int, int]] = {}
        counted_entries: Set[int] = set()
        counted_exits: Set[int] = set()
        entries = 0
        exits = 0

        # Sample detections for API response (capped to keep payload compact and fast)
        sample_detections: List[VideoDetectionBox] = []
        max_sample_detections = 50

        start_time = time.time()
        logger.info(f"Starting CV inference on {video_path.name} ({width}x{height} @ {fps:.2f} FPS)")

        try:
            while True:
                success, frame = cap.read()
                if not success:
                    break

                frame_number += 1

                # ByteTrack tracking for person class (COCO 0)
                results = model.track(
                    frame,
                    persist=True,
                    tracker=settings.CV_TRACKER_CONFIG,
                    classes=[0],
                    conf=conf,
                    verbose=False,
                )
                result = results[0]

                current_occupancy = 0
                active_frame_track_ids: Set[int] = set()
                current_time_s = round(frame_number / fps, 3)

                if result.boxes is not None and result.boxes.id is not None:
                    track_ids = result.boxes.id.int().cpu().tolist()
                    current_occupancy = len(track_ids)
                    active_frame_track_ids = set(track_ids)
                    boxes_xyxy = result.boxes.xyxy.cpu().numpy()
                    confs = result.boxes.conf.cpu().tolist() if result.boxes.conf is not None else [1.0] * len(track_ids)

                    for box, track_id, det_conf in zip(boxes_xyxy, track_ids, confs):
                        x1, y1, x2, y2 = box

                        # Dwell time tracking
                        hit_counts[track_id] = hit_counts.get(track_id, 0) + 1
                        if track_id not in first_seen:
                            first_seen[track_id] = frame_number
                        last_seen[track_id] = frame_number

                        # Directional Entry/Exit Zone Tracking (using foot position)
                        foot_x = int((x1 + x2) / 2)
                        foot_y = int(y2)

                        if track_id in previous_positions:
                            prev_x, prev_y = previous_positions[track_id]

                            vertically_aligned = (
                                zone_y1 <= foot_y <= zone_y2
                                and zone_y1 <= prev_y <= zone_y2
                            )

                            if vertically_aligned:
                                # ENTRY: RIGHT -> LEFT
                                if (
                                    prev_x > zone_x2
                                    and foot_x <= zone_x2
                                    and track_id not in counted_entries
                                ):
                                    entries += 1
                                    counted_entries.add(track_id)

                                # EXIT: LEFT -> RIGHT
                                elif (
                                    prev_x < zone_x1
                                    and foot_x >= zone_x1
                                    and track_id not in counted_exits
                                ):
                                    exits += 1
                                    counted_exits.add(track_id)

                        previous_positions[track_id] = (foot_x, foot_y)

                        # Update spatial zone tracking and dispatch to visit service
                        z_events = zone_service.update_track(
                            tracker_id=track_id,
                            box_xyxy=(float(x1), float(y1), float(x2), float(y2)),
                            frame_idx=frame_number,
                            timestamp=current_time_s,
                            camera_id=camera_id,
                        )
                        for z_ev in z_events:
                            visit_service.process_zone_event(z_ev)

                        # Collect sample detections
                        if len(sample_detections) < max_sample_detections:
                            sample_detections.append(
                                VideoDetectionBox(
                                    id=f"det-{len(sample_detections) + 1}",
                                    label="person",
                                    confidence=round(float(det_conf), 2),
                                    box=VideoBox(
                                        x=int(x1),
                                        y=int(y1),
                                        width=max(1, int(x2 - x1)),
                                        height=max(1, int(y2 - y1)),
                                    ),
                                )
                            )

                # Check for missed tracks to handle occlusions and zone departures
                missed_z_events = zone_service.handle_missed_detections(
                    current_frame=frame_number,
                    current_timestamp=current_time_s,
                    camera_id=camera_id,
                    active_tracker_ids=active_frame_track_ids,
                )
                for mz_ev in missed_z_events:
                    visit_service.process_zone_event(mz_ev)

                occupancy_values.append(current_occupancy)

                if progress_callback is not None and frame_number % 15 == 0:
                    progress_callback(frame_number, len(first_seen))

        finally:
            cap.release()

        elapsed_seconds = max(0.001, time.time() - start_time)
        measured_fps = round(frame_number / elapsed_seconds, 2)
        total_duration = round(frame_number / fps, 2)

        # Conclude any open zone and visit sessions
        end_events = zone_service.end_video(final_timestamp=total_duration, camera_id=camera_id)
        for e_ev in end_events:
            visit_service.process_zone_event(e_ev)

        visit_service.end_incomplete_sessions(final_timestamp=total_duration)

        all_visits = visit_service.get_all_visits()
        all_journey_events: List[VisitEvent] = []
        for v in all_visits:
            all_journey_events.extend(v.journey_events)

        # Calculate dwell times (filtering out noise < min_duration)
        observed_durations: List[float] = []
        for track_id, first_frame in first_seen.items():
            last_frame = last_seen.get(track_id, first_frame)
            duration_s = (last_frame - first_frame) / fps
            if duration_s >= min_duration:
                observed_durations.append(duration_s)

        avg_dwell_seconds = (
            round(sum(observed_durations) / len(observed_durations), 1)
            if observed_durations
            else 0.0
        )
        max_dwell_seconds = (
            round(max(observed_durations), 1) if observed_durations else 0.0
        )
        min_dwell_seconds = (
            round(min(observed_durations), 1) if observed_durations else 0.0
        )

        peak_occupancy = max(occupancy_values) if occupancy_values else 0
        avg_occupancy = (
            round(sum(occupancy_values) / len(occupancy_values), 2)
            if occupancy_values
            else 0.0
        )

        tracking_summaries: List[Dict[str, Any]] = []
        for track_id, f_start in first_seen.items():
            f_end = last_seen.get(track_id, f_start)
            span = max(1, f_end - f_start + 1)
            hits = hit_counts.get(track_id, 1)
            rate = round(min(1.0, hits / span), 2)
            dwell = round((f_end - f_start) / fps, 2)
            tracking_summaries.append({
                "track_id": track_id,
                "first_frame": f_start,
                "last_frame": f_end,
                "dwell_seconds": dwell,
                "hit_count": hits,
                "hit_rate": rate,
                "crossed_entrance": track_id in counted_entries,
                "crossed_exit": track_id in counted_exits,
            })

        logger.info(
            f"Finished CV processing on {video_path.name}: "
            f"{frame_number} frames in {elapsed_seconds:.2f}s ({measured_fps} FPS), "
            f"Unique Customers: {len(first_seen)}, Peak Occupancy: {peak_occupancy}, "
            f"Avg Dwell: {avg_dwell_seconds}s, Entries: {entries}, Exits: {exits}, "
            f"Track Summaries: {len(tracking_summaries)}"
        )

        return {
            "filename": video_path.name,
            "width": width,
            "height": height,
            "fps": round(fps, 2),
            "total_frames": frame_number,
            "reported_frames": reported_frames,
            "duration_seconds": total_duration,
            "elapsed_seconds": round(elapsed_seconds, 2),
            "measured_fps": measured_fps,
            "unique_customers": len(first_seen),
            "tracks_valid_dwell": len(observed_durations),
            "peak_occupancy": peak_occupancy,
            "average_occupancy": avg_occupancy,
            "average_dwell_seconds": avg_dwell_seconds,
            "maximum_dwell_seconds": max_dwell_seconds,
            "minimum_dwell_seconds": min_dwell_seconds,
            "entries": entries,
            "exits": exits,
            "detections": sample_detections,
            "tracking_summaries": tracking_summaries,
            "visits": all_visits,
            "journey_events": all_journey_events,
        }
