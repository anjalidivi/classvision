
import cv2
import json
import mediapipe as mp

from pathlib import Path
from datetime import datetime


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent

MODEL_PATH = (
    ROOT / "activity_detection" / "models"
    / "pose_landmarker_lite.task"
)

VIDEO_PATH = (
    ROOT / "uploads" / "classroom_test_30_seconds.mp4"
)

OUTPUT_DIR = ROOT / "reports" / "processed" / "activities"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

SAMPLE_INTERVAL = 5

MAX_POSES = 10

MIN_VISIBILITY = 0.40

# MediaPipe Pose landmark indexes
NOSE = 0
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28


# --------------------------------------------------
# SKELETON CONNECTIONS
# --------------------------------------------------

CONNECTIONS = [
    (11, 12),
    (11, 13),
    (13, 15),
    (12, 14),
    (14, 16),
    (11, 23),
    (12, 24),
    (23, 24),
    (23, 25),
    (25, 27),
    (24, 26),
    (26, 28),
    (0, 11),
    (0, 12)
]


# --------------------------------------------------
# LANDMARK HELPERS
# --------------------------------------------------

def visible(landmarks, index):

    point = landmarks[index]

    return (
        point.visibility is not None
        and point.visibility >= MIN_VISIBILITY
    )


def average_y(landmarks, first, second):

    return (
        landmarks[first].y
        + landmarks[second].y
    ) / 2


def average_x(landmarks, first, second):

    return (
        landmarks[first].x
        + landmarks[second].x
    ) / 2


# --------------------------------------------------
# ACTIVITY CLASSIFICATION
# --------------------------------------------------

def classify_activity(landmarks):

    activities = []

    # Check required landmarks.

    shoulders_visible = (
        visible(landmarks, LEFT_SHOULDER)
        and visible(landmarks, RIGHT_SHOULDER)
    )

    # 1. HAND RAISING

    hand_raised = False

    if shoulders_visible:

        shoulder_y = average_y(
            landmarks,
            LEFT_SHOULDER,
            RIGHT_SHOULDER
        )

        if (
            visible(landmarks, LEFT_WRIST)
            and landmarks[LEFT_WRIST].y < shoulder_y - 0.04
        ):
            hand_raised = True

        if (
            visible(landmarks, RIGHT_WRIST)
            and landmarks[RIGHT_WRIST].y < shoulder_y - 0.04
        ):
            hand_raised = True

    if hand_raised:
        activities.append("HAND_RAISED")

    # 2. HEAD DOWN

    head_down = False

    if (
        visible(landmarks, NOSE)
        and shoulders_visible
    ):

        shoulder_y = average_y(
            landmarks,
            LEFT_SHOULDER,
            RIGHT_SHOULDER
        )

        nose_y = landmarks[NOSE].y

        if nose_y > shoulder_y + 0.12:
            head_down = True

    if head_down:
        activities.append("HEAD_DOWN")

    # 3. STANDING ESTIMATION

    standing = False

    hips_visible = (
        visible(landmarks, LEFT_HIP)
        and visible(landmarks, RIGHT_HIP)
    )

    knees_visible = (
        visible(landmarks, LEFT_KNEE)
        and visible(landmarks, RIGHT_KNEE)
    )

    ankles_visible = (
        visible(landmarks, LEFT_ANKLE)
        and visible(landmarks, RIGHT_ANKLE)
    )

    if hips_visible and knees_visible:

        hip_y = average_y(
            landmarks,
            LEFT_HIP,
            RIGHT_HIP
        )

        knee_y = average_y(
            landmarks,
            LEFT_KNEE,
            RIGHT_KNEE
        )

        # Approximate posture rule.
        # Requires further validation on classroom videos.

        if hip_y < knee_y - 0.08:
            standing = True

    if standing:
        activities.append("STANDING")

    # 4. BASIC POSTURE STATUS

    if not activities:
        activities.append("NO_CLEAR_ACTIVITY")

    return activities


# --------------------------------------------------
# DRAW POSE LANDMARKS
# --------------------------------------------------

def draw_pose(frame, landmarks):

    height, width = frame.shape[:2]

    points = []

    for landmark in landmarks:

        x = int(landmark.x * width)
        y = int(landmark.y * height)

        points.append((x, y))

    # Draw skeleton lines.

    for start, end in CONNECTIONS:

        if (
            visible(landmarks, start)
            and visible(landmarks, end)
        ):

            cv2.line(
                frame,
                points[start],
                points[end],
                (0, 255, 255),
                2
            )

    # Draw visible joints.

    for index, point in enumerate(points):

        if visible(landmarks, index):

            cv2.circle(
                frame,
                point,
                4,
                (0, 255, 0),
                -1
            )


# --------------------------------------------------
# PROCESS VIDEO
# --------------------------------------------------

def process_video(video_path):

    video_path = Path(video_path)

    if not MODEL_PATH.exists():

        raise FileNotFoundError(
            f"Pose model missing: {MODEL_PATH}"
        )

    if not video_path.exists():

        raise FileNotFoundError(
            f"Video missing: {video_path}"
        )

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():

        raise RuntimeError("Could not open video.")

    fps = cap.get(cv2.CAP_PROP_FPS)

    total_frames = int(
        cap.get(cv2.CAP_PROP_FRAME_COUNT)
    )

    width = int(
        cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    )

    height = int(
        cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    )

    if fps <= 0:
        fps = 30.0

    output_video = (
        OUTPUT_DIR
        / f"{video_path.stem}_pose_annotated.mp4"
    )

    output_json = (
        OUTPUT_DIR
        / f"{video_path.stem}_activity_report.json"
    )

    writer = cv2.VideoWriter(
        str(output_video),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height)
    )

    if not writer.isOpened():

        cap.release()

        raise RuntimeError(
            "Could not create output video."
        )

    BaseOptions = mp.tasks.BaseOptions
    PoseLandmarker = mp.tasks.vision.PoseLandmarker
    PoseLandmarkerOptions = (
        mp.tasks.vision.PoseLandmarkerOptions
    )
    RunningMode = mp.tasks.vision.RunningMode

    options = PoseLandmarkerOptions(

        base_options=BaseOptions(
            model_asset_path=str(MODEL_PATH)
        ),

        running_mode=RunningMode.VIDEO,

        num_poses=MAX_POSES,

        min_pose_detection_confidence=0.35,

        min_pose_presence_confidence=0.35,

        min_tracking_confidence=0.35
    )

    report = []

    frame_number = 0

    latest_poses = []

    print("\n================================")
    print(" CLASSROOM ACTIVITY DETECTION")
    print("================================")

    print("Video:", video_path.name)
    print("Total frames:", total_frames)
    print("Sampling interval:", SAMPLE_INTERVAL)

    try:

        with PoseLandmarker.create_from_options(
            options
        ) as landmarker:

            while True:

                success, frame = cap.read()

                if not success:
                    break

                if frame_number % SAMPLE_INTERVAL == 0:

                    rgb = cv2.cvtColor(
                        frame,
                        cv2.COLOR_BGR2RGB
                    )

                    mp_image = mp.Image(
                        image_format=mp.ImageFormat.SRGB,
                        data=rgb
                    )

                    timestamp_ms = int(
                        frame_number * 1000 / fps
                    )

                    result = landmarker.detect_for_video(
                        mp_image,
                        timestamp_ms
                    )

                    latest_poses = []

                    frame_activities = []

                    if result.pose_landmarks:

                        for pose_index, landmarks in enumerate(
                            result.pose_landmarks
                        ):

                            activities = classify_activity(
                                landmarks
                            )

                            latest_poses.append({
                                "landmarks": landmarks,
                                "activities": activities
                            })

                            frame_activities.append({

                                "pose_id": (
                                    f"Pose_{pose_index + 1:02d}"
                                ),

                                "activities": activities

                            })

                    report.append({

                        "frame_number": frame_number,

                        "timestamp_seconds": round(
                            frame_number / fps,
                            3
                        ),

                        "person_count": len(latest_poses),

                        "poses": frame_activities

                    })

                    print(
                        f"Frame {frame_number:05d} | "
                        f"People: {len(latest_poses)}"
                    )

                # Draw the latest sampled pose on this frame.

                annotated = frame.copy()

                for pose in latest_poses:

                    draw_pose(
                        annotated,
                        pose["landmarks"]
                    )

                    label = ", ".join(
                        pose["activities"]
                    )

                    nose = pose["landmarks"][NOSE]

                    label_x = max(
                        5,
                        min(width - 250, int(nose.x * width))
                    )

                    label_y = max(
                        25,
                        min(height - 5, int(nose.y * height) - 10)
                    )

                    cv2.putText(
                        annotated,
                        label,
                        (label_x, label_y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        (0, 255, 0),
                        1,
                        cv2.LINE_AA
                    )

                writer.write(annotated)

                frame_number += 1

    finally:

        cap.release()
        writer.release()

    final_report = {

        "video_name": video_path.name,

        "fps": round(fps, 2),

        "total_frames": total_frames,

        "processed_frames": len(report),

        "sample_interval": SAMPLE_INTERVAL,

        "processed_at": datetime.now().isoformat(),

        "results": report

    }

    with output_json.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            final_report,
            file,
            indent=4
        )

    print("\n================================")
    print(" PROCESSING COMPLETED")
    print("================================")

    print("Processed frames:", len(report))
    print("Annotated video:", output_video)
    print("Activity report:", output_json)


# --------------------------------------------------
# MAIN
# --------------------------------------------------

if __name__ == "__main__":

    process_video(VIDEO_PATH)
