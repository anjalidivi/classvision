
import cv2
import json
import mediapipe as mp

from pathlib import Path
from datetime import datetime


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODEL_PATH = (
    PROJECT_ROOT
    / "face_detection"
    / "models"
    / "face_detector.tflite"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "processed"
    / "faces"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# DETECTION SETTINGS
# --------------------------------------------------

MIN_CONFIDENCE = 0.50
MIN_FACE_WIDTH = 20
MIN_FACE_HEIGHT = 20

NMS_IOU_THRESHOLD = 0.35
SAMPLE_INTERVAL = 5


# --------------------------------------------------
# CALCULATE INTERSECTION OVER UNION
# --------------------------------------------------

def calculate_iou(box1, box2):

    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2

    left = max(x1, x2)
    top = max(y1, y2)

    right = min(x1 + w1, x2 + w2)
    bottom = min(y1 + h1, y2 + h2)

    intersection_width = max(0, right - left)
    intersection_height = max(0, bottom - top)

    intersection = (
        intersection_width * intersection_height
    )

    area1 = w1 * h1
    area2 = w2 * h2

    union = area1 + area2 - intersection

    if union <= 0:
        return 0.0

    return intersection / union


# --------------------------------------------------
# REMOVE DUPLICATE FACE DETECTIONS USING NMS
# --------------------------------------------------

def remove_duplicate_detections(
    detections,
    iou_threshold=NMS_IOU_THRESHOLD
):

    if not detections:
        return []

    sorted_detections = sorted(
        detections,
        key=lambda item: item["confidence"],
        reverse=True
    )

    selected = []

    while sorted_detections:

        best = sorted_detections.pop(0)

        selected.append(best)

        remaining = []

        for detection in sorted_detections:

            iou = calculate_iou(
                best["box"],
                detection["box"]
            )

            if iou < iou_threshold:
                remaining.append(detection)

        sorted_detections = remaining

    return selected


# --------------------------------------------------
# INITIALIZE MEDIAPIPE FACE DETECTOR
# --------------------------------------------------

def create_face_detector():

    if not MODEL_PATH.exists():

        raise FileNotFoundError(
            f"Face detector model not found: {MODEL_PATH}"
        )

    BaseOptions = mp.tasks.BaseOptions

    FaceDetector = mp.tasks.vision.FaceDetector

    FaceDetectorOptions = (
        mp.tasks.vision.FaceDetectorOptions
    )

    RunningMode = mp.tasks.vision.RunningMode

    options = FaceDetectorOptions(

        base_options=BaseOptions(
            model_asset_path=str(MODEL_PATH)
        ),

        running_mode=RunningMode.IMAGE,

        min_detection_confidence=MIN_CONFIDENCE,

        min_suppression_threshold=0.30
    )

    return FaceDetector.create_from_options(options)


# --------------------------------------------------
# DETECT FACES IN ONE FRAME
# --------------------------------------------------

def process_frame(frame, detector):

    frame_height, frame_width = frame.shape[:2]

    rgb_frame = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2RGB
    )

    mp_image = mp.Image(
        image_format=mp.ImageFormat.SRGB,
        data=rgb_frame
    )

    result = detector.detect(mp_image)

    detections = []

    for detection in result.detections:

        if not detection.categories:
            continue

        confidence = float(
            detection.categories[0].score
        )

        if confidence < MIN_CONFIDENCE:
            continue

        bbox = detection.bounding_box

        x = int(bbox.origin_x)
        y = int(bbox.origin_y)

        width = int(bbox.width)
        height = int(bbox.height)

        # Keep coordinates inside the frame.

        x = max(0, x)
        y = max(0, y)

        width = min(width, frame_width - x)
        height = min(height, frame_height - y)

        # Reject very small detections.

        if width < MIN_FACE_WIDTH:
            continue

        if height < MIN_FACE_HEIGHT:
            continue

        # Reject unusually shaped detections.

        aspect_ratio = width / max(height, 1)

        if not 0.65 <= aspect_ratio <= 1.50:
            continue

        detections.append({

            "box": [
                x,
                y,
                width,
                height
            ],

            "confidence": round(confidence, 4)

        })

    # Remove duplicate overlapping boxes.

    detections = remove_duplicate_detections(
        detections
    )

    return detections


# --------------------------------------------------
# PROCESS VIDEO
# --------------------------------------------------

def process_video(
    video_path,
    sample_interval=SAMPLE_INTERVAL
):

    video_path = Path(video_path)

    if not video_path.exists():

        raise FileNotFoundError(
            f"Video not found: {video_path}"
        )

    if sample_interval < 1:

        raise ValueError(
            "sample_interval must be at least 1."
        )

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():

        raise RuntimeError(
            f"Could not open video: {video_path}"
        )

    fps = cap.get(cv2.CAP_PROP_FPS)

    total_frames = int(
        cap.get(cv2.CAP_PROP_FRAME_COUNT)
    )

    if fps <= 0:
        fps = 30.0

    detector = create_face_detector()

    results = []

    frame_number = 0

    total_detections = 0

    print("\n====================================")
    print("       PROCESSING VIDEO")
    print("====================================")

    print("Video:", video_path.name)
    print("FPS:", round(fps, 2))
    print("Total frames:", total_frames)
    print("Sampling interval:", sample_interval)

    try:

        while True:

            success, frame = cap.read()

            if not success:
                break

            if frame_number % sample_interval == 0:

                detections = process_frame(
                    frame,
                    detector
                )

                visible_face_count = len(
                    detections
                )

                total_detections += (
                    visible_face_count
                )

                timestamp = frame_number / fps

                frame_result = {

                    "frame_number": frame_number,

                    "timestamp_seconds": round(
                        timestamp,
                        3
                    ),

                    "detections": detections,

                    "visible_face_count": (
                        visible_face_count
                    )

                }

                results.append(frame_result)

                print(
                    f"Frame {frame_number:05d} | "
                    f"Faces: {visible_face_count}"
                )

            frame_number += 1

    finally:

        cap.release()
        detector.close()

    # --------------------------------------------------
    # SAVE REPORT
    # --------------------------------------------------

    report = {

        "video_name": video_path.name,

        "fps": round(fps, 2),

        "total_frames": total_frames,

        "processed_frames": len(results),

        "sample_interval": sample_interval,

        "total_detections": total_detections,

        "processed_at": datetime.now().isoformat(),

        "results": results

    }

    output_file = (
        OUTPUT_DIR
        / f"{video_path.stem}_shared_report.json"
    )

    with output_file.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            indent=4
        )

    # --------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------

    print("\n====================================")
    print("       PROCESSING COMPLETED")
    print("====================================")

    print("Processed frames:", len(results))

    print("Total face detections:", total_detections)

    print(
        "Average faces per sampled frame:",
        round(
            total_detections / max(len(results), 1),
            2
        )
    )

    print("Report saved:", output_file)

    return report


# --------------------------------------------------
# MAIN FUNCTION
# --------------------------------------------------

def main():

    video_path = (
        PROJECT_ROOT
        / "uploads"
        / "classroom_test_30_seconds.mp4"
    )

    process_video(
        video_path,
        sample_interval=SAMPLE_INTERVAL
    )


if __name__ == "__main__":

    main()
