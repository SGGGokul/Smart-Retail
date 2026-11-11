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
# Entrance zone
# -----------------------------
ZONE_X1 = 700
ZONE_X2 = 846
ZONE_Y1 = 320
ZONE_Y2 = 480

# -----------------------------
# Previous positions
# -----------------------------
previous_positions = {}

# Prevent duplicate counting
counted_entries = set()
counted_exits = set()

entries = 0
exits = 0

print("Starting entrance/exit analysis...")
print("RIGHT -> LEFT = ENTRY")
print("LEFT -> RIGHT = EXIT")
print("Press Q to stop.")

while True:

    success, frame = cap.read()

    if not success:
        break

    # -----------------------------
    # YOLO tracking
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
    # Draw entrance zone
    # -----------------------------
    cv2.rectangle(
        frame,
        (ZONE_X1, ZONE_Y1),
        (ZONE_X2, ZONE_Y2),
        (255, 0, 0),
        3
    )

    cv2.putText(
        frame,
        "ENTRANCE ZONE",
        (ZONE_X1 - 80, ZONE_Y1 - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        2
    )

    # -----------------------------
    # Process people
    # -----------------------------
    if result.boxes.id is not None:

        boxes = result.boxes.xyxy.cpu().numpy()
        track_ids = result.boxes.id.int().cpu().tolist()

        for box, track_id in zip(boxes, track_ids):

            x1, y1, x2, y2 = box

            # Bottom-center = approximate foot position
            foot_x = int((x1 + x2) / 2)
            foot_y = int(y2)

            # Draw foot point
            cv2.circle(
                frame,
                (foot_x, foot_y),
                6,
                (0, 255, 0),
                -1
            )

            # Display ID
            cv2.putText(
                frame,
                f"ID {track_id}",
                (int(x1), int(y1) - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                2
            )

            # --------------------------------
            # Check previous position
            # --------------------------------
            if track_id in previous_positions:

                previous_x, previous_y = previous_positions[track_id]

                # Person is moving through the entrance
                vertically_aligned = (
                    ZONE_Y1 <= foot_y <= ZONE_Y2
                    and
                    ZONE_Y1 <= previous_y <= ZONE_Y2
                )

                if vertically_aligned:

                    # --------------------------------
                    # ENTRY
                    # RIGHT -> LEFT
                    # --------------------------------
                    if (
                        previous_x > ZONE_X2
                        and foot_x <= ZONE_X2
                        and track_id not in counted_entries
                    ):

                        entries += 1
                        counted_entries.add(track_id)

                        print(
                            f"ENTRY detected - ID {track_id}"
                        )

                    # --------------------------------
                    # EXIT
                    # LEFT -> RIGHT
                    # --------------------------------
                    elif (
                        previous_x < ZONE_X1
                        and foot_x >= ZONE_X1
                        and track_id not in counted_exits
                    ):

                        exits += 1
                        counted_exits.add(track_id)

                        print(
                            f"EXIT detected - ID {track_id}"
                        )

            # Save current position
            previous_positions[track_id] = (
                foot_x,
                foot_y
            )

    # -----------------------------
    # Display counters
    # -----------------------------
    cv2.putText(
        frame,
        f"Entries: {entries}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

    cv2.putText(
        frame,
        f"Exits: {exits}",
        (20, 75),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 0, 255),
        2
    )

    # -----------------------------
    # Show video
    # -----------------------------
    cv2.imshow(
        "Entry Exit Counter",
        frame
    )

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()

print()
print("Counting completed!")
print(f"Total Entries: {entries}")
print(f"Total Exits: {exits}")