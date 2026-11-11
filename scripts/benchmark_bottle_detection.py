import os
import sys
import time
from pathlib import Path
import cv2
import numpy as np
from ultralytics import YOLO

def main():
    img_path = Path("data/uploads/sample_retail_shelf.jpg")
    if not img_path.exists():
        print(f"Error: {img_path} does not exist")
        sys.exit(1)

    img = cv2.imread(str(img_path))
    h, w = img.shape[:2]
    print(f"Loaded image: {img_path.name}, Dimensions: {w}x{h}")

    model = YOLO("yolo11n.pt")
    
    print("\n" + "="*80)
    print("PHASE 2: GRID SEARCH EVALUATION ON SHELF IMAGE")
    print("="*80)
    
    # Check all detections at very low conf (0.05) to see what the model detects at different imgsz
    print("\n--- Testing Image Resolutions (imgsz) at conf=0.10 ---")
    for sz in [640, 896, 1024, 1280]:
        t0 = time.perf_counter()
        res = model.predict(source=img, imgsz=sz, conf=0.10, verbose=False)[0]
        dt = (time.perf_counter() - t0) * 1000
        
        counts = {}
        bottle_confs = []
        for b in res.boxes:
            c = int(b.cls[0].item())
            name = model.names[c]
            counts[name] = counts.get(name, 0) + 1
            if name == "bottle":
                bottle_confs.append(float(b.conf[0].item()))
        
        bottle_info = f"bottles: {counts.get('bottle', 0)}"
        if bottle_confs:
            bottle_info += f" (avg conf: {np.mean(bottle_confs):.2f}, min: {np.min(bottle_confs):.2f}, max: {np.max(bottle_confs):.2f})"
        print(f"imgsz={sz:4d} | Latency: {dt:6.1f}ms | Total Dets: {len(res.boxes):3d} | {bottle_info} | All: {counts}")

    print("\n--- Testing Confidence Thresholds (imgsz=896) ---")
    for conf in [0.05, 0.10, 0.15, 0.20, 0.25]:
        t0 = time.perf_counter()
        res = model.predict(source=img, imgsz=896, conf=conf, verbose=False)[0]
        dt = (time.perf_counter() - t0) * 1000
        
        counts = {}
        for b in res.boxes:
            c = int(b.cls[0].item())
            name = model.names[c]
            counts[name] = counts.get(name, 0) + 1
        print(f"conf={conf:.2f} | Latency: {dt:6.1f}ms | Total Dets: {len(res.boxes):3d} | Bottles: {counts.get('bottle', 0):3d} | All: {counts}")

    print("\n--- Testing IoU Thresholds (imgsz=896, conf=0.10) ---")
    for iou in [0.45, 0.50, 0.60, 0.70, 0.80]:
        t0 = time.perf_counter()
        res = model.predict(source=img, imgsz=896, conf=0.10, iou=iou, verbose=False)[0]
        dt = (time.perf_counter() - t0) * 1000
        
        counts = {}
        for b in res.boxes:
            c = int(b.cls[0].item())
            name = model.names[c]
            counts[name] = counts.get(name, 0) + 1
        print(f"iou={iou:.2f} | Latency: {dt:6.1f}ms | Total Dets: {len(res.boxes):3d} | Bottles: {counts.get('bottle', 0):3d}")

if __name__ == "__main__":
    main()
