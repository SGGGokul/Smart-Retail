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

# -----------------------------
# Occupancy statistics
# -----------------------------
frame_number = 0

occupancy_values = []

peak_occupancy = 0

print("Starting customer occupancy analysis...")
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

    # -----------------------------
    # Count people in current frame
    # -----------------------------
    current_occupancy = 0

    if result.boxes.id is not None:
        current_occupancy = len(result.boxes.id)

    # Store occupancy
    occupancy_values.append(current_occupancy)

    # Update peak
    if current_occupancy > peak_occupancy:
        peak_occupancy = current_occupancy

    # -----------------------------
    # Display occupancy
    # -----------------------------
    cv2.putText(
        frame,
        f"Current Customers: {current_occupancy}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

    cv2.putText(
        frame,
        f"Peak Customers: {peak_occupancy}",
        (20, 75),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2
    )

    # -----------------------------
    # Display tracking
    # -----------------------------
    annotated_frame = result.plot()

    # Put KPI text on annotated frame
    cv2.putText(
        annotated_frame,
        f"Current Customers: {current_occupancy}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

    cv2.putText(
        annotated_frame,
        f"Peak Customers: {peak_occupancy}",
        (20, 75),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2
    )

    cv2.imshow(
        "Customer Occupancy",
        annotated_frame
    )

    # -----------------------------
    # Progress
    # -----------------------------
    if frame_number % 100 == 0:
        print(
            f"Processed frames: {frame_number} | "
            f"Current occupancy: {current_occupancy} | "
            f"Peak occupancy: {peak_occupancy}"
        )

    # -----------------------------
    # Quit
    # -----------------------------
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# -----------------------------
# Calculate average occupancy
# -----------------------------
if occupancy_values:
    average_occupancy = (
        sum(occupancy_values)
        / len(occupancy_values)
    )
else:
    average_occupancy = 0

cap.release()
cv2.destroyAllWindows()

# -----------------------------
# Final results
# -----------------------------
print()
print("Occupancy analysis completed!")
print(f"Total frames processed: {frame_number}")
print(f"Peak customer occupancy: {peak_occupancy}")
print(f"Average customer occupancy: {average_occupancy:.2f}")