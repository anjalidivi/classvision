import json
from pathlib import Path
from collections import Counter


class FaceTracker:
    """
    Lightweight motion-aware face tracker.

    Detection frames are matched against a predicted box based on the
    track's recent movement. This reduces ID switches when students move
    between sampled detection frames.

    Note: without a face-embedding/re-identification model, identity cannot
    be guaranteed after long occlusions or when students cross paths.
    """

    def __init__(
        self,
        max_missing=5,
        iou_threshold=0.15,
        max_center_distance=80,
        max_velocity=45,
    ):
        self.max_missing = max_missing
        self.iou_threshold = iou_threshold
        self.max_center_distance = max_center_distance
        self.max_velocity = max_velocity

        self.tracks = {}
        self.next_id = 1

    @staticmethod
    def calculate_iou(box1, box2):
        x1, y1, w1, h1 = box1
        x2, y2, w2, h2 = box2

        left = max(x1, x2)
        top = max(y1, y2)
        right = min(x1 + w1, x2 + w2)
        bottom = min(y1 + h1, y2 + h2)

        intersection = max(0, right - left) * max(0, bottom - top)
        union = w1 * h1 + w2 * h2 - intersection
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def center(box):
        x, y, w, h = box
        return x + w / 2.0, y + h / 2.0

    @staticmethod
    def normalize_detection(detection):
        if "box" in detection:
            x, y, w, h = detection["box"]
        else:
            x = detection["x"]
            y = detection["y"]
            w = detection["width"]
            h = detection["height"]

        return int(x), int(y), max(1, int(w)), max(1, int(h))

    @staticmethod
    def shift_box(box, dx, dy):
        x, y, w, h = box
        return int(round(x + dx)), int(round(y + dy)), w, h

    def _predicted_box(self, track):
        # Velocity is measured per detection update. Limit extrapolation so
        # a long occlusion cannot send a track far across the image.
        steps = min(track["missing"], 2)
        vx, vy = track["velocity"]
        return self.shift_box(
            track["box"],
            vx * steps,
            vy * steps,
        )

    def _match_score(self, track, predicted_box, detection_box):
        predicted_center = self.center(predicted_box)
        detection_center = self.center(detection_box)

        dx = predicted_center[0] - detection_center[0]
        dy = predicted_center[1] - detection_center[1]
        distance = (dx * dx + dy * dy) ** 0.5

        _, _, pw, ph = predicted_box
        _, _, dw, dh = detection_box

        # Reject implausible size changes; these often indicate a different
        # student's face has been matched to this track.
        width_ratio = max(pw, dw) / max(1, min(pw, dw))
        height_ratio = max(ph, dh) / max(1, min(ph, dh))
        if width_ratio > 2.5 or height_ratio > 2.5:
            return None

        iou = self.calculate_iou(predicted_box, detection_box)
        face_scale = max(pw, ph, dw, dh)
        distance_gate = max(
            self.max_center_distance,
            face_scale * 1.5,
        )
        if distance > distance_gate and iou < self.iou_threshold:
            return None

        distance_score = max(0.0, 1.0 - distance / max(1.0, distance_gate))
        size_score = 1.0 - min(
            1.0,
            (abs(pw - dw) / max(pw, dw) +
             abs(ph - dh) / max(ph, dh)) / 2.0,
        )

        # Position prediction is weighted more heavily than raw overlap.
        return (2.0 * iou) + (1.5 * distance_score) + (0.5 * size_score)

    def update(self, detections):
        normalized = [
            self.normalize_detection(detection)
            for detection in detections
        ]

        for track in self.tracks.values():
            track["missing"] += 1

        candidates = []
        for track_id, track in self.tracks.items():
            predicted_box = self._predicted_box(track)

            for index, detection_box in enumerate(normalized):
                score = self._match_score(
                    track,
                    predicted_box,
                    detection_box,
                )
                if score is not None:
                    # Slightly prefer tracks that were seen recently.
                    score -= track["missing"] * 0.08
                    candidates.append((score, track_id, index))

        candidates.sort(key=lambda item: item[0], reverse=True)

        matched_tracks = set()
        matched_detections = set()

        for _, track_id, index in candidates:
            if track_id in matched_tracks or index in matched_detections:
                continue

            track = self.tracks[track_id]
            new_box = normalized[index]

            old_center = self.center(track["box"])
            new_center = self.center(new_box)
            elapsed = max(1, track["missing"])

            measured_vx = (new_center[0] - old_center[0]) / elapsed
            measured_vy = (new_center[1] - old_center[1]) / elapsed

            # Smooth velocity to avoid reacting sharply to noisy detections.
            old_vx, old_vy = track["velocity"]
            vx = 0.6 * old_vx + 0.4 * measured_vx
            vy = 0.6 * old_vy + 0.4 * measured_vy

            speed = (vx * vx + vy * vy) ** 0.5
            if speed > self.max_velocity:
                scale = self.max_velocity / speed
                vx *= scale
                vy *= scale

            track["box"] = new_box
            track["velocity"] = (vx, vy)
            track["missing"] = 0
            track["hits"] += 1
            track["age"] += 1

            matched_tracks.add(track_id)
            matched_detections.add(index)

        for index, box in enumerate(normalized):
            if index in matched_detections:
                continue

            track_id = f"Student_{self.next_id:03d}"
            self.tracks[track_id] = {
                "box": box,
                "velocity": (0.0, 0.0),
                "missing": 0,
                "hits": 1,
                "age": 1,
            }
            self.next_id += 1

        expired = [
            track_id
            for track_id, track in self.tracks.items()
            if track["missing"] > self.max_missing
        ]
        for track_id in expired:
            del self.tracks[track_id]

        output = []
        for track_id in sorted(self.tracks):
            track = self.tracks[track_id]
            if track["missing"] <= self.max_missing:
                output.append({
                    "student_id": track_id,
                    "box": list(track["box"]),
                    "missing_frames": track["missing"],
                    "predicted": track["missing"] > 0,
                })

        return output


def process_shared_report(report_file):
    report_file = Path(report_file)

    with report_file.open("r", encoding="utf-8") as file:
        report = json.load(file)

    tracker = FaceTracker()
    tracking_results = []

    print("\nSTUDENT TRACKING STARTED\n")

    for frame in report["results"]:
        students = tracker.update(frame["detections"])

        tracking_results.append({
            "frame_number": frame["frame_number"],
            "timestamp_seconds": frame["timestamp_seconds"],
            "students": students,
            "visible_student_count": sum(
                1 for student in students if not student["predicted"]
            ),
        })

        print(
            f"Frame {frame['frame_number']:05d} -> "
            f"{[student['student_id'] for student in students]}"
        )

    output_file = report_file.with_name(
        report_file.stem.replace("_shared_report", "")
        + "_tracking_report.json"
    )

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(tracking_results, file, indent=4)

    counts = Counter(
        student["student_id"]
        for frame in tracking_results
        for student in frame["students"]
    )

    print("\nTRACKING COMPLETED")
    print("Frames tracked:", len(tracking_results))
    print("Unique temporary IDs:", len(counts))
    print("ID appearances:", dict(counts))
    print("Output:", output_file)


def main():
    project_root = Path(__file__).resolve().parent.parent
    report_folder = (
        project_root / "reports" / "processed" / "faces"
    )

    report_files = list(report_folder.glob("*_shared_report.json"))
    if not report_files:
        raise FileNotFoundError("Shared processor report not found.")

    report_file = max(
        report_files,
        key=lambda path: path.stat().st_mtime,
    )
    process_shared_report(report_file)


if __name__ == "__main__":
    main()
