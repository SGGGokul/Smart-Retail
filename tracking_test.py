from ultralytics import YOLO
import cv2

# Load YOLO model
model = YOLO("yolo11n.pt")

# Open retail video
video_path = "data/videos/store.mp4"
cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print("Error: Could not open video.")
    exit()

print("Starting customer tracking...")
print("Press Q to stop.")

while True:

    success, frame = cap.read()

    if not success:
        break

    # Track only persons
    results = model.track(
        frame,
        persist=True,
        tracker="bytetrack.yaml",
        classes=[0],
        verbose=False
    )

    # Draw tracking results
    annotated_frame = results[0].plot()

    # Display frame
    cv2.imshow("Customer Tracking", annotated_frame)

    # Press Q to quit
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()

print("Tracking finished!")