
import cv2
import json
import mediapipe as mp

from pathlib import Path
from datetime import datetime


# ============================================
# 1. PROJECT PATHS
# ============================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

FRAMES_DIR = PROJECT_ROOT / "reports" / "processed" / "frames"

MODEL_PATH = (
    PROJECT_ROOT
    / "face_detection"
    / "models"
    / "face_detector.tflite"
)

OUTPUT_DIR = PROJECT_ROOT / "reports" / "processed" / "faces"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================
# 2. CHECK FILES
# ============================================

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"Model not found: {MODEL_PATH}"
    )

if not FRAMES_DIR.exists():
    raise FileNotFoundError(
        f"Frames directory not found: {FRAMES_DIR}"
    )

video_folders = [
    folder
    for folder in FRAMES_DIR.iterdir()
    if folder.is_dir() and list(folder.glob("*.jpg"))
]

if not video_folders:
    raise FileNotFoundError("No video frames found.")

# Select latest processed video.
video_folder = max(
    video_folders,
    key=lambda folder: folder.stat().st_mtime
)

frame_paths = sorted(video_folder.glob("*.jpg"))

print("\nMEDIAPIPE FACE DETECTOR")
print("Model:", MODEL_PATH.name)
print("Video:", video_folder.name)
print("Total frames:", len(frame_paths))


# ============================================
# 3. INITIALIZE MEDIAPIPE
# ============================================

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
    min_detection_confidence=0.30,
    min_suppression_threshold=0.30
)


# ============================================
# 4. FACE DETECTION
# ============================================

results = []

total_faces = 0
processed_frames = 0

with FaceDetector.create_from_options(options) as detector:

    for frame_path in frame_paths:

        # Read frame.
        image = cv2.imread(str(frame_path))

        if image is None:
            print("Cannot read:", frame_path.name)
            continue

        height, width = image.shape[:2]

        # Convert BGR image to RGB.
        rgb_image = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2RGB
        )

        # Create MediaPipe image.
        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_image
        )

        # Detect faces.
        detection_result = detector.detect(mp_image)

        frame_faces = []

        for index, detection in enumerate(
            detection_result.detections,
            start=1
        ):

            bbox = detection.bounding_box

            x = max(0, bbox.origin_x)
            y = max(0, bbox.origin_y)

            x2 = min(width, bbox.origin_x + bbox.width)
            y2 = min(height, bbox.origin_y + bbox.height)

            w = max(0, x2 - x)
            h = max(0, y2 - y)

            confidence = (
                float(detection.categories[0].score)
                if detection.categories
                else 0.0
            )

            frame_faces.append({
                "temporary_detection_number": index,
                "x": int(x),
                "y": int(y),
                "width": int(w),
                "height": int(h),
                "confidence": round(confidence, 4)
            })

        face_count = len(frame_faces)

        total_faces += face_count
        processed_frames += 1

        results.append({
            "frame": frame_path.name,
            "face_count": face_count,
            "faces": frame_faces
        })

        print(
            f"{frame_path.name}: "
            f"{face_count} face(s) detected"
        )

        # Release image data.
        del image
        del rgb_image
        del mp_image


# ============================================
# 5. SAVE JSON REPORT
# ============================================

average_faces = (
    round(total_faces / processed_frames, 2)
    if processed_frames > 0
    else 0
)

report = {
    "detector": "MediaPipe Face Detector Full Range",
    "model": MODEL_PATH.name,
    "video_folder": video_folder.name,
    "processed_at": datetime.now().isoformat(),
    "total_frames": processed_frames,
    "total_face_detections": total_faces,
    "average_faces_per_frame": average_faces,
    "face_images_saved": False,
    "frames": results
}

output_file = (
    OUTPUT_DIR
    / f"{video_folder.name}_mediapipe_faces.json"
)

with open(output_file, "w", encoding="utf-8") as file:
    json.dump(report, file, indent=4)


# ============================================
# 6. FINAL SUMMARY
# ============================================

print("\n" + "=" * 45)
print("FACE DETECTION COMPLETED")
print("=" * 45)

print("Frames processed:", processed_frames)
print("Total face detections:", total_faces)
print("Average faces per frame:", average_faces)
print("Report saved:", output_file)
print("Face images saved: No")

print("=" * 45)
