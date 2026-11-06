
import cv2
import json
import sys
import shutil
import subprocess

from pathlib import Path
from collections import Counter
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared_video_processor import create_face_detector, process_frame
from face_tracker import FaceTracker
from expression_predictor import ExpressionPredictor

UPLOAD_DIR = PROJECT_ROOT / "uploads"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "processed" / "annotated"
REPORT_DIR = PROJECT_ROOT / "reports" / "processed" / "activities"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def find_ffmpeg():
    ffmpeg = shutil.which("ffmpeg")

    if ffmpeg:
        return ffmpeg

    possible_paths = [
        Path(
            r"C:\Users\Admin\Downloads\ffmpeg-9.0.2-essentials_build"
            r"\ffmpeg-9.0.2-essentials_build\bin\ffmpeg.exe"
        ),
        Path(r"C:\ffmpeg-9.0.2-essentials_build\bin\ffmpeg.exe")
    ]

    for path in possible_paths:
        if path.exists():
            return str(path)

    raise FileNotFoundError(
        "FFmpeg was not found. Please check your FFmpeg installation."
    )


def convert_to_browser_video(input_video):
    input_video = Path(input_video)

    output_video = (
        input_video.parent
        / f"{input_video.stem.replace('_integrated', '')}_browser.mp4"
    )

    ffmpeg = find_ffmpeg()

    print("\n====================================")
    print("       H.264 VIDEO CONVERSION")
    print("====================================")

    command = [
        ffmpeg,
        "-y",
        "-i", str(input_video),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-an",
        str(output_video)
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False
    )

    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg conversion failed:\n" + result.stderr[-3000:]
        )

    if not output_video.exists() or output_video.stat().st_size == 0:
        raise RuntimeError(
            "H.264 conversion finished without creating a valid output file."
        )

    print("H.264 conversion successful!")
    print("Browser video:", output_video)
    print(
        "File size:",
        round(output_video.stat().st_size / (1024 * 1024), 2),
        "MB"
    )

    return output_video


def draw_student_boxes(frame, display_tracks):
    """Draw all currently retained tracks on every video frame."""

    for student in display_tracks:
        x, y, w, h = student["box"]
        student_id = student["student_id"]

        x = int(x)
        y = int(y)
        w = int(w)
        h = int(h)

        # Green for a fresh detection, yellow for a retained track.
        if student.get("predicted", False):
            color = (0, 200, 255)
        else:
            color = (0, 200, 0)

        cv2.rectangle(
            frame,
            (x, y),
            (x + w, y + h),
            color,
            2
        )

        cv2.putText(
            frame,
            student_id,
            (x, max(y - 10, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2
        )


def process_classroom_video(video_path, sample_interval=5):

    video_path = Path(video_path)

    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    if sample_interval < 1:
        raise ValueError("sample_interval must be at least 1.")

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        raise RuntimeError("Unable to open the classroom video.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    output_video = OUTPUT_DIR / f"{video_path.stem}_integrated.mp4"
    output_json = REPORT_DIR / f"{video_path.stem}_integrated_report.json"

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    writer = cv2.VideoWriter(
        str(output_video),
        fourcc,
        fps,
        (width, height)
    )

    if not writer.isOpened():
        cap.release()
        raise RuntimeError("Unable to create the output video.")

    detector = None
    tracker = FaceTracker()

    expression_counts = Counter()
    student_expression_counts = {}
    latest_expressions = {}
    frame_results = []

    # This list is maintained between detection frames.
    display_tracks = []

    frame_number = 0
    total_detections = 0
    processed_frames = 0
    unique_students = set()

    try:
        print("\nINTEGRATED CLASSROOM PROCESSING STARTED")
        print("Video:", video_path.name)
        print("Resolution:", width, "x", height)
        print("FPS:", round(fps, 2))
        print("Sampling interval:", sample_interval)

        detector = create_face_detector()
        predictor = ExpressionPredictor()

        while True:
            success, frame = cap.read()

            if not success:
                break

            # -----------------------------------------
            # STEP 1: RUN DETECTION ONLY ON SAMPLED FRAMES
            # -----------------------------------------

            if frame_number % sample_interval == 0:

                detections = process_frame(frame, detector)

                processed_frames += 1
                total_detections += len(detections)

                for detection in detections:

                    x, y, w, h = detection["box"]
                    face_crop = frame[y:y + h, x:x + w]

                    if face_crop.size == 0:
                        continue

                    try:
                        prediction = predictor.predict(face_crop)

                        detection["expression"] = prediction["expression"]
                        detection["expression_confidence"] = (
                            prediction["confidence"]
                        )

                        expression_counts[
                            prediction["expression"]
                        ] += 1

                    except Exception as error:
                        print("Expression prediction error:", error)

                        detection["expression"] = "unknown"
                        detection["expression_confidence"] = 0.0

                # Update tracker only on sampled frames.
                tracked_faces = tracker.update(detections)

                detection_lookup = {
                    tuple(item["box"]): item
                    for item in detections
                }

                current_frame_students = []

                for student in tracked_faces:

                    student_id = student["student_id"]

                    detection = detection_lookup.get(
                        tuple(student["box"]),
                        {}
                    )

                    expression = detection.get(
                        "expression",
                        latest_expressions.get(student_id, "unknown")
                    )

                    confidence = detection.get(
                        "expression_confidence",
                        0.0
                    )

                    # Update the last known expression only
                    # when a fresh detection is available.
                    if detection and expression != "unknown":
                        latest_expressions[student_id] = expression

                    unique_students.add(student_id)

                    student_expression_counts.setdefault(
                        student_id,
                        Counter()
                    )

                    if detection and expression != "unknown":
                        student_expression_counts[
                            student_id
                        ][expression] += 1

                    x, y, w, h = student["box"]

                    current_frame_students.append({
                        "student_id": student_id,
                        "box": [
                            int(x),
                            int(y),
                            int(w),
                            int(h)
                        ],
                        "expression": expression,
                        "expression_confidence": round(
                            float(confidence),
                            4
                        )
                    })

                # IMPORTANT:
                # Store the latest tracks. Do not clear them
                # on the four frames between detections.
                display_tracks = [
                    dict(student)
                    for student in tracked_faces
                ]

                active_ids = {
                    student["student_id"]
                    for student in display_tracks
                }

                # Remove cached expressions for expired tracks.
                latest_expressions = {
                    student_id: expression
                    for student_id, expression in latest_expressions.items()
                    if student_id in active_ids
                }

                frame_results.append({
                    "frame_number": frame_number,
                    "timestamp_seconds": round(
                        frame_number / fps,
                        3
                    ),
                    "students": current_frame_students,
                    "visible_student_count": len(current_frame_students)
                })

                if frame_number % 100 == 0:
                    print(
                        f"Frame {frame_number:05d} | "
                        f"Faces: {len(detections)} | "
                        f"Tracked: {len(tracked_faces)}"
                    )

            # -----------------------------------------
            # STEP 2: DRAW ON EVERY FRAME
            # -----------------------------------------

            # This is OUTSIDE the detection condition.
            # Therefore boxes remain visible between sampled frames.
            draw_student_boxes(frame, display_tracks)

            # Write every frame to the output video.
            writer.write(frame)

            frame_number += 1

    finally:
        cap.release()
        writer.release()

        if detector is not None:
            detector.close()

    # -----------------------------------------
    # H.264 CONVERSION
    # -----------------------------------------

    print("\nConverting annotated video to H.264...")

    browser_video = convert_to_browser_video(output_video)

    # -----------------------------------------
    # PREPARE REPORT
    # -----------------------------------------

    report = {
        "video_name": video_path.name,
        "processed_at": datetime.now().isoformat(),
        "video_fps": round(fps, 2),
        "video_width": width,
        "video_height": height,
        "total_video_frames": total_frames,
        "processed_frames": processed_frames,
        "sample_interval": sample_interval,
        "total_face_detections": total_detections,
        "unique_temporary_student_ids": len(unique_students),
        "student_ids": sorted(unique_students),
        "expression_distribution": dict(expression_counts),

        "student_expression_summary": {
            student_id: dict(counts)
            for student_id, counts in student_expression_counts.items()
        },

        "results": frame_results,

        "annotated_video": str(
            browser_video.relative_to(PROJECT_ROOT)
        ),

        "original_annotated_video": str(
            output_video.relative_to(PROJECT_ROOT)
        )
    }

    with open(output_json, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    print("\n====================================")
    print("       PROCESSING COMPLETED")
    print("====================================")

    print("Frames processed:", processed_frames)
    print("Total face detections:", total_detections)
    print("Unique temporary IDs:", len(unique_students))
    print("Expression distribution:", dict(expression_counts))
    print("Original annotated video:", output_video)
    print("Browser-compatible video:", browser_video)
    print("JSON report:", output_json)

    return report


if __name__ == "__main__":

    sample_video = UPLOAD_DIR / "classroom_test_30_seconds.mp4"

    process_classroom_video(
        sample_video,
        sample_interval=5
    )
