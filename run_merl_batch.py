from pathlib import Path
import csv
import cv2
from ultralytics import YOLO

# Run this script from anywhere; paths are based on this script's folder.
PROJECT_DIR = Path(__file__).resolve().parent
VIDEO_DIR = PROJECT_DIR / "data" / "videos"
MODEL_PATH = PROJECT_DIR / "yolo11n.pt"
OUTPUT_DIR = PROJECT_DIR / "results"
OUTPUT_DIR.mkdir(exist_ok=True)

# Process only these five MERL clips.
VIDEO_NAMES = [
    "1_1_crop.mp4",
    "2_1_crop.mp4",
    "3_1_crop.mp4",
    "4_1_crop.mp4",
    "5_1_crop.mp4",
]

CONFIDENCE = 0.4
MIN_TRACK_SECONDS = 1.0

def process_video(video_path: Path) -> dict:
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path.name}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    reported_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    if not fps or fps <= 0:
        raise RuntimeError(f"Could not read a valid FPS value for {video_path.name}")

    # A fresh model/tracker per video prevents track IDs carrying over between clips.
    model = YOLO(str(MODEL_PATH))
    cap = cv2.VideoCapture(str(video_path))

    frame_number = 0
    occupancy_values = []
    first_seen = {}
    last_seen = {}

    print(f"\nProcessing: {video_path.name}")
    print(f"Video info: {width}x{height}, {fps:.3f} FPS, reported frames: {reported_frames}")

    try:
        while True:
            success, frame = cap.read()
            if not success:
                break

            frame_number += 1
            results = model.track(
                frame,
                persist=True,
                tracker="bytetrack.yaml",
                classes=[0],       # COCO class 0 = person
                conf=CONFIDENCE,
                verbose=False,
            )
            result = results[0]

            # Count tracked person boxes only; this is not ground-truth occupancy.
            current_count = 0
            if result.boxes is not None and result.boxes.id is not None:
                ids = result.boxes.id.int().cpu().tolist()
                current_count = len(ids)
                for track_id in ids:
                    if track_id not in first_seen:
                        first_seen[track_id] = frame_number
                    last_seen[track_id] = frame_number

            occupancy_values.append(current_count)

            if frame_number % 300 == 0:
                print(
                    f"  Frames: {frame_number} | "
                    f"Current tracked persons: {current_count} | "
                    f"Track IDs seen: {len(first_seen)}"
                )
    finally:
        cap.release()

    observed_durations = []
    for track_id in first_seen:
        duration_seconds = (last_seen[track_id] - first_seen[track_id]) / fps
        if duration_seconds >= MIN_TRACK_SECONDS:
            observed_durations.append(duration_seconds)

    total_duration = frame_number / fps
    average_occupancy = (
        sum(occupancy_values) / len(occupancy_values)
        if occupancy_values else 0.0
    )
    peak_occupancy = max(occupancy_values) if occupancy_values else 0
    average_observed_duration = (
        sum(observed_durations) / len(observed_durations)
        if observed_durations else 0.0
    )
    maximum_observed_duration = max(observed_durations) if observed_durations else 0.0
    minimum_observed_duration = min(observed_durations) if observed_durations else 0.0

    row = {
        "video": video_path.name,
        "width_px": width,
        "height_px": height,
        "fps": round(fps, 3),
        "frames_processed": frame_number,
        "duration_seconds": round(total_duration, 3),
        "unique_track_ids_observed": len(first_seen),
        "tracks_at_least_1_second": len(observed_durations),
        "average_tracked_person_boxes_per_frame": round(average_occupancy, 3),
        "peak_tracked_person_boxes_in_frame": peak_occupancy,
        "average_observed_track_duration_seconds": round(average_observed_duration, 3),
        "maximum_observed_track_duration_seconds": round(maximum_observed_duration, 3),
        "minimum_observed_track_duration_seconds": round(minimum_observed_duration, 3),
        "confidence_threshold": CONFIDENCE,
        "minimum_track_duration_filter_seconds": MIN_TRACK_SECONDS,
    }

    print(f"  Finished: {video_path.name}")
    print(f"  Frames processed: {frame_number}")
    print(f"  Duration: {total_duration:.2f} seconds")
    print(f"  Track IDs observed: {len(first_seen)}")
    print(f"  Tracks >= 1 second: {len(observed_durations)}")
    print(f"  Average tracked person boxes/frame: {average_occupancy:.3f}")
    print(f"  Peak tracked person boxes/frame: {peak_occupancy}")
    print(f"  Average observed track duration: {average_observed_duration:.2f} seconds")
    print(f"  Maximum observed track duration: {maximum_observed_duration:.2f} seconds")
    print(f"  Minimum observed track duration: {minimum_observed_duration:.2f} seconds")
    return row

def main():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model file not found: {MODEL_PATH}\n"
            "Make sure yolo11n.pt is in the Smart-Retail project folder."
        )

    rows = []
    errors = []

    for name in VIDEO_NAMES:
        path = VIDEO_DIR / name
        try:
            rows.append(process_video(path))
        except Exception as exc:
            errors.append((name, str(exc)))
            print(f"\nERROR processing {name}: {exc}")

    csv_path = OUTPUT_DIR / "merl_video_results.csv"
    if rows:
        with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nSaved results CSV: {csv_path}")

    if errors:
        error_path = OUTPUT_DIR / "merl_video_errors.txt"
        with error_path.open("w", encoding="utf-8") as file:
            for name, message in errors:
                file.write(f"{name}: {message}\n")
        print(f"Some videos had errors. Details saved to: {error_path}")

    print("\nAll processing attempts finished.")
    print("Important: these are automated estimates, not validated ground-truth accuracy.")
    print("Because MERL clips show one shopper at a time, do not interpret the count as busy-store occupancy.")

if __name__ == "__main__":
    main()