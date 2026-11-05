"""
Benchmark YOLO11n + ByteTrack processing speed on the five MERL clips.
Run from E:\\Smart-Retail with the project's virtual environment activated:
    python benchmark_merl_fps.py

Outputs:
    results/fps_benchmark.csv
    results/fps_benchmark_system.txt

FPS is measured on the machine where this script runs. It is not a claim
about a different GPU/CPU or deployment environment.
"""
import csv
import platform
import time
from pathlib import Path

import cv2
import torch
from ultralytics import YOLO

ROOT = Path(r"E:\Smart-Retail")
VIDEO_DIR = ROOT / "data" / "videos"
WEIGHTS = ROOT / "yolo11n.pt"
RESULTS_DIR = ROOT / "results"
CSV_PATH = RESULTS_DIR / "fps_benchmark.csv"
SYSTEM_PATH = RESULTS_DIR / "fps_benchmark_system.txt"

VIDEOS = [
    "1_1_crop.mp4",
    "2_1_crop.mp4",
    "3_1_crop.mp4",
    "4_1_crop.mp4",
    "5_1_crop.mp4",
]
CONFIDENCE = 0.40
PERSON_CLASS = 0
TRACKER = "bytetrack.yaml"
WARMUP_FRAMES = 10


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if not WEIGHTS.exists():
        raise FileNotFoundError(f"Model weights not found: {WEIGHTS}")
    missing = [name for name in VIDEOS if not (VIDEO_DIR / name).exists()]
    if missing:
        raise FileNotFoundError(
            "Missing video(s) in " + str(VIDEO_DIR) + ": " + ", ".join(missing)
        )

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A (CPU)"
    system_lines = [
        f"Platform: {platform.platform()}",
        f"Processor: {platform.processor() or 'Not reported by OS'}",
        f"Python: {platform.python_version()}",
        f"OpenCV: {cv2.__version__}",
        f"PyTorch: {torch.__version__}",
        f"Ultralytics: {__import__('ultralytics').__version__}",
        f"Device selected: {device}",
        f"GPU: {gpu_name}",
        f"Model weights: {WEIGHTS}",
        f"Confidence threshold: {CONFIDENCE}",
        f"Class filter: person (COCO class {PERSON_CLASS})",
        f"Tracker: {TRACKER}",
        f"Warm-up: up to {WARMUP_FRAMES} frames per video (excluded from reported timing)",
        "Inference FPS = measured frames / time spent inside model tracking calls after warm-up.",
        "End-to-end FPS = all frames / elapsed processing-loop time, including video decoding.",
    ]

    rows = []
    print(f"Device: {device}; GPU: {gpu_name}")
    for video_name in VIDEOS:
        video_path = VIDEO_DIR / video_name
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"[SKIP] Could not open {video_path}")
            continue

        total_frames_reported = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps_source = cap.get(cv2.CAP_PROP_FPS)
        model = YOLO(str(WEIGHTS))

        # Warm-up using detector only, not the tracker, to avoid polluting IDs.
        warmed = 0
        while warmed < WARMUP_FRAMES:
            ok, frame = cap.read()
            if not ok:
                break
            model.predict(frame, classes=[PERSON_CLASS], conf=CONFIDENCE, verbose=False)
            warmed += 1

        measured_frames = 0
        inference_seconds = 0.0
        loop_start = time.perf_counter()
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            t0 = time.perf_counter()
            model.track(
                frame,
                persist=True,
                tracker=TRACKER,
                classes=[PERSON_CLASS],
                conf=CONFIDENCE,
                verbose=False,
            )
            inference_seconds += time.perf_counter() - t0
            measured_frames += 1
            if measured_frames % 500 == 0:
                print(f"  {video_name}: processed {measured_frames} measured frames...")
        loop_seconds = time.perf_counter() - loop_start
        cap.release()

        inference_fps = measured_frames / inference_seconds if inference_seconds else 0.0
        end_to_end_fps = measured_frames / loop_seconds if loop_seconds else 0.0
        row = {
            "video": video_name,
            "source_fps": round(fps_source, 3) if fps_source else "",
            "reported_total_frames": total_frames_reported,
            "warmup_frames_excluded": warmed,
            "measured_frames": measured_frames,
            "inference_seconds": round(inference_seconds, 4),
            "loop_seconds_including_decode": round(loop_seconds, 4),
            "inference_fps": round(inference_fps, 3),
            "end_to_end_fps": round(end_to_end_fps, 3),
            "device": device,
            "gpu": gpu_name,
        }
        rows.append(row)
        print(
            f"[DONE] {video_name}: {measured_frames} frames; "
            f"inference FPS={inference_fps:.2f}; end-to-end FPS={end_to_end_fps:.2f}"
        )

    if not rows:
        raise RuntimeError("No videos were successfully benchmarked.")

    with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    total_frames = sum(r["measured_frames"] for r in rows)
    total_inf = sum(r["inference_seconds"] for r in rows)
    total_loop = sum(r["loop_seconds_including_decode"] for r in rows)
    system_lines += [
        "",
        f"Successfully benchmarked videos: {len(rows)}",
        f"Total measured frames: {total_frames}",
        f"Combined inference FPS: {total_frames / total_inf:.3f}" if total_inf else "Combined inference FPS: N/A",
        f"Combined end-to-end FPS: {total_frames / total_loop:.3f}" if total_loop else "Combined end-to-end FPS: N/A",
        "Note: results are machine-, software-, and workload-dependent.",
    ]
    SYSTEM_PATH.write_text("\n".join(system_lines), encoding="utf-8")
    print(f"\nSaved benchmark CSV: {CSV_PATH}")
    print(f"Saved system details: {SYSTEM_PATH}")
    print("\nUpload both output files here when finished.")


if __name__ == "__main__":
    main()
