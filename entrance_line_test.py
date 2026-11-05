import cv2

video_path = "data/videos/store.mp4"

cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print("Error: Could not open video.")
    exit()

success, frame = cap.read()

if not success:
    print("Error: Could not read frame.")
    cap.release()
    exit()

# Entrance / exit counting line
cv2.line(
    frame,
    (846, 330),
    (680, 480),
    (255, 0, 0),
    3
)

cv2.imshow("Entrance Line Test", frame)

print("Check the entrance line position.")
print("Press any key to close.")

cv2.waitKey(0)

cap.release()
cv2.destroyAllWindows()