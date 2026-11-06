
import json
from pathlib import Path
from collections import Counter


class FaceTracker:

    def __init__(
        self,
        max_missing=5,
        iou_threshold=0.15,
        max_center_distance=80
    ):

        self.max_missing = max_missing
        self.iou_threshold = iou_threshold
        self.max_center_distance = max_center_distance

        self.tracks = {}
        self.next_id = 1

    # --------------------------------------------------
    # CALCULATE IOU
    # --------------------------------------------------

    def calculate_iou(self, box1, box2):

        x1, y1, w1, h1 = box1
        x2, y2, w2, h2 = box2

        left = max(x1, x2)
        top = max(y1, y2)

        right = min(x1 + w1, x2 + w2)
        bottom = min(y1 + h1, y2 + h2)

        intersection = (
            max(0, right - left) *
            max(0, bottom - top)
        )

        union = (
            w1 * h1 +
            w2 * h2 -
            intersection
        )

        return intersection / union if union > 0 else 0.0

    # --------------------------------------------------
    # CALCULATE CENTER
    # --------------------------------------------------

    def center(self, box):

        x, y, w, h = box

        return (
            x + w / 2,
            y + h / 2
        )

    # --------------------------------------------------
    # NORMALIZE DETECTION
    # --------------------------------------------------

    def normalize_detection(self, detection):

        if "box" in detection:

            x, y, w, h = detection["box"]

        else:

            x = detection["x"]
            y = detection["y"]
            w = detection["width"]
            h = detection["height"]

        return (
            int(x),
            int(y),
            int(w),
            int(h)
        )

    # --------------------------------------------------
    # UPDATE TRACKS
    # --------------------------------------------------

    def update(self, detections):

        normalized = [
            self.normalize_detection(d)
            for d in detections
        ]

        # Increase missing count for every existing track.
        for track in self.tracks.values():

            track["missing"] += 1

        candidates = []

        # --------------------------------------------------
        # MATCH EXISTING TRACKS WITH NEW DETECTIONS
        # --------------------------------------------------

        for track_id, track in self.tracks.items():

            old_box = track["box"]
            old_center = self.center(old_box)

            for index, new_box in enumerate(normalized):

                new_center = self.center(new_box)

                dx = old_center[0] - new_center[0]
                dy = old_center[1] - new_center[1]

                distance = (dx * dx + dy * dy) ** 0.5

                iou = self.calculate_iou(
                    old_box,
                    new_box
                )

                if (
                    iou >= self.iou_threshold
                    or distance <= self.max_center_distance
                ):

                    distance_score = (
                        1 - min(
                            distance / self.max_center_distance,
                            1
                        )
                    )

                    score = iou + distance_score * 0.25

                    # Prefer tracks that have not been missing.
                    score -= track["missing"] * 0.05

                    candidates.append(
                        (score, track_id, index)
                    )

        candidates.sort(reverse=True)

        matched_tracks = set()
        matched_detections = set()

        # --------------------------------------------------
        # APPLY MATCHES
        # --------------------------------------------------

        for score, track_id, index in candidates:

            if track_id in matched_tracks:
                continue

            if index in matched_detections:
                continue

            self.tracks[track_id]["box"] = normalized[index]

            self.tracks[track_id]["missing"] = 0

            matched_tracks.add(track_id)

            matched_detections.add(index)

        # --------------------------------------------------
        # CREATE NEW STUDENT IDs
        # --------------------------------------------------

        for index, box in enumerate(normalized):

            if index in matched_detections:
                continue

            track_id = f"Student_{self.next_id:03d}"

            self.tracks[track_id] = {

                "box": box,

                "missing": 0

            }

            self.next_id += 1

        # --------------------------------------------------
        # REMOVE EXPIRED TRACKS
        # --------------------------------------------------

        expired = [

            track_id

            for track_id, track in self.tracks.items()

            if track["missing"] > self.max_missing

        ]

        for track_id in expired:

            del self.tracks[track_id]

        # --------------------------------------------------
        # IMPORTANT FIX:
        # RETURN ACTIVE AND TEMPORARILY MISSING TRACKS
        # --------------------------------------------------

        output = []

        for track_id in sorted(self.tracks.keys()):

            track = self.tracks[track_id]

            if track["missing"] <= self.max_missing:

                output.append({

                    "student_id": track_id,

                    "box": list(track["box"]),

                    "missing_frames": track["missing"],

                    "predicted": track["missing"] > 0

                })

        return output


# --------------------------------------------------
# PROCESS SHARED REPORT
# --------------------------------------------------

def process_shared_report(report_file):

    report_file = Path(report_file)

    with report_file.open(
        "r",
        encoding="utf-8"
    ) as file:

        report = json.load(file)

    tracker = FaceTracker()

    tracking_results = []

    print("\nSTUDENT TRACKING STARTED\n")

    for frame in report["results"]:

        students = tracker.update(
            frame["detections"]
        )

        tracking_results.append({

            "frame_number": frame["frame_number"],

            "timestamp_seconds": frame["timestamp_seconds"],

            "students": students,

            "visible_student_count": len(students)

        })

        print(
            f"Frame {frame['frame_number']:05d} -> "
            f"{[s['student_id'] for s in students]}"
        )

    # --------------------------------------------------
    # SAVE TRACKING REPORT
    # --------------------------------------------------

    output_file = report_file.with_name(

        report_file.stem.replace(
            "_shared_report",
            ""
        ) + "_tracking_report.json"

    )

    with output_file.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            tracking_results,
            file,
            indent=4
        )

    counts = Counter(

        student["student_id"]

        for frame in tracking_results

        for student in frame["students"]

    )

    print("\nTRACKING COMPLETED")

    print(
        "Frames tracked:",
        len(tracking_results)
    )

    print(
        "Unique temporary IDs:",
        len(counts)
    )

    print(
        "ID appearances:",
        dict(counts)
    )

    print(
        "Output:",
        output_file
    )


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    project_root = Path(__file__).resolve().parent.parent

    report_folder = (
        project_root /
        "reports" /
        "processed" /
        "faces"
    )

    report_files = list(
        report_folder.glob("*_shared_report.json")
    )

    if not report_files:

        raise FileNotFoundError(
            "Shared processor report not found."
        )

    report_file = max(
        report_files,
        key=lambda path: path.stat().st_mtime
    )

    process_shared_report(report_file)


if __name__ == "__main__":

    main()
