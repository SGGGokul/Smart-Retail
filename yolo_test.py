from ultralytics import YOLO
import cv2

# Load the pretrained YOLO model
model = YOLO("yolo11n.pt")

# Open the retail video
video_path = "data/videos/store.mp4"
cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print("Error: Could not open video.")
    exit()

# Read the first frame
success, frame = cap.read()

if not success:
    print("Error: Could not read frame.")
    cap.release()
    exit()

# Run YOLO detection
results = model(frame)

# Draw the detected objects on the frame
annotated_frame = results[0].plot()

# Display the result
cv2.imshow("YOLO Detection", annotated_frame)

print("YOLO detection completed!")
print("Press any key to close the window.")

cv2.waitKey(0)

cap.release()
cv2.destroyAllWindows()
