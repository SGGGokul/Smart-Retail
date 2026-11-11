from ultralytics import YOLO
import cv2

# Load YOLO model
model = YOLO("yolo11n.pt")

# Open video
video_path = "data/videos/store.mp4"
cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print("Error: Could not open video.")
    exit()

# Store unique customer IDs
customer_ids = set()

frame_number = 0

print("Processing video...")
print("Press Q to stop.")

while True:
    success, frame = cap.read()

    if not success:
        break

    frame_number += 1

    # Track persons
    results = model.track(
        frame,
        persist=True,
        tracker="bytetrack.yaml",
        classes=[0],
        conf=0.4,
        verbose=False
    )

    # Get tracking IDs
    boxes = results[0].boxes

    if boxes.id is not None:
        track_ids = boxes.id.int().cpu().tolist()

        for track_id in track_ids:
            customer_ids.add(track_id)

    # Display progress
    if frame_number % 100 == 0:
        print(
            f"Processed frames: {frame_number} | "
            f"Unique customer IDs: {len(customer_ids)}"
        )

cap.release()

print("\nProcessing completed!")
print(f"Total frames processed: {frame_number}")
print(f"Unique customer IDs detected: {len(customer_ids)}")