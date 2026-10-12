from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


Point = Tuple[float, float, float]


def _point(landmarks: Dict[str, Dict[str, float]], name: str) -> Optional[Point]:
    value = landmarks.get(name)
    if not value:
        return None
    return (float(value["x"]), float(value["y"]), float(value["z"]))


def _midpoint(a: Optional[Point], b: Optional[Point]) -> Optional[Point]:
    if a is None or b is None:
        return None
    return ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, (a[2] + b[2]) * 0.5)


def _distance(a: Optional[Point], b: Optional[Point]) -> Optional[float]:
    if a is None or b is None:
        return None
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _angle_deg(a: Optional[Point], b: Optional[Point], c: Optional[Point]) -> Optional[float]:
    if a is None or b is None or c is None:
        return None

    ba = (a[0] - b[0], a[1] - b[1], a[2] - b[2])
    bc = (c[0] - b[0], c[1] - b[1], c[2] - b[2])
    dot = sum(ba[index] * bc[index] for index in range(3))
    mag_ba = math.sqrt(sum(item * item for item in ba))
    mag_bc = math.sqrt(sum(item * item for item in bc))
    if mag_ba == 0 or mag_bc == 0:
        return None

    cosine = max(-1.0, min(1.0, dot / (mag_ba * mag_bc)))
    return math.degrees(math.acos(cosine))


def _json_point(point: Optional[Point]) -> Optional[List[float]]:
    if point is None:
        return None
    return [round(point[0], 6), round(point[1], 6), round(point[2], 6)]


def _landmarks_use_y_up(landmarks: Dict[str, Dict[str, float]]) -> bool:
    for landmark in landmarks.values():
        if not isinstance(landmark, dict):
            continue
        coordinate_frame = str(landmark.get("coordinate_frame", "")).lower()
        if "y_down" in coordinate_frame:
            return False
        if "y_up" in coordinate_frame:
            return True
        if "body_centered" in coordinate_frame:
            return True
    return False


def _is_arm_raised(wrist: Optional[Point], shoulder: Optional[Point], *, y_up: bool) -> bool:
    if wrist is None or shoulder is None:
        return False
    if y_up:
        return wrist[1] > shoulder[1]
    return wrist[1] < shoulder[1]


def frame_features(landmarks: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
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

    angles = {
        "left_elbow": _angle_deg(left_shoulder, left_elbow, left_wrist),
        "right_elbow": _angle_deg(right_shoulder, right_elbow, right_wrist),
        "left_knee": _angle_deg(left_hip, left_knee, left_ankle),
        "right_knee": _angle_deg(right_hip, right_knee, right_ankle),
        "left_shoulder": _angle_deg(left_elbow, left_shoulder, left_hip),
        "right_shoulder": _angle_deg(right_elbow, right_shoulder, right_hip),
    }
    y_up = _landmarks_use_y_up(landmarks)

    return {
        "hip_center": _json_point(_midpoint(left_hip, right_hip)),
        "shoulder_center": _json_point(_midpoint(left_shoulder, right_shoulder)),
        "stance_width": _distance(left_ankle, right_ankle),
        "shoulder_width": _distance(left_shoulder, right_shoulder),
        "angles_deg": {
            key: None if value is None else round(value, 3)
            for key, value in angles.items()
        },
        "arm_state": {
            "left_arm_raised": _is_arm_raised(left_wrist, left_shoulder, y_up=y_up),
            "right_arm_raised": _is_arm_raised(right_wrist, right_shoulder, y_up=y_up),
        },
    }


def summarize_motion(frames: List[Dict[str, Any]], requested_label: str) -> Dict[str, Any]:
    if not frames:
        return {
            "requested_label": requested_label,
            "heuristic_labels": [],
            "primary_skill": requested_label or "unknown",
            "confidence": 0.0,
        }

    hip_x_values = [
        frame["features"]["hip_center"][0]
        for frame in frames
        if frame.get("features", {}).get("hip_center")
    ]
    stance_values = [
        float(frame["features"]["stance_width"])
        for frame in frames
        if frame.get("features", {}).get("stance_width") is not None
    ]
    left_arm_raised = [
        bool(frame["features"]["arm_state"]["left_arm_raised"])
        for frame in frames
    ]
    right_arm_raised = [
        bool(frame["features"]["arm_state"]["right_arm_raised"])
        for frame in frames
    ]

    labels: List[str] = []
    confidence = 0.0

    if len(hip_x_values) >= 2:
        displacement = abs(hip_x_values[-1] - hip_x_values[0])
        if displacement > 0.06:
            labels.append("body_translation")
            confidence = max(confidence, min(1.0, displacement / 0.25))

    if stance_values and statistics.pstdev(stance_values) > 0.015:
        labels.append("leg_motion")
        confidence = max(confidence, min(1.0, statistics.pstdev(stance_values) / 0.08))

    if left_arm_raised and sum(left_arm_raised) / len(left_arm_raised) > 0.35:
        labels.append("left_arm_raised")
        confidence = max(confidence, 0.75)

    if right_arm_raised and sum(right_arm_raised) / len(right_arm_raised) > 0.35:
        labels.append("right_arm_raised")
        confidence = max(confidence, 0.75)

    if "body_translation" in labels and "leg_motion" in labels:
        labels.append("walk_like")
        confidence = max(confidence, 0.8)

    if requested_label:
        primary_skill = requested_label
    elif "walk_like" in labels:
        primary_skill = "walk_like"
    elif labels:
        primary_skill = labels[-1]
    else:
        primary_skill = "unknown"

    humanoid_meanings = {
        "body_translation": ("전신 이동", "골반 중심이 이동해 휴머노이드의 루트 위치 제어가 필요합니다."),
        "leg_motion": ("다리 동작", "보폭이 변해 고관절·무릎·발목의 협응과 균형 제어가 필요합니다."),
        "left_arm_raised": ("왼팔 들기", "왼팔 관절 궤적을 따라 상체 자세를 제어하는 동작입니다."),
        "right_arm_raised": ("오른팔 들기", "오른팔 관절 궤적을 따라 상체 자세를 제어하는 동작입니다."),
        "walk_like": ("보행 유사 동작", "루트 이동과 양다리 협응을 함께 학습하는 휴머노이드 보행 동작입니다."),
    }
    meaning_items = [
        {"code": item, "name_ko": humanoid_meanings[item][0], "meaning_ko": humanoid_meanings[item][1]}
        for item in labels
        if item in humanoid_meanings
    ]
    if not meaning_items:
        meaning_items.append(
            {
                "code": "pose_sequence",
                "name_ko": "전신 자세 변화",
                "meaning_ko": "관측된 관절 자세의 시간 변화를 휴머노이드 관절 제어 궤적으로 학습합니다.",
            }
        )

    return {
        "requested_label": requested_label,
        "heuristic_labels": labels,
        "primary_skill": primary_skill,
        "confidence": round(confidence, 3),
        "embodiment": "humanoid",
        "meaning_ko": meaning_items,
        "learning_goal_ko": "사람의 전신 자세를 휴머노이드의 균형 잡힌 관절 및 루트 동작으로 재현",
    }


def save_humanoid_training_dataset(trace: Dict[str, Any], output_path: str) -> Dict[str, Any]:
    """Save frame-to-next-frame examples suitable for humanoid imitation learning."""
    frames = trace.get("frames") if isinstance(trace.get("frames"), list) else []
    dataset_path = Path(output_path)
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    summary = trace.get("summary") if isinstance(trace.get("summary"), dict) else {}
    written = 0

    with dataset_path.open("w", encoding="utf-8", newline="\n") as dataset_file:
        for index in range(max(0, len(frames) - 1)):
            current = frames[index] if isinstance(frames[index], dict) else {}
            following = frames[index + 1] if isinstance(frames[index + 1], dict) else {}
            observation_landmarks = current.get("retarget_landmarks") or current.get("landmarks") or {}
            target_landmarks = following.get("retarget_landmarks") or following.get("landmarks") or {}
            if not observation_landmarks or not target_landmarks:
                continue
            sample = {
                "schema": "vlagraph.humanoid_imitation.v1",
                "embodiment": "humanoid",
                "task": summary.get("primary_skill", "unknown"),
                "instruction": trace.get("prompt") or trace.get("label") or summary.get("primary_skill", ""),
                "observation": {
                    "timestamp_sec": current.get("timestamp_sec", 0.0),
                    "landmarks": observation_landmarks,
                    "features": current.get("retarget_features") or current.get("features") or {},
                },
                "action": {
                    "timestamp_sec": following.get("timestamp_sec", 0.0),
                    "target_landmarks": target_landmarks,
                    "target_features": following.get("retarget_features") or following.get("features") or {},
                },
                "meaning": summary.get("meaning_ko", []),
            }
            dataset_file.write(json.dumps(sample, ensure_ascii=False, separators=(",", ":")) + "\n")
            written += 1

    return {
        "path": str(dataset_path),
        "format": "jsonl",
        "schema": "vlagraph.humanoid_imitation.v1",
        "embodiment": "humanoid",
        "samples": written,
        "trainable": written > 0,
    }


def extract_video_motion(
    *,
    video_path: str,
    output_path: str,
    label: str = "",
    prompt: str = "",
    every_n_frames: int = 2,
    max_frames: int = 0,
    min_visibility: float = 0.35,
) -> Dict[str, Any]:
    try:
        import cv2
        import mediapipe as mp
    except Exception as exc:
        raise RuntimeError(
            "Motion extraction requires mediapipe and opencv. "
            "Install backend dependencies or rebuild the backend image. "
            f"Import error: {exc}"
        ) from exc

    video_file = Path(video_path)
    if not video_file.exists():
        raise FileNotFoundError(f"Video file not found: {video_file}")

    capture = cv2.VideoCapture(str(video_file))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {video_file}")

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    every_n_frames = max(1, int(every_n_frames or 1))

    frames: List[Dict[str, Any]] = []
    frame_index = -1
    mp_pose = mp.solutions.pose

    def serialize_pose_landmarks(raw_landmarks: Any, *, coordinate_frame: str) -> Tuple[Dict[str, Dict[str, float]], int]:
        serialized: Dict[str, Dict[str, float]] = {}
        visible = 0
        for index, landmark in enumerate(raw_landmarks.landmark):
            name = mp_pose.PoseLandmark(index).name
            visibility = float(getattr(landmark, "visibility", 1.0))
            if visibility >= min_visibility:
                visible += 1
            y_value = float(landmark.y)
            z_value = float(landmark.z)
            # MediaPipe Pose world output uses image-style +Y downward.
            # Flip Y and Z together so the canonical Y-up frame remains
            # right-handed and preserves rotation signs.
            if "world_landmarks" in coordinate_frame and "y_up" in coordinate_frame:
                y_value = -y_value
                z_value = -z_value
            serialized[name] = {
                "x": round(float(landmark.x), 6),
                "y": round(y_value, 6),
                "z": round(z_value, 6),
                "visibility": round(visibility, 6),
                "coordinate_frame": coordinate_frame,
            }
        return serialized, visible

    try:
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
                if frame_index % every_n_frames != 0:
                    continue

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                result = pose.process(rgb)
                if not result.pose_landmarks:
                    continue

                landmarks, visible_count = serialize_pose_landmarks(
                    result.pose_landmarks,
                    coordinate_frame="mediapipe_image_normalized_y_down",
                )
                world_landmarks: Dict[str, Dict[str, float]] = {}
                world_visible_count = 0
                if result.pose_world_landmarks:
                    world_landmarks, world_visible_count = serialize_pose_landmarks(
                        result.pose_world_landmarks,
                        coordinate_frame="mediapipe_world_landmarks_body_centered_y_up",
                    )

                if visible_count < 12:
                    continue

                timestamp_sec = frame_index / fps if fps > 0 else 0.0
                frame_payload: Dict[str, Any] = {
                    "frame_index": frame_index,
                    "timestamp_sec": round(timestamp_sec, 6),
                    "visible_landmarks": visible_count,
                    "landmarks": landmarks,
                    "features": frame_features(landmarks),
                }
                if world_landmarks and world_visible_count >= 12:
                    frame_payload["world_landmarks"] = world_landmarks
                    frame_payload["retarget_landmarks"] = world_landmarks
                    frame_payload["world_visible_landmarks"] = world_visible_count
                    frame_payload["retarget_landmark_source"] = "mediapipe_pose_world_landmarks"
                    frame_payload["world_features"] = frame_features(world_landmarks)
                    frame_payload["retarget_features"] = frame_payload["world_features"]
                else:
                    frame_payload["retarget_landmark_source"] = "mediapipe_pose_landmarks"

                frames.append(frame_payload)

                if max_frames > 0 and len(frames) >= max_frames:
                    break
    finally:
        capture.release()

    output = {
        "type": "video_motion_trace",
        "source_video": str(video_file),
        "label": label,
        "prompt": prompt,
        "video": {
            "fps": fps,
            "frame_count": frame_count,
            "width": width,
            "height": height,
            "duration_sec": round(frame_count / fps, 6) if fps > 0 else None,
        },
        "sampling": {
            "every_n_frames": every_n_frames,
            "sampled_frames": len(frames),
            "min_visibility": min_visibility,
        },
        "summary": summarize_motion(frames, label),
        "frames": frames,
    }

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    return output
