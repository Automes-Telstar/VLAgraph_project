"""Extract human motion traces from a video for imitation-learning datasets.

This script is intentionally small and standalone. It reads a video, runs
MediaPipe Pose on sampled frames, and writes a JSON file containing landmarks,
basic joint angles, and simple motion labels.

Example:
    python scripts/extract_video_motion.py --video demo.mp4 --output uploads/motion_traces/demo.json --label walk_forward
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import statistics
from typing import Any


def _point(landmarks: dict[str, dict[str, float]], name: str) -> tuple[float, float, float] | None:
    value = landmarks.get(name)
    if not value:
        return None
    return (float(value["x"]), float(value["y"]), float(value["z"]))


def _distance(a: tuple[float, float, float] | None, b: tuple[float, float, float] | None) -> float | None:
    if a is None or b is None:
        return None
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _midpoint(
    a: tuple[float, float, float] | None,
    b: tuple[float, float, float] | None,
) -> tuple[float, float, float] | None:
    if a is None or b is None:
        return None
    return ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, (a[2] + b[2]) * 0.5)


def _angle_deg(
    a: tuple[float, float, float] | None,
    b: tuple[float, float, float] | None,
    c: tuple[float, float, float] | None,
) -> float | None:
    if a is None or b is None or c is None:
        return None

    ba = (a[0] - b[0], a[1] - b[1], a[2] - b[2])
    bc = (c[0] - b[0], c[1] - b[1], c[2] - b[2])
    dot = sum(ba[i] * bc[i] for i in range(3))
    mag_ba = math.sqrt(sum(item * item for item in ba))
    mag_bc = math.sqrt(sum(item * item for item in bc))
    if mag_ba == 0 or mag_bc == 0:
        return None

    cosine = max(-1.0, min(1.0, dot / (mag_ba * mag_bc)))
    return math.degrees(math.acos(cosine))


def _as_json_point(point: tuple[float, float, float] | None) -> list[float] | None:
    if point is None:
        return None
    return [round(point[0], 6), round(point[1], 6), round(point[2], 6)]


def _frame_features(landmarks: dict[str, dict[str, float]]) -> dict[str, Any]:
    left_shoulder = _point(landmarks, "LEFT_SHOULDER")
    right_shoulder = _point(landmarks, "RIGHT_SHOULDER")
    left_elbow = _point(landmarks, "LEFT_ELBOW")
    right_elbow = _point(landmarks, "RIGHT_ELBOW")
    left_wrist = _point(landmarks, "LEFT_WRIST")
    right_wrist = _point(landmarks, "RIGHT_WRIST")
    left_hip = _point(landmarks, "LEFT_HIP")
    right_hip = _point(landmarks, "RIGHT_HIP")
    left_knee = _point(landmarks, "LEFT_KNEE")
    right_knee = _point(landmarks, "RIGHT_KNEE")
    left_ankle = _point(landmarks, "LEFT_ANKLE")
    right_ankle = _point(landmarks, "RIGHT_ANKLE")

    hip_center = _midpoint(left_hip, right_hip)
    shoulder_center = _midpoint(left_shoulder, right_shoulder)

    angles = {
        "left_elbow": _angle_deg(left_shoulder, left_elbow, left_wrist),
        "right_elbow": _angle_deg(right_shoulder, right_elbow, right_wrist),
        "left_knee": _angle_deg(left_hip, left_knee, left_ankle),
        "right_knee": _angle_deg(right_hip, right_knee, right_ankle),
        "left_shoulder": _angle_deg(left_elbow, left_shoulder, left_hip),
        "right_shoulder": _angle_deg(right_elbow, right_shoulder, right_hip),
    }

    arm_state = {
        "left_arm_raised": bool(left_wrist and left_shoulder and left_wrist[1] < left_shoulder[1]),
        "right_arm_raised": bool(right_wrist and right_shoulder and right_wrist[1] < right_shoulder[1]),
    }

    return {
        "hip_center": _as_json_point(hip_center),
        "shoulder_center": _as_json_point(shoulder_center),
        "stance_width": _distance(left_ankle, right_ankle),
        "shoulder_width": _distance(left_shoulder, right_shoulder),
        "angles_deg": {
            key: None if value is None else round(value, 3)
            for key, value in angles.items()
        },
        "arm_state": arm_state,
    }


def _label_summary(frames: list[dict[str, Any]], requested_label: str) -> dict[str, Any]:
    if not frames:
        return {
            "requested_label": requested_label,
            "heuristic_labels": [],
            "confidence": 0.0,
        }

    hip_x_values = [
        frame["features"]["hip_center"][0]
        for frame in frames
        if frame["features"].get("hip_center")
    ]
    stance_values = [
        float(frame["features"]["stance_width"])
        for frame in frames
        if frame["features"].get("stance_width") is not None
    ]
    left_arm_raised = [
        bool(frame["features"]["arm_state"]["left_arm_raised"])
        for frame in frames
    ]
    right_arm_raised = [
        bool(frame["features"]["arm_state"]["right_arm_raised"])
        for frame in frames
    ]

    labels: list[str] = []
    confidence = 0.0

    if len(hip_x_values) >= 2:
        displacement = abs(hip_x_values[-1] - hip_x_values[0])
        if displacement > 0.06:
            labels.append("body_translation")
            confidence = max(confidence, min(1.0, displacement / 0.25))

    if stance_values and statistics.pstdev(stance_values) > 0.015:
        labels.append("leg_motion")
        confidence = max(confidence, min(1.0, statistics.pstdev(stance_values) / 0.08))

    if sum(left_arm_raised) / len(left_arm_raised) > 0.35:
        labels.append("left_arm_raised")
        confidence = max(confidence, 0.75)

    if sum(right_arm_raised) / len(right_arm_raised) > 0.35:
        labels.append("right_arm_raised")
        confidence = max(confidence, 0.75)

    if "body_translation" in labels and "leg_motion" in labels:
        labels.append("walk_like")
        confidence = max(confidence, 0.8)

    return {
        "requested_label": requested_label,
        "heuristic_labels": labels,
        "confidence": round(confidence, 3),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract human pose motion trace from a video.")
    parser.add_argument("--video", required=True, help="Input video path.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    parser.add_argument("--label", default="", help="Human-readable motion label, e.g. walk_forward.")
    parser.add_argument("--prompt", default="", help="Optional natural-language instruction for this demo.")
    parser.add_argument("--every-n-frames", type=int, default=2, help="Frame sampling stride.")
    parser.add_argument("--max-frames", type=int, default=0, help="Stop after this many sampled frames. 0 means no limit.")
    parser.add_argument("--min-visibility", type=float, default=0.35, help="Minimum landmark visibility to keep a frame.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        import cv2
        import mediapipe as mp
    except Exception as exc:
        raise SystemExit(
            "Missing motion extraction dependencies. Install them with:\n"
            "  python -m pip install -r scripts/requirements-motion.txt\n"
            f"Import error: {exc}"
        )

    video_path = pathlib.Path(args.video)
    output_path = pathlib.Path(args.output)
    if not video_path.exists():
        raise SystemExit(f"Video file not found: {video_path}")

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise SystemExit(f"Could not open video: {video_path}")

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    mp_pose = mp.solutions.pose
    sampled_frames: list[dict[str, Any]] = []
    frame_index = -1

    with mp_pose.Pose(
        static_image_mode=False,
        model_complexity=1,
        enable_segmentation=False,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as pose:
        while True:
            ok, frame = capture.read()
            if not ok:
                break

            frame_index += 1
            if frame_index % max(1, args.every_n_frames) != 0:
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = pose.process(rgb)
            if not result.pose_landmarks:
                continue

            landmarks: dict[str, dict[str, float]] = {}
            visible_count = 0
            for index, landmark in enumerate(result.pose_landmarks.landmark):
                name = mp_pose.PoseLandmark(index).name
                visibility = float(getattr(landmark, "visibility", 0.0))
                if visibility >= args.min_visibility:
                    visible_count += 1
                landmarks[name] = {
                    "x": round(float(landmark.x), 6),
                    "y": round(float(landmark.y), 6),
                    "z": round(float(landmark.z), 6),
                    "visibility": round(visibility, 6),
                }

            if visible_count < 12:
                continue

            timestamp_sec = frame_index / fps if fps > 0 else 0.0
            sampled_frames.append(
                {
                    "frame_index": frame_index,
                    "timestamp_sec": round(timestamp_sec, 6),
                    "visible_landmarks": visible_count,
                    "landmarks": landmarks,
                    "features": _frame_features(landmarks),
                }
            )

            if args.max_frames > 0 and len(sampled_frames) >= args.max_frames:
                break

    capture.release()

    output = {
        "type": "video_motion_trace",
        "source_video": str(video_path),
        "label": args.label,
        "prompt": args.prompt,
        "video": {
            "fps": fps,
            "frame_count": frame_count,
            "width": width,
            "height": height,
            "duration_sec": round(frame_count / fps, 6) if fps > 0 else None,
        },
        "sampling": {
            "every_n_frames": max(1, args.every_n_frames),
            "sampled_frames": len(sampled_frames),
            "min_visibility": args.min_visibility,
        },
        "summary": _label_summary(sampled_frames, args.label),
        "frames": sampled_frames,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(sampled_frames)} motion frames to {output_path}")
    print(json.dumps(output["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
