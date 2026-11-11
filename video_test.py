import cv2

video_path = "data/videos/store.mp4"

cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print("Error: Could not open video.")
    exit()

success, frame = cap.read()

if success:
    print("First frame read successfully!")

    cv2.imshow("First Frame", frame)

    print("Press any key to close the window.")
    cv2.waitKey(0)

else:
    print("Error: Could not read the first frame.")

cap.release()
cv2.destroyAllWindows()