import cv2
import numpy as np


class OpticalFlowTracker:
    """
    Tracks face-box movement between detector frames using Lucas-Kanade
    optical flow. Forward/backward validation helps reject points that have
    drifted onto the background.
    """

    def __init__(
        self,
        max_corners=40,
        quality_level=0.01,
        min_distance=4,
        max_error=30.0,
        forward_backward_threshold=1.5,
    ):
        self.max_corners = max_corners
        self.quality_level = quality_level
        self.min_distance = min_distance
        self.max_error = max_error
        self.forward_backward_threshold = forward_backward_threshold

        self.previous_gray = None
        self.student_points = {}

    @staticmethod
    def to_gray(frame):
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    @staticmethod
    def _clip_box(box, frame_width, frame_height):
        x, y, w, h = map(int, box)
        x1 = max(0, min(frame_width - 1, x))
        y1 = max(0, min(frame_height - 1, y))
        x2 = max(x1 + 1, min(frame_width, x + w))
        y2 = max(y1 + 1, min(frame_height, y + h))
        return [x1, y1, x2 - x1, y2 - y1]

    def detect_features(self, gray, box):
        height, width = gray.shape
        x, y, w, h = self._clip_box(box, width, height)

        # Avoid extremely small regions that cannot provide reliable points.
        if w < 8 or h < 8:
            return None

        roi = gray[y:y + h, x:x + w]
        points = cv2.goodFeaturesToTrack(
            roi,
            maxCorners=self.max_corners,
            qualityLevel=self.quality_level,
            minDistance=self.min_distance,
            blockSize=3,
        )

        if points is None:
            return None

        points[:, 0, 0] += x
        points[:, 0, 1] += y
        return points.astype(np.float32)

    def reset(self, frame, tracks):
        gray = self.to_gray(frame)
        self.previous_gray = gray
        self.student_points = {}

        for student in tracks:
            student_id = student["student_id"]
            points = self.detect_features(gray, student["box"])
            if points is not None and len(points) >= 3:
                self.student_points[student_id] = points

    def _valid_flow_points(self, old_points, new_points, status, error,
                           backward_points, backward_status):
        if status is None or backward_status is None:
            return None, None

        valid = status.reshape(-1).astype(bool)
        valid &= backward_status.reshape(-1).astype(bool)

        if error is not None:
            valid &= error.reshape(-1) < self.max_error

        old = old_points.reshape(-1, 2)
        new = new_points.reshape(-1, 2)
        backward = backward_points.reshape(-1, 2)

        fb_error = np.linalg.norm(old - backward, axis=1)
        valid &= fb_error <= self.forward_backward_threshold

        good_old = old[valid]
        good_new = new[valid]

        if len(good_new) < 3:
            return None, None

        # Remove motion outliers using the median displacement.
        displacement = good_new - good_old
        median_motion = np.median(displacement, axis=0)
        residual = np.linalg.norm(displacement - median_motion, axis=1)
        inliers = residual <= max(2.5, self.forward_backward_threshold * 2)

        good_old = good_old[inliers]
        good_new = good_new[inliers]

        if len(good_new) < 3:
            return None, None

        return good_old, good_new

    def update(self, frame, tracks):
        current_gray = self.to_gray(frame)

        if self.previous_gray is None:
            self.reset(frame, tracks)
            return tracks

        frame_height, frame_width = current_gray.shape
        updated_tracks = []
        new_student_points = {}

        for original_student in tracks:
            student = dict(original_student)
            student_id = student["student_id"]
            x, y, w, h = map(int, student["box"])

            points = self.student_points.get(student_id)
            if points is None or len(points) < 3:
                points = self.detect_features(
                    self.previous_gray,
                    student["box"],
                )

            if points is not None and len(points) >= 3:
                next_points, status, error = cv2.calcOpticalFlowPyrLK(
                    self.previous_gray,
                    current_gray,
                    points,
                    None,
                    winSize=(21, 21),
                    maxLevel=3,
                    criteria=(
                        cv2.TERM_CRITERIA_EPS |
                        cv2.TERM_CRITERIA_COUNT,
                        30,
                        0.01,
                    ),
                )

                if next_points is not None and status is not None:
                    backward_points, backward_status, _ = (
                        cv2.calcOpticalFlowPyrLK(
                            current_gray,
                            self.previous_gray,
                            next_points,
                            None,
                            winSize=(21, 21),
                            maxLevel=3,
                            criteria=(
                                cv2.TERM_CRITERIA_EPS |
                                cv2.TERM_CRITERIA_COUNT,
                                30,
                                0.01,
                            ),
                        )
                    )

                    if backward_points is not None:
                        good_old, good_new = self._valid_flow_points(
                            points,
                            next_points,
                            status,
                            error,
                            backward_points,
                            backward_status,
                        )

                        if good_new is not None:
                            movement = good_new - good_old
                            dx, dy = np.median(
                                movement,
                                axis=0,
                            )

                            moved_box = [
                                int(round(x + dx)),
                                int(round(y + dy)),
                                w,
                                h,
                            ]
                            student["box"] = self._clip_box(
                                moved_box,
                                frame_width,
                                frame_height,
                            )

                            # Retain only points that remain near the moved
                            # face region, rejecting points on the background.
                            bx, by, bw, bh = student["box"]
                            margin_x = max(4, int(bw * 0.15))
                            margin_y = max(4, int(bh * 0.15))

                            px = good_new[:, 0]
                            py = good_new[:, 1]
                            inside = (
                                (px >= bx - margin_x) &
                                (px <= bx + bw + margin_x) &
                                (py >= by - margin_y) &
                                (py <= by + bh + margin_y)
                            )
                            retained = good_new[inside]

                            if len(retained) >= 3:
                                new_student_points[student_id] = (
                                    retained.reshape(-1, 1, 2).astype(
                                        np.float32
                                    )
                                )

            if (
                student_id not in new_student_points
                or len(new_student_points[student_id]) < 5
            ):
                refreshed = self.detect_features(
                    current_gray,
                    student["box"],
                )
                if refreshed is not None and len(refreshed) >= 3:
                    new_student_points[student_id] = refreshed

            updated_tracks.append(student)

        self.previous_gray = current_gray
        self.student_points = new_student_points
        return updated_tracks
