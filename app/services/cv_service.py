import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from app.core.config import get_settings
from app.schemas.video import VideoBox, VideoDetectionBox

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
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Any]:
        """Process video through YOLO11n + ByteTrack with isolated tracker state.

        Args:
            video_path: Path to target video file.
            confidence: Detection confidence threshold (default: settings.CV_CONFIDENCE).
            min_track_seconds: Minimum duration to count dwell time (default: settings.CV_MIN_TRACK_SECONDS).
            zone_coords: (x1, x2, y1, y2) bounding box for entry/exit zone.
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

                if result.boxes is not None and result.boxes.id is not None:
                    track_ids = result.boxes.id.int().cpu().tolist()
                    current_occupancy = len(track_ids)
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

                occupancy_values.append(current_occupancy)

                if progress_callback is not None and frame_number % 15 == 0:
                    progress_callback(frame_number, len(first_seen))

        finally:
            cap.release()

        elapsed_seconds = max(0.001, time.time() - start_time)
        measured_fps = round(frame_number / elapsed_seconds, 2)
        total_duration = round(frame_number / fps, 2)

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
        }
