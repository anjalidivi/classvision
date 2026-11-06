
import cv2
import json

from pathlib import Path
from face_tracker import FaceTracker


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent

REPORT_DIR = (
    PROJECT_DIR / "reports" / "processed" / "faces"
)

OUTPUT_DIR = (
    PROJECT_DIR / "reports" / "processed" / "annotated"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# ENGAGEMENT BOX COLOURS (BGR)
# --------------------------------------------------

COLORS = {
    "engaged": (0, 180, 0),          # Green
    "low_engagement": (0, 0, 220),   # Red
    "waiting": (150, 150, 150)      # Grey
}


# --------------------------------------------------
# GET ENGAGEMENT STATUS
# --------------------------------------------------

def get_engagement_status(student):

    status = student.get(
        "engagement_status",
        "waiting"
    )

    if status not in COLORS:
        return "waiting"

    return status


# --------------------------------------------------
# DRAW ONLY FACE BOUNDING BOX
# --------------------------------------------------

def draw_student_box(frame, student):

    height, width = frame.shape[:2]

    x, y, box_width, box_height = student["box"]

    # Small proportional margin.

    margin_x = int(box_width * 0.08)
    margin_y = int(box_height * 0.08)

    x1 = max(0, x - margin_x)
    y1 = max(0, y - margin_y)

    x2 = min(
        width - 1,
        x + box_width + margin_x
    )

    y2 = min(
        height - 1,
        y + box_height + margin_y
    )

    # Get engagement colour.

    status = get_engagement_status(student)

    color = COLORS[status]

    # Draw only the face rectangle.

    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        color,
        2
    )


# --------------------------------------------------
# CREATE ANNOTATED VIDEO
# --------------------------------------------------

def create_annotated_video(video_path, report_path):

    video_path = Path(video_path)
    report_path = Path(report_path)

    with report_path.open(
        "r",
        encoding="utf-8"
    ) as file:

        report = json.load(file)

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():

        raise RuntimeError(
            "Cannot open input video."
        )

    fps = cap.get(cv2.CAP_PROP_FPS)

    width = int(
        cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    )

    height = int(
        cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    )

    if fps <= 0 or width <= 0 or height <= 0:

        cap.release()

        raise RuntimeError(
            "Invalid video properties."
        )

    output_path = (
        OUTPUT_DIR
        / (video_path.stem + "_engagement.mp4")
    )

    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height)
    )

    if not writer.isOpened():

        cap.release()

        raise RuntimeError(
            "Could not create output video."
        )

    tracker = FaceTracker()

    # Match processor frame numbers.
    # The processor starts counting from zero.

    sampled_frames = {
        item["frame_number"]: item["detections"]
        for item in report["results"]
    }

    current_students = []

    frame_number = 0

    print("\nCREATING FACE-BOX VIDEO...\n")

    try:

        while True:

            success, frame = cap.read()

            if not success:
                break

            # Update tracking on sampled frames.

            if frame_number in sampled_frames:

                current_students = tracker.update(
                    sampled_frames[frame_number]
                )

            # Draw only face boxes.
            # No skeletons, IDs, activity labels or frame text.

            for student in current_students:

                draw_student_box(
                    frame,
                    student
                )

            writer.write(frame)

            frame_number += 1

            if frame_number % 100 == 0:

                print(
                    "Processed frames:",
                    frame_number
                )

    finally:

        cap.release()
        writer.release()

    print("\nVIDEO CREATED SUCCESSFULLY")

    print("Output:", output_path)

    print(
        "Initial box status: GREY "
        "(engagement assessment not connected)"
    )


# --------------------------------------------------
# MAIN FUNCTION
# --------------------------------------------------

def main():

    report_files = list(
        REPORT_DIR.glob("*_shared_report.json")
    )

    if not report_files:

        raise FileNotFoundError(
            "No shared processor report found."
        )

    report_path = max(
        report_files,
        key=lambda path: path.stat().st_mtime
    )

    video_name = report_path.name.replace(
        "_shared_report.json",
        ""
    )

    video_path = (
        PROJECT_DIR
        / "uploads"
        / (video_name + ".mp4")
    )

    if not video_path.exists():

        raise FileNotFoundError(
            f"Input video not found: {video_path}"
        )

    print("Input video:", video_path.name)

    print("Face report:", report_path.name)

    create_annotated_video(
        video_path,
        report_path
    )


if __name__ == "__main__":

    main()
