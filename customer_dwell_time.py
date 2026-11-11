from ultralytics import YOLO
import cv2

# -----------------------------
# Load YOLO model
# -----------------------------
model = YOLO("yolo11n.pt")

# -----------------------------
# Open video
# -----------------------------
video_path = "data/videos/store.mp4"
cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print("Error: Could not open video.")
    exit()

# Get FPS
fps = cap.get(cv2.CAP_PROP_FPS)

# -----------------------------
# Track customer appearance
# -----------------------------
first_seen = {}
last_seen = {}

frame_number = 0

print("Starting customer dwell-time analysis...")
print("Press Q to stop.")

while True:

    success, frame = cap.read()

    if not success:
        break

    frame_number += 1

    # -----------------------------
    # Track people
    # -----------------------------
    results = model.track(
        frame,
        persist=True,
        tracker="bytetrack.yaml",
        classes=[0],
        conf=0.4,
        verbose=False
    )

    result = results[0]

    if result.boxes.id is not None:

        track_ids = result.boxes.id.int().cpu().tolist()

        for track_id in track_ids:

            # First frame where customer was observed
            if track_id not in first_seen:
                first_seen[track_id] = frame_number

            # Most recent frame
            last_seen[track_id] = frame_number

    # -----------------------------
    # Display tracking
    # -----------------------------
    annotated_frame = result.plot()

    cv2.putText(
        annotated_frame,
        f"Customers tracked: {len(first_seen)}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

    cv2.imshow(
        "Customer Dwell Time",
        annotated_frame
    )

    # Progress
    if frame_number % 100 == 0:
        print(
            f"Processed frames: {frame_number} | "
            f"Customers tracked: {len(first_seen)}"
        )

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()

# -----------------------------
# Calculate dwell times
# -----------------------------
dwell_times = []

for track_id in first_seen:

    duration_frames = (
        last_seen[track_id]
        - first_seen[track_id]
    )

    duration_seconds = duration_frames / fps

    # Ignore extremely short detections
    if duration_seconds >= 1:
        dwell_times.append(
            (track_id, duration_seconds)
        )

# -----------------------------
# Calculate statistics
# -----------------------------
if dwell_times:

    durations = [
        duration
        for track_id, duration in dwell_times
    ]

    average_dwell = sum(durations) / len(durations)
    maximum_dwell = max(durations)
    minimum_dwell = min(durations)

else:

    average_dwell = 0
    maximum_dwell = 0
    minimum_dwell = 0

# -----------------------------
# Final output
# -----------------------------
print()
print("Dwell-time analysis completed!")

print(f"Total frames processed: {frame_number}")
print(f"Customers tracked: {len(first_seen)}")
print(f"Customers with valid observations: {len(dwell_times)}")

print(
    f"Average observed dwell time: "
    f"{average_dwell:.2f} seconds"
)

print(
    f"Maximum observed dwell time: "
    f"{maximum_dwell:.2f} seconds"
)

print(
    f"Minimum observed dwell time: "
    f"{minimum_dwell:.2f} seconds"
)