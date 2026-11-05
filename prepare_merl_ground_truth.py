"""
Create a small, manually checkable ground-truth set for the MERL clips.

Run from E:\\Smart-Retail with the project venv active:
    python prepare_merl_ground_truth.py

Creates:
  results/ground_truth_sample/frames/          (raw frames, no boxes drawn)
  results/ground_truth_sample/predictions.csv  (YOLO person detections on sampled frames)
  results/ground_truth_sample/annotation_template.csv

Open the raw frame images and enter the TRUE number of visible people in the
ground_truth_person_count column of annotation_template.csv. Count visible
people, including partial people at frame edges; do not count posters/images
of people on products. Save the CSV and upload it with predictions.csv.
"""
import csv
from pathlib import Path

import cv2
from ultralytics import YOLO

ROOT = Path(r"E:\Smart-Retail")
VIDEO_DIR = ROOT / "data" / "videos"
WEIGHTS = ROOT / "yolo11n.pt"
OUT_DIR = ROOT / "results" / "ground_truth_sample"
FRAMES_DIR = OUT_DIR / "frames"
PREDICTIONS_CSV = OUT_DIR / "predictions.csv"
TEMPLATE_CSV = OUT_DIR / "annotation_template.csv"

VIDEOS = [
    "1_1_crop.mp4",
    "2_1_crop.mp4",
    "3_1_crop.mp4",
    "4_1_crop.mp4",
    "5_1_crop.mp4",
]
SAMPLES_PER_VIDEO = 10
CONFIDENCE = 0.40
PERSON_CLASS = 0


def main():
    if not WEIGHTS.exists():
        raise FileNotFoundError(f"Model weights not found: {WEIGHTS}")
    missing = [v for v in VIDEOS if not (VIDEO_DIR / v).exists()]
    if missing:
        raise FileNotFoundError(f"Missing videos in {VIDEO_DIR}: {missing}")

    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(WEIGHTS))
    pred_rows = []
    template_rows = []

    for video_name in VIDEOS:
        path = VIDEO_DIR / video_name
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            print(f"[SKIP] Cannot open {video_name}")
            continue

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        # Spread sample frames across the clip, avoiding the very first/last frame.
        indices = [
            round((i + 1) * (frame_count - 1) / (SAMPLES_PER_VIDEO + 1))
            for i in range(SAMPLES_PER_VIDEO)
        ]

        print(f"\nSampling {video_name}...")
        for sample_num, frame_index in enumerate(indices, start=1):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok:
                print(f"  [WARN] Could not read frame {frame_index}")
                continue

            stem = Path(video_name).stem
            image_name = f"{stem}_sample_{sample_num:02d}_frame_{frame_index:05d}.jpg"
            image_path = FRAMES_DIR / image_name
            # Save raw image without detection boxes so manual counts are unbiased.
            if not cv2.imwrite(str(image_path), frame):
                print(f"  [WARN] Could not save {image_path}")
                continue

            result = model.predict(
                frame, classes=[PERSON_CLASS], conf=CONFIDENCE, verbose=False
            )[0]
            boxes = result.boxes
            pred_count = len(boxes) if boxes is not None else 0
            confs = []
            coords = []
            if boxes is not None:
                for b in boxes:
                    xyxy = [round(float(v), 1) for v in b.xyxy[0].tolist()]
                    conf = round(float(b.conf[0]), 4)
                    coords.append(xyxy)
                    confs.append(conf)

            seconds = frame_index / source_fps
            pred_rows.append({
                "image_file": image_name,
                "video": video_name,
                "frame_index_zero_based": frame_index,
                "timestamp_seconds": round(seconds, 3),
                "source_fps": round(source_fps, 3),
                "model_person_detection_count": pred_count,
                "detection_confidences": ";".join(map(str, confs)),
                "detection_boxes_xyxy": ";".join(str(c) for c in coords),
                "confidence_threshold": CONFIDENCE,
            })
            template_rows.append({
                "image_file": image_name,
                "video": video_name,
                "frame_index_zero_based": frame_index,
                "timestamp_seconds": round(seconds, 3),
                "model_person_detection_count": pred_count,
                "ground_truth_person_count": "",
                "notes_if_uncertain": "",
            })
            print(
                f"  {image_name}: model detections={pred_count}, "
                f"time={seconds:.2f}s"
            )
        cap.release()

    if not pred_rows:
        raise RuntimeError("No sample frames were created.")

    with PREDICTIONS_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(pred_rows[0].keys()))
        w.writeheader()
        w.writerows(pred_rows)
    with TEMPLATE_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(template_rows[0].keys()))
        w.writeheader()
        w.writerows(template_rows)

    print("\nDone.")
    print(f"Raw sample images: {FRAMES_DIR}")
    print(f"Predictions CSV:   {PREDICTIONS_CSV}")
    print(f"Annotation CSV:    {TEMPLATE_CSV}")
    print("\nNext: inspect each raw image and fill ground_truth_person_count.")
    print("Count actual visible people, not detection boxes. Save the CSV and upload it.")
    print("For uncertain frames, enter your best count and explain in notes_if_uncertain.")


if __name__ == "__main__":
    main()
