from __future__ import annotations

import copy
import json
import math
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import unquote, urlsplit

from backend.config import UPLOAD_DIR
from backend.executors.g1_action_schema import (
    G1_JOINT_GROUPS,
    G1_WAIST_3DOF_JOINTS,
    G1_GROUP_ORDER,
    g1_full_joint_order,
    g1_schema_payload,
)
from backend.executors.mediapipe_g1_mapping import landmarks_to_g1_named_targets
from backend.motion.extractor import extract_video_motion, save_humanoid_training_dataset

_RETARGET_SMOOTHING_BY_NODE: Dict[str, Dict[str, float]] = {}
_RETARGET_DIAGNOSTIC_LAST_LOG_AT: Dict[str, float] = {}

DEFAULT_VLAGRAPH_HOST_ROOT = r"C:\Users\0\Desktop\vlagraph"
DEFAULT_ISAACLAB_BRIDGE_ROOT = r"C:\vlagraph_isaaclab_bridge"


def reset_motion_retarget_runtime_state(node_ids: List[str] | None = None) -> None:
    if node_ids is None:
        _RETARGET_SMOOTHING_BY_NODE.clear()
        return

    for node_id in node_ids:
        _RETARGET_SMOOTHING_BY_NODE.pop(str(node_id), None)


def _incoming_values(
    node_id: str,
    edges: List[Dict[str, Any]],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for edge in edges:
        if edge.get("target") != node_id:
            continue

        source_id = edge.get("source")
        source_handle = edge.get("sourceHandle")
        target_handle = edge.get("targetHandle")
        source_payload = context.get(source_id)
        if source_payload is None:
            continue

        value = source_payload
        if source_handle:
            if not isinstance(source_payload, dict) or source_handle not in source_payload:
                continue
            value = source_payload[source_handle]

        key = target_handle or source_handle or source_id
        result[str(key)] = value
    return result


def _text(value: Any) -> str:
    return str(value or "").strip()


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


def _video_path_from_value(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("video_path", "video", "file_path", "path", "url"):
            candidate = _text(value.get(key))
            if candidate:
                return _resolve_video_path(candidate)
        return ""

    return _resolve_video_path(_text(value))


def _resolve_video_path(value: str) -> str:
    if not value:
        return ""

    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https"} and parsed.path.startswith("/uploads/"):
        return str(Path(UPLOAD_DIR) / Path(unquote(parsed.path)).name)

    if value.startswith("/uploads/") or value.startswith("\\uploads\\"):
        return str(Path(UPLOAD_DIR) / Path(value.replace("\\", "/")).name)

    normalized = value.replace("\\", os.sep)
    path = Path(normalized)
    if path.is_absolute():
        return str(path)

    upload_candidate = Path(UPLOAD_DIR) / path.name
    if upload_candidate.exists():
        return str(upload_candidate)

    return str(path)


def _trace_path_for_video(video_path: str, output_name: str = "") -> str:
    trace_dir = Path(UPLOAD_DIR) / "motion_traces"
    safe_name = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_"
        for char in _text(output_name)
    ).strip("_")
    if not safe_name:
        safe_name = f"{Path(video_path).stem or 'motion'}-{uuid.uuid4().hex[:8]}"
    if not safe_name.lower().endswith(".json"):
        safe_name = f"{safe_name}.json"
    return str(trace_dir / safe_name)


def _host_trace_path(trace_path: str) -> str:
    """Best-effort Windows host path for Docker-mounted upload traces."""
    path = Path(trace_path)
    host_root = _text(os.getenv("VLAGRAPH_HOST_ROOT")) or DEFAULT_VLAGRAPH_HOST_ROOT
    filename = path.name
    if not filename:
        return trace_path

    normalized = str(trace_path).replace("\\", "/")
    upload_dir = str(UPLOAD_DIR).replace("\\", "/").rstrip("/")
    if normalized.startswith("/tmp/openvla_uploads/") or (
        upload_dir and normalized.startswith(f"{upload_dir}/")
    ):
        return str(Path(host_root) / "uploads" / "motion_traces" / filename)

    if path.is_absolute():
        return str(path)

    return str(Path(host_root) / "uploads" / "motion_traces" / filename)


def _isaaclab_bridge_commands(trace_path: str, *, task: str = "Isaac-Cartpole-Direct-v0") -> Dict[str, Any]:
    bridge_root = _text(os.getenv("VLAGRAPH_ISAACLAB_BRIDGE_ROOT")) or DEFAULT_ISAACLAB_BRIDGE_ROOT
    host_trace = _host_trace_path(trace_path)
    task = _text(task) or "Isaac-Cartpole-Direct-v0"
    powershell = (
        f'powershell -ExecutionPolicy Bypass -File "{bridge_root}\\scripts\\train_isaaclab.ps1" '
        f'-Trace "{host_trace}" -Task {task} -NumEnvs 1 -MaxIterations 200'
    )
    cmd = (
        f'cd /d "{bridge_root}" && '
        f'powershell -ExecutionPolicy Bypass -File .\\scripts\\train_isaaclab.ps1 '
        f'-Trace "{host_trace}" -Task {task} -NumEnvs 1 -MaxIterations 200'
    )
    return {
        "bridge_root": bridge_root,
        "trace_path": trace_path,
        "trace_path_host": host_trace,
        "task": task,
        "powershell": powershell,
        "cmd": cmd,
    }


def _compact_motion(trace: Dict[str, Any], trace_path: str) -> Dict[str, Any]:
    return {
        "type": trace.get("type", "video_motion_trace"),
        "trace_path": trace_path,
        "source_video": trace.get("source_video"),
        "label": trace.get("label", ""),
        "prompt": trace.get("prompt", ""),
        "video": trace.get("video", {}),
        "sampling": trace.get("sampling", {}),
        "summary": trace.get("summary", {}),
    }


POSE_PREVIEW_LANDMARKS = {
    "NOSE",
    "LEFT_SHOULDER",
    "RIGHT_SHOULDER",
    "LEFT_ELBOW",
    "RIGHT_ELBOW",
    "LEFT_WRIST",
    "RIGHT_WRIST",
    "LEFT_HIP",
    "RIGHT_HIP",
    "LEFT_KNEE",
    "RIGHT_KNEE",
    "LEFT_ANKLE",
    "RIGHT_ANKLE",
}


def _pose_preview_from_trace(
    trace: Dict[str, Any],
    *,
    max_preview_frames: int = 120,
) -> Dict[str, Any]:
    frames = trace.get("frames") if isinstance(trace.get("frames"), list) else []
    if not frames:
        return {"frames": [], "landmarks": sorted(POSE_PREVIEW_LANDMARKS)}

    max_preview_frames = max(1, int(max_preview_frames or 1))
    stride = max(1, len(frames) // max_preview_frames)
    sampled = frames[::stride][:max_preview_frames]
    preview_frames: List[Dict[str, Any]] = []

    for frame in sampled:
        if not isinstance(frame, dict):
            continue
        landmarks = frame.get("landmarks") if isinstance(frame.get("landmarks"), dict) else {}
        compact_landmarks: Dict[str, Dict[str, float]] = {}
        for name in POSE_PREVIEW_LANDMARKS:
            landmark = landmarks.get(name)
            if not isinstance(landmark, dict):
                continue
            try:
                compact_landmarks[name] = {
                    "x": round(float(landmark.get("x", 0.0)), 5),
                    "y": round(float(landmark.get("y", 0.0)), 5),
                    "visibility": round(float(landmark.get("visibility", 1.0)), 4),
                }
            except Exception:
                continue

        if compact_landmarks:
            preview_frames.append(
                {
                    "frame_index": frame.get("frame_index"),
                    "timestamp_sec": frame.get("timestamp_sec", 0.0),
                    "landmarks": compact_landmarks,
                }
            )

    return {
        "type": "mediapipe_pose_preview",
        "landmarks": sorted(POSE_PREVIEW_LANDMARKS),
        "frames": preview_frames,
        "video": trace.get("video", {}),
    }


def _lower_words(*values: Any) -> str:
    return " ".join(_text(value).lower() for value in values if _text(value))


def _skill_from_motion(value: Any) -> str:
    if isinstance(value, dict):
        summary = value.get("summary")
        if isinstance(summary, dict):
            primary = _text(summary.get("primary_skill"))
            if primary:
                return primary
            labels = summary.get("heuristic_labels")
            if isinstance(labels, list) and labels:
                return _text(labels[-1])
        return _text(value.get("skill") or value.get("label") or value.get("motionLabel"))
    return _text(value)


def _summary_from_motion(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict) and isinstance(value.get("summary"), dict):
        return value["summary"]
    return {}


def _motion_duration_sec(value: Any) -> float:
    trace = _load_motion_trace(value)
    if not isinstance(trace, dict):
        return 0.0

    video = trace.get("video")
    if isinstance(video, dict):
        for key in ("duration_sec", "durationSec", "duration"):
            try:
                duration = float(video.get(key))
            except Exception:
                continue
            if math.isfinite(duration) and duration > 0.0:
                return duration

    frames = trace.get("frames")
    if isinstance(frames, list) and len(frames) >= 2:
        times: List[float] = []
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            try:
                timestamp = float(frame.get("timestamp_sec", frame.get("timestamp")))
            except Exception:
                continue
            if math.isfinite(timestamp):
                times.append(timestamp)
        if len(times) >= 2:
            return max(0.0, max(times) - min(times))

    return 0.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _load_motion_trace(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    if isinstance(value.get("frames"), list):
        return value

    for nested_key in ("motion", "trace", "motion_trace", "motionTrace"):
        nested = value.get(nested_key)
        if isinstance(nested, dict) and isinstance(nested.get("frames"), list):
            return nested

    live_landmarks = None
    if isinstance(value.get("retarget_landmarks"), dict):
        live_landmarks = value.get("retarget_landmarks")
    elif isinstance(value.get("landmarks"), dict):
        live_landmarks = value.get("landmarks")
    elif isinstance(value.get("pose3d"), dict):
        pose3d = value.get("pose3d") or {}
        if isinstance(pose3d.get("retarget_landmarks"), dict):
            live_landmarks = pose3d.get("retarget_landmarks")
        elif isinstance(pose3d.get("landmarks"), dict):
            live_landmarks = pose3d.get("landmarks")
    elif isinstance(value.get("skeleton"), dict):
        skeleton = value.get("skeleton") or {}
        if isinstance(skeleton.get("retarget_landmarks"), dict):
            live_landmarks = skeleton.get("retarget_landmarks")
        elif isinstance(skeleton.get("landmarks"), dict):
            live_landmarks = skeleton.get("landmarks")

    if isinstance(live_landmarks, dict) and live_landmarks:
        return {
            "type": value.get("type", "live_pose_motion_trace"),
            "source": value.get("source", "live_pose_payload"),
            "label": value.get("label") or value.get("motionLabel") or "",
            "prompt": value.get("prompt") or "",
            "summary": value.get("summary") if isinstance(value.get("summary"), dict) else {},
            "frames": [
                {
                    "frame_index": value.get("frame_index", 0),
                    "timestamp_sec": value.get("timestamp_sec", value.get("timestamp", 0.0)),
                    "visible_landmarks": len(live_landmarks),
                    "landmarks": live_landmarks,
                    "features": value.get("features") if isinstance(value.get("features"), dict) else {},
                }
            ],
        }

    trace_path = _text(value.get("trace_path") or value.get("tracePath") or value.get("dataset"))
    if not trace_path:
        return value

    raw_path = Path(trace_path)
    candidates = [raw_path]
    if not raw_path.is_absolute():
        candidates.append(Path.cwd() / raw_path)
        candidates.append(Path(UPLOAD_DIR) / raw_path.name)

    path = next((candidate for candidate in candidates if candidate.exists()), None)
    if path is None:
        return value

    try:
        loaded = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(loaded, dict):
            loaded.setdefault("trace_path", str(path))
            return loaded
    except Exception:
        return value

    return value


def _motion_source_text(value: Any) -> str:
    trace = _load_motion_trace(value)
    if not isinstance(trace, dict):
        return ""

    parts: List[str] = []
    for key in (
        "type",
        "source",
        "label",
        "motionLabel",
        "prompt",
        "pipeline",
        "producer",
    ):
        item = trace.get(key)
        if isinstance(item, str) and item:
            parts.append(item)

    summary = trace.get("summary")
    if isinstance(summary, dict):
        for key in ("primary_skill", "label", "source"):
            item = summary.get(key)
            if isinstance(item, str) and item:
                parts.append(item)
        labels = summary.get("heuristic_labels")
        if isinstance(labels, list):
            parts.extend(str(item) for item in labels if item)

    return " ".join(parts).strip().lower().replace("-", "_")


def _looks_like_live_mocap_motion(value: Any) -> bool:
    source_text = _motion_source_text(value)
    if not source_text:
        return False
    return any(
        marker in source_text
        for marker in (
            "rgbd_pose_motion_trace",
            "rgbd_pose_fusion",
            "rgbd",
            "rgb_d",
            "realsense",
            "d435i",
            "mediapipe",
            "live_pose",
            "pose3d",
        )
    )


def _angle_flexion(angles: Dict[str, Any], key: str, *, scale: float, maximum: float) -> float:
    try:
        angle = float(angles.get(key))
    except Exception:
        return 0.0
    return round(_clamp((180.0 - angle) * scale, 0.0, maximum), 3)


def _landmark_axis_delta(
    landmarks: Dict[str, Any],
    left_name: str,
    right_name: str,
    axis: str,
) -> float:
    try:
        left = landmarks.get(left_name) or {}
        right = landmarks.get(right_name) or {}
        return float(left.get(axis, 0.0)) - float(right.get(axis, 0.0))
    except Exception:
        return 0.0


def _point3(landmarks: Dict[str, Any], name: str) -> tuple[float, float, float] | None:
    value = landmarks.get(name)
    if not isinstance(value, dict):
        return None
    try:
        point = (float(value["x"]), float(value["y"]), float(value["z"]))
    except Exception:
        return None
    if not all(math.isfinite(item) for item in point):
        return None
    return point


def _landmark_confidence(landmarks: Dict[str, Any], name: str) -> float:
    value = landmarks.get(name)
    if not isinstance(value, dict):
        return 0.0
    for key in ("visibility", "presence", "confidence", "score"):
        if key not in value:
            continue
        try:
            confidence = float(value.get(key))
        except Exception:
            continue
        if math.isfinite(confidence):
            return _clamp(confidence, 0.0, 1.0)
    return 1.0


def _distance3(a: tuple[float, float, float] | None, b: tuple[float, float, float] | None) -> float:
    if a is None or b is None:
        return 0.0
    return math.sqrt(sum((a[index] - b[index]) ** 2 for index in range(3)))


def _safe_scale(value: float, scale: float) -> float:
    return value / max(scale, 1e-6)


def _landmarks_use_y_up(landmarks: Dict[str, Any]) -> bool:
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


def _vertical_raise_amount(
    landmarks: Dict[str, Any],
    shoulder_name: str,
    elbow_name: str,
    wrist_name: str,
    *,
    body_scale: float,
) -> float:
    shoulder = _point3(landmarks, shoulder_name)
    elbow = _point3(landmarks, elbow_name)
    wrist = _point3(landmarks, wrist_name)
    if shoulder is None:
        return 0.0
    reference = wrist or elbow
    if reference is None:
        return 0.0
    if _landmarks_use_y_up(landmarks):
        vertical_delta = reference[1] - shoulder[1]
    else:
        vertical_delta = shoulder[1] - reference[1]
    return _clamp(_safe_scale(vertical_delta, body_scale * 1.25), 0.0, 1.0)


def _side_amount(
    landmarks: Dict[str, Any],
    shoulder_name: str,
    elbow_name: str,
    *,
    body_scale: float,
) -> float:
    shoulder = _point3(landmarks, shoulder_name)
    elbow = _point3(landmarks, elbow_name)
    if shoulder is None or elbow is None:
        return 0.0
    return _clamp(_safe_scale(elbow[0] - shoulder[0], body_scale), -1.0, 1.0)


def _depth_amount(
    landmarks: Dict[str, Any],
    shoulder_name: str,
    elbow_name: str,
    wrist_name: str,
    *,
    body_scale: float,
) -> float:
    shoulder = _point3(landmarks, shoulder_name)
    reference = _point3(landmarks, wrist_name) or _point3(landmarks, elbow_name)
    if shoulder is None or reference is None:
        return 0.0
    return _clamp(_safe_scale(reference[2] - shoulder[2], body_scale), -1.0, 1.0)


def _leg_swing_amount(
    landmarks: Dict[str, Any],
    hip_name: str,
    ankle_name: str,
    *,
    body_scale: float,
) -> float:
    hip = _point3(landmarks, hip_name)
    ankle = _point3(landmarks, ankle_name)
    if hip is None or ankle is None:
        return 0.0
    # Smaller depth than the hip means the foot is toward the camera.
    return _clamp(_safe_scale(hip[2] - ankle[2], body_scale), -1.0, 1.0)


def _landmark_visibility(landmarks: Dict[str, Any], name: str, default: float = 1.0) -> float:
    value = landmarks.get(name)
    if not isinstance(value, dict):
        return 0.0
    return _clamp(_to_float(value.get("visibility"), default), 0.0, 1.0)


def _chain_visibility(
    landmarks: Dict[str, Any],
    names: tuple[str, ...],
    *,
    default: float = 1.0,
) -> float:
    values = [_landmark_visibility(landmarks, name, default=default) for name in names]
    return min(values) if values else 0.0


def _arm_activity_amount(
    *,
    raise_amount: float,
    side_deg: float,
    depth_deg: float,
    elbow_deg: float,
) -> float:
    return max(
        abs(float(raise_amount)),
        abs(float(side_deg)) / 45.0,
        abs(float(depth_deg)) / 45.0,
        abs(float(elbow_deg)) / 90.0,
    )


def _lower_body_should_lock(
    landmarks: Dict[str, Any],
    *,
    mode: str,
    min_visibility: float,
) -> bool:
    normalized = _text(mode).lower()
    if normalized in {"lock", "locked", "upper", "upper_body", "upper-only", "upper_only", "seated"}:
        return True
    if normalized in {"free", "full", "full_body", "off", "none"}:
        return False

    left_leg_vis = _chain_visibility(landmarks, ("LEFT_HIP", "LEFT_KNEE", "LEFT_ANKLE"))
    right_leg_vis = _chain_visibility(landmarks, ("RIGHT_HIP", "RIGHT_KNEE", "RIGHT_ANKLE"))
    if min(left_leg_vis, right_leg_vis) < min_visibility:
        return True

    left_hip = _point3(landmarks, "LEFT_HIP")
    right_hip = _point3(landmarks, "RIGHT_HIP")
    left_knee = _point3(landmarks, "LEFT_KNEE")
    right_knee = _point3(landmarks, "RIGHT_KNEE")
    left_ankle = _point3(landmarks, "LEFT_ANKLE")
    right_ankle = _point3(landmarks, "RIGHT_ANKLE")
    hip_center = _midpoint3(left_hip, right_hip)
    knee_center = _midpoint3(left_knee, right_knee)
    ankle_center = _midpoint3(left_ankle, right_ankle)
    if hip_center is None or knee_center is None or ankle_center is None:
        return True

    # A seated/desk-occluded RGB-D pose often has knees/ankles compressed near the hips.
    leg_span = abs(float(hip_center[1]) - float(ankle_center[1]))
    knee_span = abs(float(hip_center[1]) - float(knee_center[1]))
    hip_width = _distance3(left_hip, right_hip) or 0.35
    return leg_span < hip_width * 1.15 or knee_span < hip_width * 0.45


def _midpoint3(
    a: tuple[float, float, float] | None,
    b: tuple[float, float, float] | None,
) -> tuple[float, float, float] | None:
    if a is None or b is None:
        return None
    return ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, (a[2] + b[2]) * 0.5)


def _vec3(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> tuple[float, float, float]:
    return (b[0] - a[0], b[1] - a[1], b[2] - a[2])


def _len3(v: tuple[float, float, float] | None) -> float:
    if v is None:
        return 0.0
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _dot3(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross3(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _scale3(v: tuple[float, float, float], scale: float) -> tuple[float, float, float]:
    return (v[0] * scale, v[1] * scale, v[2] * scale)


def _normalize3(v: tuple[float, float, float] | None) -> tuple[float, float, float]:
    length = _len3(v)
    if v is None or length <= 1.0e-8:
        return (0.0, 0.0, 0.0)
    return (v[0] / length, v[1] / length, v[2] / length)


def _body_vector(
    value: tuple[float, float, float],
    axes: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
) -> tuple[float, float, float]:
    right_axis, up_axis, forward_axis = axes
    vec = _normalize3(value)
    return (_dot3(vec, right_axis), _dot3(vec, up_axis), _dot3(vec, forward_axis))


def _signed_angle3(
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    axis: tuple[float, float, float],
) -> float:
    start = _normalize3(start)
    end = _normalize3(end)
    cross = _cross3(start, end)
    return math.atan2(_dot3(cross, axis), _clamp(_dot3(start, end), -1.0, 1.0))


def _g1_body_axes_from_landmarks(
    landmarks: Dict[str, Any],
) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]] | None:
    left_shoulder = _point3(landmarks, "LEFT_SHOULDER")
    right_shoulder = _point3(landmarks, "RIGHT_SHOULDER")
    left_hip = _point3(landmarks, "LEFT_HIP")
    right_hip = _point3(landmarks, "RIGHT_HIP")

    if left_shoulder is not None and right_shoulder is not None:
        right_axis = _normalize3(_vec3(left_shoulder, right_shoulder))
    elif left_hip is not None and right_hip is not None:
        right_axis = _normalize3(_vec3(left_hip, right_hip))
    else:
        return None

    if left_shoulder is not None and right_shoulder is not None and left_hip is not None and right_hip is not None:
        shoulder_center = _midpoint3(left_shoulder, right_shoulder)
        hip_center = _midpoint3(left_hip, right_hip)
        up_axis = _normalize3(_vec3(hip_center, shoulder_center)) if shoulder_center and hip_center else (0.0, 1.0, 0.0)
    else:
        up_axis = (0.0, 1.0, 0.0)

    forward_axis = _normalize3(_cross3(right_axis, up_axis))
    if _len3(forward_axis) <= 1.0e-6:
        forward_axis = (0.0, 0.0, 1.0)
    # RGB-D fusion now sends body-centered coordinates with +Z as person-forward.
    forward_sign = _to_float(os.getenv("RGBD_RETARGET_FORWARD_SIGN"), 1.0)
    if forward_sign < 0.0:
        forward_axis = _scale3(forward_axis, -1.0)
    up_axis = _normalize3(_cross3(forward_axis, right_axis))
    return right_axis, up_axis, forward_axis


def _g1_pelvis_axes_from_landmarks(
    landmarks: Dict[str, Any],
) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]] | None:
    """Build a lower-body frame that does not rotate with the shoulders."""
    left_hip = _point3(landmarks, "LEFT_HIP")
    right_hip = _point3(landmarks, "RIGHT_HIP")
    if left_hip is None or right_hip is None:
        return None
    right_axis = _normalize3(_vec3(left_hip, right_hip))
    if _len3(right_axis) <= 1.0e-6:
        return None
    shoulder_center = _midpoint3(
        _point3(landmarks, "LEFT_SHOULDER"),
        _point3(landmarks, "RIGHT_SHOULDER"),
    )
    hip_center = _midpoint3(left_hip, right_hip)
    up_sign = (
        -1.0
        if shoulder_center is not None and hip_center is not None and shoulder_center[1] < hip_center[1]
        else 1.0
    )
    world_up = (0.0, up_sign, 0.0)
    up_axis = _normalize3(
        _sub3(world_up, _scale3(right_axis, _dot3(world_up, right_axis)))
    )
    forward_axis = _normalize3(_cross3(right_axis, up_axis))
    if _len3(up_axis) <= 1.0e-6 or _len3(forward_axis) <= 1.0e-6:
        return None
    if _to_float(os.getenv("RGBD_RETARGET_FORWARD_SIGN"), 1.0) < 0.0:
        forward_axis = _scale3(forward_axis, -1.0)
    up_axis = _normalize3(_cross3(forward_axis, right_axis))
    return right_axis, up_axis, forward_axis


def _angle3_deg(
    a: tuple[float, float, float] | None,
    b: tuple[float, float, float] | None,
    c: tuple[float, float, float] | None,
) -> float | None:
    if a is None or b is None or c is None:
        return None
    ba = _vec3(b, a)
    bc = _vec3(b, c)
    mag_ba = _len3(ba)
    mag_bc = _len3(bc)
    if mag_ba <= 1.0e-6 or mag_bc <= 1.0e-6:
        return None
    dot = ba[0] * bc[0] + ba[1] * bc[1] + ba[2] * bc[2]
    cosine = _clamp(dot / (mag_ba * mag_bc), -1.0, 1.0)
    return math.degrees(math.acos(cosine))


def _flexion_rad(
    a: tuple[float, float, float] | None,
    b: tuple[float, float, float] | None,
    c: tuple[float, float, float] | None,
) -> float:
    angle = _angle3_deg(a, b, c)
    if angle is None:
        return 0.0
    return math.radians(_clamp(180.0 - angle, 0.0, 180.0))


G1_SHOULDER_PITCH_MIN_RAD = -2.35
G1_SHOULDER_PITCH_MAX_RAD = 1.25
G1_SHOULDER_YAW_MIN_RAD = -2.45
G1_SHOULDER_YAW_MAX_RAD = 2.45
G1_LEFT_SHOULDER_ROLL_LIMITS_RAD = (-1.55, 2.20)
G1_RIGHT_SHOULDER_ROLL_LIMITS_RAD = (-2.20, 1.55)
G1_ELBOW_PITCH_LIMITS_RAD = (0.0, 1.8)
G1_ELBOW_ROLL_LIMITS_RAD = (-0.9, 0.9)
G1_HIP_PITCH_MIN_RAD = -1.25
G1_HIP_PITCH_MAX_RAD = 1.0
G1_HIP_ROLL_LIMITS_RAD = (-0.9, 0.9)
G1_HIP_YAW_LIMITS_RAD = (-0.7, 0.7)
G1_KNEE_LIMITS_RAD = (0.0, 1.75)
G1_POSE_SEQUENCE_ARM_RAISE_DEG = 120.0


KYLE_USDSKEL_JOINT_CALIBRATION: Dict[str, Dict[str, List[float] | List[int]]] = {
    # Input semantic order from _pose_frame_from_trace_frame is:
    # arm=[raise, depth, side], leg=[pitch, 0, 0], spine=[0, 0, roll].
    # KyleRobot's UsdSkel local axes are not the same as RGB-D body axes, so
    # this table remaps/signs the coarse pose into a better skeleton-space seed.
    "Hips": {"sign": [1.0, 1.0, -1.0], "scale": [1.0, 1.0, 0.45]},
    "Spine1": {"sign": [1.0, 1.0, -1.0], "scale": [1.0, 1.0, 0.85]},
    "LeftArm": {"order": [0, 2, 1], "sign": [1.0, 1.0, -1.0], "scale": [0.55, 0.9, 0.75]},
    "RightArm": {"order": [0, 2, 1], "sign": [1.0, 1.0, 1.0], "scale": [0.55, 0.9, 0.75]},
    "LeftForeArm": {"sign": [1.0, 1.0, 1.0], "scale": [1.0, 1.0, 1.0]},
    "RightForeArm": {"sign": [1.0, 1.0, 1.0], "scale": [1.0, 1.0, 1.0]},
    "LeftForearm": {"sign": [1.0, 1.0, 1.0], "scale": [1.0, 1.0, 1.0]},
    "RightForearm": {"sign": [1.0, 1.0, 1.0], "scale": [1.0, 1.0, 1.0]},
    "LeftLeg": {"sign": [-1.0, 1.0, 1.0], "scale": [1.15, 1.0, 1.0]},
    "RightLeg": {"sign": [-1.0, 1.0, 1.0], "scale": [1.15, 1.0, 1.0]},
    "LeftUpLeg": {"sign": [-1.0, 1.0, 1.0], "scale": [1.15, 1.0, 1.0]},
    "RightUpLeg": {"sign": [-1.0, 1.0, 1.0], "scale": [1.15, 1.0, 1.0]},
}

KYLE_USDSKEL_NEUTRAL_JOINTS_DEG: Dict[str, List[float]] = {
    "Hips": [0.0, 0.0, 0.0],
    "Spine1": [0.0, 0.0, 0.0],
    "Spine2": [0.0, 0.0, 0.0],
    "Neck": [0.0, 0.0, 0.0],
    "Head": [0.0, 0.0, 0.0],
    "LeftShoulder": [0.0, 0.0, 0.0],
    "RightShoulder": [0.0, 0.0, 0.0],
    "LeftArm": [25.0, 0.0, -55.0],
    "RightArm": [25.0, 0.0, 55.0],
    "LeftForeArm": [8.0, 0.0, 0.0],
    "RightForeArm": [8.0, 0.0, 0.0],
    "LeftForearm": [8.0, 0.0, 0.0],
    "RightForearm": [8.0, 0.0, 0.0],
    "LeftLeg": [0.0, 0.0, 0.0],
    "RightLeg": [0.0, 0.0, 0.0],
    "LeftUpLeg": [0.0, 0.0, 0.0],
    "RightUpLeg": [0.0, 0.0, 0.0],
    "LeftKnee": [0.0, 0.0, 0.0],
    "RightKnee": [0.0, 0.0, 0.0],
}


def _pose_calibration_profile_name(value: Any) -> str:
    profile = _text(value or os.getenv("RGBD_POSE_CALIBRATION", "")).lower()
    if profile in {"", "auto"}:
        return "auto"
    if profile in {"none", "off", "false", "0"}:
        return "none"
    if profile in {"kyle", "kyle_usdskel", "kyle_usdskel_v1", "usdskel"}:
        return "kyle_usdskel_v1"
    return profile


def _kyle_neutral_rotation(joint_name: str) -> List[float]:
    return list(KYLE_USDSKEL_NEUTRAL_JOINTS_DEG.get(joint_name, [0.0, 0.0, 0.0]))


def _calibrate_pose_rotation(
    joint_name: str,
    rotation: List[float],
    *,
    profile: str,
) -> List[float]:
    if profile != "kyle_usdskel_v1":
        return [round(float(value), 3) for value in rotation[:3]]

    spec = KYLE_USDSKEL_JOINT_CALIBRATION.get(joint_name)
    if not spec:
        return [round(float(value), 3) for value in rotation[:3]]

    values = [float(value) for value in rotation[:3]]
    while len(values) < 3:
        values.append(0.0)
    order = spec.get("order", [0, 1, 2])
    sign = spec.get("sign", [1.0, 1.0, 1.0])
    scale = spec.get("scale", [1.0, 1.0, 1.0])
    offset = spec.get("offset", [0.0, 0.0, 0.0])
    calibrated: List[float] = []
    for index in range(3):
        source_index = int(order[index]) if index < len(order) else index
        raw = values[source_index] if 0 <= source_index < len(values) else 0.0
        next_value = raw
        next_value *= float(sign[index]) if index < len(sign) else 1.0
        next_value *= float(scale[index]) if index < len(scale) else 1.0
        next_value += float(offset[index]) if index < len(offset) else 0.0
        calibrated.append(round(next_value, 3))
    return calibrated


def _calibrate_pose_joints(
    joints: Dict[str, List[float]],
    *,
    profile: str,
) -> Dict[str, List[float]]:
    profile = _pose_calibration_profile_name(profile)
    if profile in {"none", "auto"}:
        return {
            str(name): [round(float(value), 3) for value in values[:3]]
            for name, values in joints.items()
        }
    return {
        str(name): _calibrate_pose_rotation(str(name), values, profile=profile)
        for name, values in joints.items()
    }


def _rotate_x(value: tuple[float, float, float], angle: float) -> tuple[float, float, float]:
    x, y, z = value
    c = math.cos(angle)
    s = math.sin(angle)
    return (x, y * c - z * s, y * s + z * c)


def _rotate_y(value: tuple[float, float, float], angle: float) -> tuple[float, float, float]:
    x, y, z = value
    c = math.cos(angle)
    s = math.sin(angle)
    return (x * c + z * s, y, -x * s + z * c)


def _rotate_z(value: tuple[float, float, float], angle: float) -> tuple[float, float, float]:
    x, y, z = value
    c = math.cos(angle)
    s = math.sin(angle)
    return (x * c - y * s, x * s + y * c, z)


def _rotate_axis(
    value: tuple[float, float, float],
    axis: tuple[float, float, float],
    angle: float,
) -> tuple[float, float, float]:
    ux, uy, uz = _normalize3(axis)
    if abs(ux) + abs(uy) + abs(uz) <= 1.0e-8:
        return value
    x, y, z = value
    c = math.cos(angle)
    s = math.sin(angle)
    dot = ux * x + uy * y + uz * z
    return (
        x * c + (uy * z - uz * y) * s + ux * dot * (1.0 - c),
        y * c + (uz * x - ux * z) * s + uy * dot * (1.0 - c),
        z * c + (ux * y - uy * x) * s + uz * dot * (1.0 - c),
    )


def _g1_shoulder_roll_limits(side: str) -> tuple[float, float]:
    return G1_LEFT_SHOULDER_ROLL_LIMITS_RAD if side == "left" else G1_RIGHT_SHOULDER_ROLL_LIMITS_RAD


def _apply_g1_ball_joint_rotation(
    value: tuple[float, float, float],
    pitch: float,
    roll: float,
    yaw: float,
) -> tuple[float, float, float]:
    result = _rotate_x(value, pitch)
    result = _rotate_y(result, yaw)
    result = _rotate_z(result, -roll)
    return result


def _g1_shoulder_fk_direction(pitch: float, roll: float, yaw: float) -> tuple[float, float, float]:
    return _normalize3(_apply_g1_ball_joint_rotation((0.0, -1.0, 0.0), pitch, roll, yaw))


def _g1_shoulder_ik_score(
    target: tuple[float, float, float],
    pitch: float,
    roll: float,
    yaw: float,
    neutral: tuple[float, float, float],
) -> float:
    direction = _g1_shoulder_fk_direction(pitch, roll, yaw)
    alignment = 1.0 - _clamp(_dot3(direction, target), -1.0, 1.0)
    effort = (
        (pitch - neutral[0]) * (pitch - neutral[0])
        + (roll - neutral[1]) * (roll - neutral[1])
        + (yaw - neutral[2]) * (yaw - neutral[2])
    )
    return alignment + 0.003 * effort


def _linspace(minimum: float, maximum: float, count: int) -> List[float]:
    if count <= 1:
        return [(minimum + maximum) * 0.5]
    step = (maximum - minimum) / float(count - 1)
    return [minimum + step * index for index in range(count)]


def _body_offset(
    value: tuple[float, float, float],
    axes: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
) -> tuple[float, float, float]:
    right_axis, up_axis, forward_axis = axes
    return (_dot3(value, right_axis), _dot3(value, up_axis), _dot3(value, forward_axis))


def _add3(left: tuple[float, float, float], right: tuple[float, float, float]) -> tuple[float, float, float]:
    return (left[0] + right[0], left[1] + right[1], left[2] + right[2])


def _blend3(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
    alpha: float,
) -> tuple[float, float, float]:
    alpha = _clamp(alpha, 0.0, 1.0)
    return (
        left[0] * (1.0 - alpha) + right[0] * alpha,
        left[1] * (1.0 - alpha) + right[1] * alpha,
        left[2] * (1.0 - alpha) + right[2] * alpha,
    )


def _sub3(left: tuple[float, float, float], right: tuple[float, float, float]) -> tuple[float, float, float]:
    return (left[0] - right[0], left[1] - right[1], left[2] - right[2])


def _dist_sq3(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    dx = left[0] - right[0]
    dy = left[1] - right[1]
    dz = left[2] - right[2]
    return dx * dx + dy * dy + dz * dz


def _g1_chain_fk(
    joints: List[float],
    *,
    first_length: float,
    second_length: float,
) -> tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]:
    pitch, roll, yaw, hinge, hinge_roll = joints
    first_dir = _normalize3(_apply_g1_ball_joint_rotation((0.0, -1.0, 0.0), pitch, roll, yaw))
    local_right = _normalize3(_apply_g1_ball_joint_rotation((1.0, 0.0, 0.0), pitch, roll, yaw))
    bend_axis = _normalize3(_rotate_axis(local_right, first_dir, hinge_roll))
    second_dir = _normalize3(_rotate_axis(first_dir, bend_axis, hinge))
    middle_pos = _scale3(first_dir, first_length)
    end_pos = _add3(middle_pos, _scale3(second_dir, second_length))
    return middle_pos, end_pos, first_dir, second_dir


def _coordinate_descent_ik(
    seeds: List[List[float]],
    bounds: List[tuple[float, float]],
    score_fn: Any,
) -> List[float]:
    best = [float(value) for value in seeds[0]]
    best_score = float(score_fn(best))
    for seed in seeds[1:]:
        candidate = [
            _clamp(float(value), bounds[index][0], bounds[index][1])
            for index, value in enumerate(seed)
        ]
        score = float(score_fn(candidate))
        if score < best_score:
            best = candidate
            best_score = score

    for step in (0.65, 0.35, 0.18, 0.09, 0.045, 0.022):
        for _ in range(2):
            improved = False
            for index, (lower, upper) in enumerate(bounds):
                for direction in (-1.0, 1.0):
                    candidate = list(best)
                    candidate[index] = _clamp(candidate[index] + direction * step, lower, upper)
                    score = float(score_fn(candidate))
                    if score + 1.0e-9 < best_score:
                        best = candidate
                        best_score = score
                        improved = True
            if not improved:
                break
    return best


def _scale_joint_solution(
    solution: List[float],
    neutral: List[float],
    bounds: List[tuple[float, float]],
    pose_scale: float,
) -> List[float]:
    return [
        _clamp_rad(neutral[index] + (float(value) - neutral[index]) * pose_scale, bounds[index][0], bounds[index][1])
        for index, value in enumerate(solution)
    ]


def _chain_flexion_from_lengths(upper_len: float, lower_len: float, reach_len: float) -> float:
    if upper_len <= 1.0e-6 or lower_len <= 1.0e-6:
        return 0.0
    cos_angle = _clamp(
        (upper_len * upper_len + lower_len * lower_len - reach_len * reach_len)
        / (2.0 * upper_len * lower_len),
        -1.0,
        1.0,
    )
    return _clamp(math.pi - math.acos(cos_angle), 0.0, math.pi)


def _mocap_middle_target(
    middle_target: tuple[float, float, float],
    end_target: tuple[float, float, float],
    *,
    middle_confidence: float,
) -> tuple[tuple[float, float, float], float, float]:
    reach_len = _len3(end_target)
    middle_len = _len3(middle_target)
    if reach_len <= 1.0e-6 or middle_len <= 1.0e-6:
        return middle_target, _clamp(middle_confidence, 0.0, 1.0), 0.0

    end_dir = _normalize3(end_target)
    middle_dir = _normalize3(middle_target)
    lower_len = _len3(_sub3(end_target, middle_target))
    observed_chain_len = max(middle_len + lower_len, reach_len, 1.0e-6)
    extension = _clamp((reach_len / observed_chain_len - 0.70) / 0.30, 0.0, 1.0)
    disagreement = _clamp((0.72 - _dot3(middle_dir, end_dir)) / 1.44, 0.0, 1.0)
    low_confidence = 1.0 - _clamp(middle_confidence, 0.0, 1.0)
    repair = _clamp(max(extension * disagreement, low_confidence * extension), 0.0, 1.0)
    if repair <= 1.0e-4:
        return middle_target, _clamp(middle_confidence, 0.0, 1.0), repair

    inferred_len = _clamp(
        max(middle_len, observed_chain_len * 0.48),
        min(0.18, reach_len),
        max(reach_len * 0.55, 0.18),
    )
    inferred = _scale3(end_dir, min(inferred_len, max(reach_len * 0.92, 0.18)))
    repaired = _blend3(middle_target, inferred, repair)
    return repaired, _clamp(middle_confidence * (1.0 - repair), 0.0, 1.0), repair


def _solve_g1_arm_full_ik(
    shoulder: tuple[float, float, float],
    elbow: tuple[float, float, float],
    wrist: tuple[float, float, float],
    *,
    side: str,
    pose_scale: float,
    elbow_confidence: float,
    axes: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
) -> List[float]:
    observed_elbow_target = _body_offset(_vec3(shoulder, elbow), axes)
    wrist_target = _body_offset(_vec3(shoulder, wrist), axes)
    elbow_target, elbow_weight, elbow_repair = _mocap_middle_target(
        observed_elbow_target,
        wrist_target,
        middle_confidence=elbow_confidence,
    )
    lower_target = _body_offset(_vec3(elbow, wrist), axes)
    if elbow_repair > 1.0e-4:
        lower_target = _sub3(wrist_target, elbow_target)
    first_length = max(_len3(elbow_target), 0.18)
    second_length = max(_len3(lower_target), first_length * 0.55, 0.15)
    neutral_roll = 0.18 if side == "left" else -0.18
    neutral = [0.0, neutral_roll, 0.0, 0.35, 0.0]
    bounds = [
        (G1_SHOULDER_PITCH_MIN_RAD, G1_SHOULDER_PITCH_MAX_RAD),
        _g1_shoulder_roll_limits(side),
        (G1_SHOULDER_YAW_MIN_RAD, G1_SHOULDER_YAW_MAX_RAD),
        G1_ELBOW_PITCH_LIMITS_RAD,
        G1_ELBOW_ROLL_LIMITS_RAD,
    ]
    upper_seed = list(_solve_g1_shoulder_ik(_normalize3(elbow_target), side=side, pose_scale=1.0))
    reach_seed = list(_solve_g1_shoulder_ik(_normalize3(wrist_target), side=side, pose_scale=1.0))
    observed_flexion = _flexion_rad(shoulder, elbow, wrist)
    inferred_flexion = _chain_flexion_from_lengths(first_length, second_length, _len3(wrist_target))
    flexion_seed = observed_flexion * elbow_weight + inferred_flexion * (1.0 - elbow_weight)
    seeds = [
        [*upper_seed, _clamp(flexion_seed, *G1_ELBOW_PITCH_LIMITS_RAD), 0.0],
        [*reach_seed, 0.0, 0.0],
        neutral,
        [-1.45, 1.70 if side == "left" else -1.70, -1.55 if side == "left" else 1.55, 0.0, 0.0],
        [-1.20, neutral_roll, 0.0, _clamp(flexion_seed, *G1_ELBOW_PITCH_LIMITS_RAD), 0.0],
    ]
    elbow_dir_target = _normalize3(elbow_target)
    wrist_dir_target = _normalize3(wrist_target)
    lower_dir_target = _normalize3(lower_target)

    def score(joints: List[float]) -> float:
        middle_pos, end_pos, first_dir, second_dir = _g1_chain_fk(
            joints,
            first_length=first_length,
            second_length=second_length,
        )
        effort = sum((joints[index] - neutral[index]) ** 2 for index in range(len(joints)))
        return (
            (0.35 + 1.10 * elbow_weight) * _dist_sq3(middle_pos, elbow_target)
            + 2.25 * _dist_sq3(end_pos, wrist_target)
            + (0.10 + 0.35 * elbow_weight) * (1.0 - _clamp(_dot3(first_dir, elbow_dir_target), -1.0, 1.0))
            + 0.65 * (1.0 - _clamp(_dot3(_normalize3(end_pos), wrist_dir_target), -1.0, 1.0))
            + 0.35 * (1.0 - _clamp(_dot3(second_dir, lower_dir_target), -1.0, 1.0))
            + 0.002 * effort
        )

    return _scale_joint_solution(_coordinate_descent_ik(seeds, bounds, score), neutral, bounds, pose_scale)


def _solve_g1_leg_full_ik(
    hip: tuple[float, float, float],
    knee: tuple[float, float, float],
    ankle: tuple[float, float, float],
    *,
    side: str,
    pose_scale: float,
    axes: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
) -> List[float]:
    knee_target = _body_offset(_vec3(hip, knee), axes)
    ankle_target = _body_offset(_vec3(hip, ankle), axes)
    shin_target = _body_offset(_vec3(knee, ankle), axes)
    thigh_length = max(_len3(knee_target), 0.22)
    shin_length = max(_len3(shin_target), thigh_length * 0.65, 0.20)
    neutral = [-0.08, 0.0, 0.0, 0.22, -0.12, 0.0]
    bounds = [
        (G1_HIP_PITCH_MIN_RAD, G1_HIP_PITCH_MAX_RAD),
        G1_HIP_ROLL_LIMITS_RAD,
        G1_HIP_YAW_LIMITS_RAD,
        G1_KNEE_LIMITS_RAD,
        (-0.9, 0.55),
        (-0.55, 0.55),
    ]
    side_axis = -1.0 if side == "left" else 1.0
    thigh_dir = _normalize3(knee_target)
    hip_pitch = -_angle_from_down(thigh_dir)
    hip_roll = _side_swing_angle(thigh_dir, side_axis=side_axis)
    knee_flexion = _flexion_rad(hip, knee, ankle)
    seed = [
        _clamp(-0.08 + 0.85 * hip_pitch, *bounds[0]),
        _clamp((1.0 if side == "left" else -1.0) * 0.65 * hip_roll, *bounds[1]),
        _clamp(0.35 * math.atan2(thigh_dir[2], max(0.12, abs(thigh_dir[1]))), *bounds[2]),
        _clamp(0.10 + 0.90 * knee_flexion, *bounds[3]),
        _clamp(-0.10 - 0.35 * knee_flexion, *bounds[4]),
        _clamp(-0.35 * shin_target[0] * side_axis, *bounds[5]),
    ]
    seeds = [seed, neutral, [seed[0], 0.0, 0.0, seed[3], seed[4], seed[5]]]
    knee_dir_target = _normalize3(knee_target)
    ankle_dir_target = _normalize3(ankle_target)
    shin_dir_target = _normalize3(shin_target)

    def score(joints: List[float]) -> float:
        middle_pos, end_pos, first_dir, second_dir = _g1_chain_fk(
            [joints[0], joints[1], joints[2], joints[3], 0.0],
            first_length=thigh_length,
            second_length=shin_length,
        )
        effort = sum((joints[index] - neutral[index]) ** 2 for index in range(4))
        return (
            1.35 * _dist_sq3(middle_pos, knee_target)
            + 2.0 * _dist_sq3(end_pos, ankle_target)
            + 0.45 * (1.0 - _clamp(_dot3(first_dir, knee_dir_target), -1.0, 1.0))
            + 0.55 * (1.0 - _clamp(_dot3(_normalize3(end_pos), ankle_dir_target), -1.0, 1.0))
            + 0.25 * (1.0 - _clamp(_dot3(second_dir, shin_dir_target), -1.0, 1.0))
            + 0.002 * effort
        )

    return _scale_joint_solution(_coordinate_descent_ik(seeds, bounds, score), neutral, bounds, pose_scale)


def _solve_g1_shoulder_ik(
    target: tuple[float, float, float],
    *,
    side: str,
    pose_scale: float,
) -> tuple[float, float, float]:
    target = _normalize3(target)
    if _len3(target) <= 1.0e-6:
        return (0.0, 0.18 if side == "left" else -0.18, 0.0)

    roll_min, roll_max = _g1_shoulder_roll_limits(side)
    pitch_min, pitch_max = G1_SHOULDER_PITCH_MIN_RAD, G1_SHOULDER_PITCH_MAX_RAD
    yaw_min, yaw_max = G1_SHOULDER_YAW_MIN_RAD, G1_SHOULDER_YAW_MAX_RAD
    neutral = (0.0, 0.18 if side == "left" else -0.18, 0.0)

    seeds = [
        neutral,
        (-0.25, neutral[1], 0.0),
        (-0.85, neutral[1], 0.0),
        (-1.35, 1.75 if side == "left" else -1.75, -1.55 if side == "left" else 1.55),
        (-1.70, 2.05 if side == "left" else -2.05, -1.90 if side == "left" else 1.90),
    ]
    best = min(seeds, key=lambda item: _g1_shoulder_ik_score(target, item[0], item[1], item[2], neutral))
    best_score = _g1_shoulder_ik_score(target, best[0], best[1], best[2], neutral)

    for pitch in _linspace(pitch_min, pitch_max, 11):
        for roll in _linspace(roll_min, roll_max, 11):
            for yaw in _linspace(yaw_min, yaw_max, 11):
                score = _g1_shoulder_ik_score(target, pitch, roll, yaw, neutral)
                if score < best_score:
                    best = (pitch, roll, yaw)
                    best_score = score

    pitch_span = (pitch_max - pitch_min) / 10.0
    roll_span = (roll_max - roll_min) / 10.0
    yaw_span = (yaw_max - yaw_min) / 10.0
    for _ in range(4):
        candidates = (
            _linspace(max(pitch_min, best[0] - pitch_span), min(pitch_max, best[0] + pitch_span), 5),
            _linspace(max(roll_min, best[1] - roll_span), min(roll_max, best[1] + roll_span), 5),
            _linspace(max(yaw_min, best[2] - yaw_span), min(yaw_max, best[2] + yaw_span), 5),
        )
        for pitch in candidates[0]:
            for roll in candidates[1]:
                for yaw in candidates[2]:
                    score = _g1_shoulder_ik_score(target, pitch, roll, yaw, neutral)
                    if score < best_score:
                        best = (pitch, roll, yaw)
                        best_score = score
        pitch_span *= 0.45
        roll_span *= 0.45
        yaw_span *= 0.45

    scaled = (
        neutral[0] + (best[0] - neutral[0]) * pose_scale,
        neutral[1] + (best[1] - neutral[1]) * pose_scale,
        neutral[2] + (best[2] - neutral[2]) * pose_scale,
    )
    return (
        _clamp_rad(scaled[0], pitch_min, pitch_max),
        _clamp_rad(scaled[1], roll_min, roll_max),
        _clamp_rad(scaled[2], yaw_min, yaw_max),
    )


def _angle_from_down(vector_in_body: tuple[float, float, float]) -> float:
    # Body coordinates are x=right, y=up, z=forward. Down is therefore -Y.
    return math.atan2(vector_in_body[2], -vector_in_body[1])


def _side_swing_angle(vector_in_body: tuple[float, float, float], *, side_axis: float) -> float:
    outward = _clamp(vector_in_body[0] * side_axis, -1.0, 1.0)
    down = max(0.08, abs(vector_in_body[1]))
    return math.atan2(outward, down)


def _add_g1_arm_targets(
    named: Dict[str, float],
    landmarks: Dict[str, Any],
    *,
    side: str,
    pose_scale: float,
    axes: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
) -> None:
    prefix = "left" if side == "left" else "right"
    label = "LEFT" if side == "left" else "RIGHT"
    shoulder = _point3(landmarks, f"{label}_SHOULDER")
    elbow = _point3(landmarks, f"{label}_ELBOW")
    wrist = _point3(landmarks, f"{label}_WRIST")
    if shoulder is None or elbow is None:
        return

    if wrist is not None:
        pitch, roll, yaw, elbow_pitch, elbow_roll = _solve_g1_arm_full_ik(
            shoulder,
            elbow,
            wrist,
            side=side,
            pose_scale=pose_scale,
            elbow_confidence=_landmark_confidence(landmarks, f"{label}_ELBOW"),
            axes=axes,
        )
        named[f"{prefix}_shoulder_pitch_joint"] = pitch
        named[f"{prefix}_shoulder_roll_joint"] = roll
        named[f"{prefix}_shoulder_yaw_joint"] = yaw
        named[f"{prefix}_elbow_pitch_joint"] = elbow_pitch
        named[f"{prefix}_elbow_roll_joint"] = elbow_roll
        return

    upper = _body_vector(_vec3(shoulder, elbow), axes)
    pitch, roll, yaw = _solve_g1_shoulder_ik(upper, side=side, pose_scale=pose_scale)
    named[f"{prefix}_shoulder_pitch_joint"] = pitch
    named[f"{prefix}_shoulder_roll_joint"] = roll
    named[f"{prefix}_shoulder_yaw_joint"] = yaw


def _add_g1_leg_targets(
    named: Dict[str, float],
    landmarks: Dict[str, Any],
    *,
    side: str,
    pose_scale: float,
    lower_body_scale: float = 1.0,
    axes: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
) -> None:
    prefix = "left" if side == "left" else "right"
    label = "LEFT" if side == "left" else "RIGHT"
    side_roll = 1.0 if side == "left" else -1.0
    side_axis = -1.0 if side == "left" else 1.0
    leg_scale = pose_scale * max(0.1, float(lower_body_scale))
    hip = _point3(landmarks, f"{label}_HIP")
    knee = _point3(landmarks, f"{label}_KNEE")
    ankle = _point3(landmarks, f"{label}_ANKLE")
    if hip is None or knee is None:
        return

    if ankle is not None:
        hip_pitch, hip_roll, hip_yaw, knee_joint, ankle_pitch, ankle_roll = _solve_g1_leg_full_ik(
            hip,
            knee,
            ankle,
            side=side,
            pose_scale=leg_scale,
            axes=axes,
        )
        named[f"{prefix}_hip_pitch_joint"] = hip_pitch
        named[f"{prefix}_hip_roll_joint"] = hip_roll
        named[f"{prefix}_hip_yaw_joint"] = hip_yaw
        named[f"{prefix}_knee_joint"] = knee_joint
        named[f"{prefix}_ankle_pitch_joint"] = ankle_pitch
        named[f"{prefix}_ankle_roll_joint"] = ankle_roll
        return

    thigh = _body_vector(_vec3(hip, knee), axes)
    hip_pitch = -_angle_from_down(thigh)
    hip_roll = _side_swing_angle(thigh, side_axis=side_axis)
    named[f"{prefix}_hip_pitch_joint"] = _clamp_rad(
        -0.08 + leg_scale * 0.85 * hip_pitch,
        G1_HIP_PITCH_MIN_RAD,
        G1_HIP_PITCH_MAX_RAD,
    )
    named[f"{prefix}_hip_roll_joint"] = _clamp_rad(leg_scale * side_roll * 0.65 * hip_roll, -0.9, 0.9)
    named[f"{prefix}_hip_yaw_joint"] = _clamp_rad(
        leg_scale * 0.35 * math.atan2(thigh[2], max(0.12, abs(thigh[1]))),
        -0.7,
        0.7,
    )

    if ankle is not None:
        shin = _body_vector(_vec3(knee, ankle), axes)
        knee_flexion = _flexion_rad(hip, knee, ankle)
        named[f"{prefix}_knee_joint"] = _clamp_rad(0.10 + leg_scale * 0.90 * knee_flexion, 0.0, 1.75)
        named[f"{prefix}_ankle_pitch_joint"] = _clamp_rad(-0.10 - leg_scale * 0.35 * knee_flexion, -0.9, 0.55)
        named[f"{prefix}_ankle_roll_joint"] = _clamp_rad(
            -leg_scale * 0.35 * _clamp(shin[0] * side_axis, -1.0, 1.0),
            -0.55,
            0.55,
        )


def _g1_named_targets_from_landmarks(
    landmarks: Dict[str, Any],
    *,
    pose_scale: float,
    lower_body_scale: float = 1.0,
) -> Dict[str, float]:
    chest_axes = _g1_body_axes_from_landmarks(landmarks)
    pelvis_axes = _g1_pelvis_axes_from_landmarks(landmarks)
    if chest_axes is None or pelvis_axes is None:
        return {}

    named: Dict[str, float] = {}
    left_shoulder = _point3(landmarks, "LEFT_SHOULDER")
    right_shoulder = _point3(landmarks, "RIGHT_SHOULDER")
    left_hip = _point3(landmarks, "LEFT_HIP")
    right_hip = _point3(landmarks, "RIGHT_HIP")

    if left_shoulder is not None and right_shoulder is not None and left_hip is not None and right_hip is not None:
        shoulder_axis = _normalize3(_vec3(left_shoulder, right_shoulder))
        hip_axis = _normalize3(_vec3(left_hip, right_hip))
        shoulder_center = _midpoint3(left_shoulder, right_shoulder)
        hip_center = _midpoint3(left_hip, right_hip)
        spine = _normalize3(_vec3(hip_center, shoulder_center)) if shoulder_center and hip_center else (0.0, 1.0, 0.0)
        yaw = _clamp_rad(0.35 * _signed_angle3(hip_axis, shoulder_axis, pelvis_axes[1]) * pose_scale, -0.25, 0.25)
        roll = _clamp_rad(
            math.atan2(_dot3(spine, pelvis_axes[0]), max(1.0e-5, _dot3(spine, pelvis_axes[1]))) * pose_scale,
            -0.35,
            0.35,
        )
        pitch = _clamp_rad(
            -math.atan2(_dot3(spine, pelvis_axes[2]), max(1.0e-5, _dot3(spine, pelvis_axes[1])))
            * pose_scale
            * _to_float(os.getenv("VLAGRAPH_MOTION_WAIST_PITCH_SIGN"), 1.0),
            -0.55,
            0.55,
        )
        named["waist_yaw_joint"] = yaw
        named["waist_roll_joint"] = roll
        named["waist_pitch_joint"] = pitch
        named["torso_joint"] = yaw

    _add_g1_arm_targets(named, landmarks, side="left", pose_scale=pose_scale, axes=chest_axes)
    _add_g1_arm_targets(named, landmarks, side="right", pose_scale=pose_scale, axes=chest_axes)
    _add_g1_leg_targets(
        named,
        landmarks,
        side="left",
        pose_scale=pose_scale,
        lower_body_scale=lower_body_scale,
        axes=pelvis_axes,
    )
    _add_g1_leg_targets(
        named,
        landmarks,
        side="right",
        pose_scale=pose_scale,
        lower_body_scale=lower_body_scale,
        axes=pelvis_axes,
    )
    return named


def _pose_frame_from_trace_frame(
    frame: Dict[str, Any],
    *,
    index: int,
    pose_scale: float,
    pose_calibration: str,
    lower_body_mode: str = "auto",
    lower_body_scale: float = 1.0,
    inactive_arm_deadzone: float = 0.14,
    limb_min_visibility: float = 0.42,
    prefer_pose_joints: bool = False,
    constrain_live_g1_targets: bool = False,
) -> Dict[str, Any]:
    features = frame.get("features") if isinstance(frame.get("features"), dict) else {}
    landmarks = frame.get("landmarks") if isinstance(frame.get("landmarks"), dict) else {}
    retarget_landmarks = frame.get("retarget_landmarks") if isinstance(frame.get("retarget_landmarks"), dict) else {}
    if not retarget_landmarks:
        retarget_landmarks = frame.get("world_landmarks") if isinstance(frame.get("world_landmarks"), dict) else {}
    if not retarget_landmarks:
        retarget_landmarks = landmarks
    retarget_features = frame.get("retarget_features") if isinstance(frame.get("retarget_features"), dict) else {}
    if not retarget_features:
        retarget_features = frame.get("world_features") if isinstance(frame.get("world_features"), dict) else {}
    feature_source = retarget_features if retarget_features else features
    angles = feature_source.get("angles_deg") if isinstance(feature_source.get("angles_deg"), dict) else {}
    retarget_landmark_source = _text(frame.get("retarget_landmark_source") or ("world_landmarks" if retarget_landmarks is not landmarks else "landmarks"))

    lower_body_scale = max(0.1, float(lower_body_scale))
    leg_pose_scale = pose_scale * lower_body_scale
    left_knee = _angle_flexion(angles, "left_knee", scale=0.75 * leg_pose_scale, maximum=95.0)
    right_knee = _angle_flexion(angles, "right_knee", scale=0.75 * leg_pose_scale, maximum=95.0)
    left_elbow = _angle_flexion(angles, "left_elbow", scale=0.8 * pose_scale, maximum=90.0)
    right_elbow = _angle_flexion(angles, "right_elbow", scale=0.8 * pose_scale, maximum=90.0)

    left_shoulder = _point3(retarget_landmarks, "LEFT_SHOULDER")
    right_shoulder = _point3(retarget_landmarks, "RIGHT_SHOULDER")
    left_hip = _point3(retarget_landmarks, "LEFT_HIP")
    right_hip = _point3(retarget_landmarks, "RIGHT_HIP")
    shoulder_width = _distance3(left_shoulder, right_shoulder)
    hip_width = _distance3(left_hip, right_hip)
    body_scale = shoulder_width or hip_width or 0.35
    calibration_profile = _pose_calibration_profile_name(pose_calibration)
    provided_g1_targets = frame.get("g1_named_targets")
    if not isinstance(provided_g1_targets, dict):
        provided_g1_targets = frame.get("joint_target_map")
    if not isinstance(provided_g1_targets, dict):
        provided_g1_targets = frame.get("named_joint_targets")
    if isinstance(provided_g1_targets, dict) and provided_g1_targets:
        g1_named_targets = {str(name): float(value) for name, value in provided_g1_targets.items()}
        g1_target_source = "precomputed_mediapipe_g1_targets"
    else:
        g1_named_targets = landmarks_to_g1_named_targets(retarget_landmarks)
        g1_target_source = "mediapipe_g1_mapping"
        if not g1_named_targets:
            g1_named_targets = _g1_named_targets_from_landmarks(
                retarget_landmarks,
                pose_scale=pose_scale,
                lower_body_scale=lower_body_scale,
            )
            g1_target_source = "motion_nodes_ik"

    left_raise = _vertical_raise_amount(
        landmarks,
        "LEFT_SHOULDER",
        "LEFT_ELBOW",
        "LEFT_WRIST",
        body_scale=body_scale,
    )
    right_raise = _vertical_raise_amount(
        landmarks,
        "RIGHT_SHOULDER",
        "RIGHT_ELBOW",
        "RIGHT_WRIST",
        body_scale=body_scale,
    )
    left_arm_raise = -round(G1_POSE_SEQUENCE_ARM_RAISE_DEG * left_raise * pose_scale, 3)
    right_arm_raise = -round(G1_POSE_SEQUENCE_ARM_RAISE_DEG * right_raise * pose_scale, 3)
    left_arm_side = round(_side_amount(retarget_landmarks, "LEFT_SHOULDER", "LEFT_ELBOW", body_scale=body_scale) * 35.0 * pose_scale, 3)
    right_arm_side = round(_side_amount(retarget_landmarks, "RIGHT_SHOULDER", "RIGHT_ELBOW", body_scale=body_scale) * 35.0 * pose_scale, 3)
    left_arm_depth = round(_depth_amount(retarget_landmarks, "LEFT_SHOULDER", "LEFT_ELBOW", "LEFT_WRIST", body_scale=body_scale) * 30.0 * pose_scale, 3)
    right_arm_depth = round(_depth_amount(retarget_landmarks, "RIGHT_SHOULDER", "RIGHT_ELBOW", "RIGHT_WRIST", body_scale=body_scale) * 30.0 * pose_scale, 3)
    if g1_named_targets and calibration_profile != "kyle_usdskel_v1" and not prefer_pose_joints:
        left_arm_raise = round(math.degrees(g1_named_targets.get("left_shoulder_pitch_joint", math.radians(left_arm_raise))), 3)
        right_arm_raise = round(math.degrees(g1_named_targets.get("right_shoulder_pitch_joint", math.radians(right_arm_raise))), 3)
        left_arm_side = round(math.degrees(g1_named_targets.get("left_shoulder_roll_joint", 0.18) - 0.18), 3)
        right_arm_side = round(math.degrees(g1_named_targets.get("right_shoulder_roll_joint", -0.18) + 0.18), 3)
        left_arm_depth = round(math.degrees(g1_named_targets.get("left_shoulder_yaw_joint", 0.0)), 3)
        right_arm_depth = round(math.degrees(g1_named_targets.get("right_shoulder_yaw_joint", 0.0)), 3)
        left_elbow = round(math.degrees(max(0.0, g1_named_targets.get("left_elbow_pitch_joint", 0.35) - 0.15)), 3)
        right_elbow = round(math.degrees(max(0.0, g1_named_targets.get("right_elbow_pitch_joint", 0.35) - 0.15)), 3)

    left_arm_visibility = _chain_visibility(retarget_landmarks, ("LEFT_SHOULDER", "LEFT_ELBOW", "LEFT_WRIST"))
    right_arm_visibility = _chain_visibility(retarget_landmarks, ("RIGHT_SHOULDER", "RIGHT_ELBOW", "RIGHT_WRIST"))
    left_arm_activity = _arm_activity_amount(
        raise_amount=left_raise,
        side_deg=left_arm_side,
        depth_deg=left_arm_depth,
        elbow_deg=left_elbow,
    )
    right_arm_activity = _arm_activity_amount(
        raise_amount=right_raise,
        side_deg=right_arm_side,
        depth_deg=right_arm_depth,
        elbow_deg=right_elbow,
    )
    deadzone = max(0.0, float(inactive_arm_deadzone))
    dominant_arm_ratio = _to_float(os.getenv("RGBD_RETARGET_DOMINANT_ARM_RATIO"), 0.38)
    strongest_arm_activity = max(left_arm_activity, right_arm_activity)
    if deadzone > 0.0 and strongest_arm_activity >= max(deadzone * 2.0, 0.35):
        if left_arm_activity < strongest_arm_activity * dominant_arm_ratio:
            left_arm_activity = 0.0
        if right_arm_activity < strongest_arm_activity * dominant_arm_ratio:
            right_arm_activity = 0.0
    left_arm_inactive = left_arm_visibility < limb_min_visibility or left_arm_activity < deadzone
    right_arm_inactive = right_arm_visibility < limb_min_visibility or right_arm_activity < deadzone
    if left_arm_inactive:
        left_arm_raise = 0.0
        left_arm_depth = 0.0
        left_arm_side = 0.0
        left_elbow = 0.0
    if right_arm_inactive:
        right_arm_raise = 0.0
        right_arm_depth = 0.0
        right_arm_side = 0.0
        right_elbow = 0.0

    ankle_y_delta = _landmark_axis_delta(retarget_landmarks, "LEFT_ANKLE", "RIGHT_ANKLE", "y")
    shoulder_x_delta = _landmark_axis_delta(retarget_landmarks, "LEFT_SHOULDER", "RIGHT_SHOULDER", "x")
    hip_x_delta = _landmark_axis_delta(retarget_landmarks, "LEFT_HIP", "RIGHT_HIP", "x")
    body_roll = round(_clamp((shoulder_x_delta - hip_x_delta) * 45.0 * pose_scale, -20.0, 20.0), 3)
    leg_swing = round(_clamp(ankle_y_delta * 80.0 * leg_pose_scale, -32.0, 32.0), 3)
    left_depth_swing = round(_leg_swing_amount(retarget_landmarks, "LEFT_HIP", "LEFT_ANKLE", body_scale=body_scale) * 28.0 * leg_pose_scale, 3)
    right_depth_swing = round(_leg_swing_amount(retarget_landmarks, "RIGHT_HIP", "RIGHT_ANKLE", body_scale=body_scale) * 28.0 * leg_pose_scale, 3)
    if g1_named_targets and calibration_profile != "kyle_usdskel_v1" and not prefer_pose_joints:
        if "left_hip_pitch_joint" in g1_named_targets:
            left_depth_swing = round(math.degrees(g1_named_targets["left_hip_pitch_joint"] + 0.08), 3)
        if "right_hip_pitch_joint" in g1_named_targets:
            right_depth_swing = round(math.degrees(g1_named_targets["right_hip_pitch_joint"] + 0.08), 3)
        if "left_knee_joint" in g1_named_targets:
            left_knee = round(math.degrees(max(0.0, g1_named_targets["left_knee_joint"] - 0.10)), 3)
        if "right_knee_joint" in g1_named_targets:
            right_knee = round(math.degrees(max(0.0, g1_named_targets["right_knee_joint"] - 0.10)), 3)

    lower_body_locked = _lower_body_should_lock(
        retarget_landmarks,
        mode=lower_body_mode,
        min_visibility=max(0.0, float(limb_min_visibility)),
    )
    if lower_body_locked:
        body_roll = 0.0
        leg_swing = 0.0
        left_depth_swing = 0.0
        right_depth_swing = 0.0
        left_knee = 0.0
        right_knee = 0.0

    g1_mapping_debug: Dict[str, Any] = {}
    if g1_named_targets:
        def set_g1_neutral(*joint_names: str) -> None:
            for joint_name in joint_names:
                g1_named_targets[joint_name] = float(G1_NEUTRAL_JOINTS.get(joint_name, 0.0))

        if left_arm_inactive:
            set_g1_neutral(
                "left_shoulder_pitch_joint",
                "left_shoulder_roll_joint",
                "left_shoulder_yaw_joint",
                "left_elbow_pitch_joint",
                "left_elbow_roll_joint",
            )
        if right_arm_inactive:
            set_g1_neutral(
                "right_shoulder_pitch_joint",
                "right_shoulder_roll_joint",
                "right_shoulder_yaw_joint",
                "right_elbow_pitch_joint",
                "right_elbow_roll_joint",
            )
        if lower_body_locked:
            set_g1_neutral(
                "torso_joint",
                "left_hip_pitch_joint",
                "left_hip_roll_joint",
                "left_hip_yaw_joint",
                "left_knee_joint",
                "left_ankle_pitch_joint",
                "left_ankle_roll_joint",
                "right_hip_pitch_joint",
                "right_hip_roll_joint",
                "right_hip_yaw_joint",
                "right_knee_joint",
                "right_ankle_pitch_joint",
                "right_ankle_roll_joint",
            )
        if g1_target_source != "motion_nodes_ik" and abs(float(pose_scale) - 1.0) > 1.0e-6:
            g1_named_targets = _scaled_g1_named_targets(g1_named_targets, pose_scale)
        _apply_inward_arm_roll_correction(g1_named_targets, retarget_landmarks)
        _apply_forward_arm_pitch_convention(g1_named_targets)
        _apply_closed_stance_leg_roll_correction(g1_named_targets, retarget_landmarks)
        if constrain_live_g1_targets:
            g1_named_targets, g1_mapping_debug = _constrain_live_rgbd_g1_targets(g1_named_targets)

    raw_joints = {
        "Hips": [0.0, 0.0, body_roll * 0.35],
        "Spine1": [0.0, 0.0, body_roll],
        "LeftLeg": [round(leg_swing + left_depth_swing - left_knee * 0.2, 3), 0.0, 0.0],
        "RightLeg": [round(-leg_swing + right_depth_swing - right_knee * 0.2, 3), 0.0, 0.0],
        "LeftUpLeg": [round(leg_swing + left_depth_swing - left_knee * 0.2, 3), 0.0, 0.0],
        "RightUpLeg": [round(-leg_swing + right_depth_swing - right_knee * 0.2, 3), 0.0, 0.0],
        "LeftKnee": [left_knee, 0.0, 0.0],
        "RightKnee": [right_knee, 0.0, 0.0],
        "LeftArm": [left_arm_raise, left_arm_depth, left_arm_side],
        "RightArm": [right_arm_raise, right_arm_depth, right_arm_side],
        "LeftForeArm": [left_elbow, 0.0, 0.0],
        "RightForeArm": [right_elbow, 0.0, 0.0],
        "LeftForearm": [left_elbow, 0.0, 0.0],
        "RightForearm": [right_elbow, 0.0, 0.0],
    }
    joints = _calibrate_pose_joints(raw_joints, profile=calibration_profile)
    if calibration_profile == "kyle_usdskel_v1":
        if left_arm_inactive:
            joints["LeftArm"] = _kyle_neutral_rotation("LeftArm")
            joints["LeftForeArm"] = _kyle_neutral_rotation("LeftForeArm")
            joints["LeftForearm"] = _kyle_neutral_rotation("LeftForearm")
        if right_arm_inactive:
            joints["RightArm"] = _kyle_neutral_rotation("RightArm")
            joints["RightForeArm"] = _kyle_neutral_rotation("RightForeArm")
            joints["RightForearm"] = _kyle_neutral_rotation("RightForearm")

    return {
        "index": index,
        "time_code": index,
        "timestamp_sec": frame.get("timestamp_sec", 0.0),
        "landmarks": landmarks,
        "retarget_landmarks": retarget_landmarks if retarget_landmarks is not landmarks else {},
        "retarget_landmark_source": retarget_landmark_source,
        "joints": joints,
        "raw_joints": raw_joints if calibration_profile != "none" else {},
        "pose_calibration": calibration_profile,
        "limb_filter": {
            "lower_body_locked": lower_body_locked,
            "lower_body_mode": lower_body_mode,
            "inactive_arm_deadzone": round(deadzone, 4),
            "limb_min_visibility": round(float(limb_min_visibility), 4),
            "left_arm_activity": round(left_arm_activity, 4),
            "right_arm_activity": round(right_arm_activity, 4),
            "left_arm_inactive": left_arm_inactive,
            "right_arm_inactive": right_arm_inactive,
            "left_arm_visibility": round(left_arm_visibility, 4),
            "right_arm_visibility": round(right_arm_visibility, 4),
            "g1_mapping": g1_mapping_debug,
            "g1_target_source": g1_target_source,
            "retarget_landmark_source": retarget_landmark_source,
        },
        "g1_named_targets": g1_named_targets,
    }


G1_NEUTRAL_JOINTS: Dict[str, float] = {
    "torso_joint": 0.0,
    "waist_yaw_joint": 0.0,
    "waist_roll_joint": 0.0,
    "waist_pitch_joint": 0.0,
    "left_hip_pitch_joint": -0.08,
    "left_hip_roll_joint": 0.0,
    "left_hip_yaw_joint": 0.0,
    "left_knee_joint": 0.22,
    "left_ankle_pitch_joint": -0.12,
    "left_ankle_roll_joint": 0.0,
    "right_hip_pitch_joint": -0.08,
    "right_hip_roll_joint": 0.0,
    "right_hip_yaw_joint": 0.0,
    "right_knee_joint": 0.22,
    "right_ankle_pitch_joint": -0.12,
    "right_ankle_roll_joint": 0.0,
    "left_shoulder_pitch_joint": 0.0,
    "left_shoulder_roll_joint": 0.18,
    "left_shoulder_yaw_joint": 0.0,
    "left_elbow_pitch_joint": 0.35,
    "left_elbow_roll_joint": 0.0,
    "right_shoulder_pitch_joint": 0.0,
    "right_shoulder_roll_joint": -0.18,
    "right_shoulder_yaw_joint": 0.0,
    "right_elbow_pitch_joint": 0.35,
    "right_elbow_roll_joint": 0.0,
}


def _g1_retarget_joint_order() -> List[str]:
    """Legacy GR00T order plus explicit physical G1 waist axes."""
    joints = list(g1_full_joint_order())
    for joint in G1_WAIST_3DOF_JOINTS:
        if joint not in joints:
            joints.append(joint)
    return joints

MOTION_LEARNING_G1_LIMITS_RAD: Dict[str, tuple[float, float]] = {
    "torso_joint": (-0.25, 0.25),
    "waist_yaw_joint": (-0.25, 0.25),
    "waist_roll_joint": (-0.35, 0.35),
    "waist_pitch_joint": (-0.55, 0.55),
    "left_hip_pitch_joint": (-0.36, 0.24),
    "right_hip_pitch_joint": (-0.36, 0.24),
    "left_hip_roll_joint": (-0.32, 0.32),
    "right_hip_roll_joint": (-0.32, 0.32),
    "left_hip_yaw_joint": (-0.28, 0.28),
    "right_hip_yaw_joint": (-0.28, 0.28),
    # Keep video retarget lower-body values stable but allow in-place pelvis
    # motion enough knee/ankle range to avoid floating feet.
    "left_knee_joint": (0.10, 0.68),
    "right_knee_joint": (0.10, 0.68),
    "left_ankle_pitch_joint": (-0.45, 0.24),
    "right_ankle_pitch_joint": (-0.45, 0.24),
    "left_ankle_roll_joint": (-0.25, 0.25),
    "right_ankle_roll_joint": (-0.25, 0.25),
    # Isaac/Unitree G1 treats negative shoulder pitch as arm-forward. MediaPipe
    # body-space IK can produce positive pitch for forward reach, so keep the
    # backward side intentionally shallow after the convention correction below.
    "left_shoulder_pitch_joint": (-1.35, 0.35),
    "right_shoulder_pitch_joint": (-1.35, 0.35),
    "left_shoulder_roll_joint": (-0.45, 0.78),
    "right_shoulder_roll_joint": (-0.78, 0.45),
    "left_shoulder_yaw_joint": (-0.85, 0.85),
    "right_shoulder_yaw_joint": (-0.85, 0.85),
    "left_elbow_pitch_joint": (0.0, 1.55),
    "right_elbow_pitch_joint": (0.0, 1.55),
    "left_elbow_roll_joint": (-0.75, 0.75),
    "right_elbow_roll_joint": (-0.75, 0.75),
}

LIVE_RGBD_G1_LIMITS_RAD: Dict[str, tuple[float, float]] = {
    # Live RGB-D landmarks are camera-space point estimates, not robot joint
    # angles. Keep noisy lateral/twist axes tighter than offline video retarget.
    "torso_joint": (-0.16, 0.16),
    "waist_yaw_joint": (-0.25, 0.25),
    "waist_roll_joint": (-0.35, 0.35),
    "waist_pitch_joint": (-0.55, 0.55),
    "left_hip_pitch_joint": (-0.45, 0.45),
    "right_hip_pitch_joint": (-0.45, 0.45),
    "left_hip_roll_joint": (-0.16, 0.16),
    "right_hip_roll_joint": (-0.16, 0.16),
    "left_hip_yaw_joint": (-0.12, 0.12),
    "right_hip_yaw_joint": (-0.12, 0.12),
    "left_knee_joint": (0.05, 0.70),
    "right_knee_joint": (0.05, 0.70),
    "left_ankle_pitch_joint": (-0.32, 0.20),
    "right_ankle_pitch_joint": (-0.32, 0.20),
    "left_ankle_roll_joint": (-0.12, 0.12),
    "right_ankle_roll_joint": (-0.12, 0.12),
    "left_shoulder_pitch_joint": (-1.45, 1.25),
    "right_shoulder_pitch_joint": (-1.45, 1.25),
    "left_shoulder_roll_joint": (-0.35, 0.95),
    "right_shoulder_roll_joint": (-0.95, 0.35),
    "left_shoulder_yaw_joint": (-0.45, 0.45),
    "right_shoulder_yaw_joint": (-0.45, 0.45),
    "left_elbow_pitch_joint": (0.05, 1.55),
    "right_elbow_pitch_joint": (0.05, 1.55),
    "left_elbow_roll_joint": (-0.28, 0.28),
    "right_elbow_roll_joint": (-0.28, 0.28),
}


def _clamp_rad(value: float, minimum: float, maximum: float) -> float:
    return round(max(minimum, min(maximum, value)), 6)


def _deg_to_rad(value: Any) -> float:
    try:
        return math.radians(float(value))
    except Exception:
        return 0.0


def _frame_joint_rotation(frame: Dict[str, Any], name: str, axis: int = 0) -> float:
    joints = frame.get("joints") if isinstance(frame.get("joints"), dict) else {}
    value = joints.get(name)
    if not isinstance(value, (list, tuple)) or axis >= len(value):
        return 0.0
    return _deg_to_rad(value[axis])


def _constrain_motion_learning_g1_targets(named: Dict[str, float]) -> Dict[str, float]:
    constrained: Dict[str, float] = {}
    joint_order = list(g1_full_joint_order())
    for joint in ("waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint"):
        if joint in named and joint not in joint_order:
            joint_order.append(joint)
    for joint in joint_order:
        value = float(named.get(joint, G1_NEUTRAL_JOINTS.get(joint, 0.0)))
        limits = MOTION_LEARNING_G1_LIMITS_RAD.get(joint)
        if limits is not None:
            value = _clamp(value, limits[0], limits[1])
        constrained[joint] = round(value, 6)
    return constrained


def _apply_inward_arm_roll_correction(named: Dict[str, float], landmarks: Dict[str, Any]) -> None:
    """Reduce outward shoulder roll when MediaPipe wrists move toward the torso center."""
    left_shoulder = _point3(landmarks, "LEFT_SHOULDER")
    right_shoulder = _point3(landmarks, "RIGHT_SHOULDER")
    left_wrist = _point3(landmarks, "LEFT_WRIST")
    right_wrist = _point3(landmarks, "RIGHT_WRIST")
    if left_shoulder is None or right_shoulder is None:
        return

    shoulder_width = max(abs(left_shoulder[0] - right_shoulder[0]), 1.0e-4)
    center_x = (left_shoulder[0] + right_shoulder[0]) * 0.5

    def inward_amount(side: str, wrist: tuple[float, float, float] | None, shoulder: tuple[float, float, float]) -> float:
        if wrist is None:
            return 0.0
        if side == "left":
            # Left wrist crossing left-shoulder inward means image x moves toward the torso center.
            raw = (shoulder[0] - wrist[0]) / shoulder_width
            crossed_center = center_x - wrist[0]
        else:
            raw = (wrist[0] - shoulder[0]) / shoulder_width
            crossed_center = wrist[0] - center_x
        return _clamp(max(raw, crossed_center / shoulder_width), 0.0, 1.0)

    left_inward = inward_amount("left", left_wrist, left_shoulder)
    right_inward = inward_amount("right", right_wrist, right_shoulder)

    if left_inward > 0.05:
        current = float(named.get("left_shoulder_roll_joint", G1_NEUTRAL_JOINTS["left_shoulder_roll_joint"]))
        # Positive left roll is outward abduction on the G1. Pull it back toward neutral/cross-body.
        target = 0.18 - 0.38 * left_inward
        named["left_shoulder_roll_joint"] = round(min(current, target), 6)
        named["left_shoulder_yaw_joint"] = round(float(named.get("left_shoulder_yaw_joint", 0.0)) * (1.0 - 0.35 * left_inward), 6)

    if right_inward > 0.05:
        current = float(named.get("right_shoulder_roll_joint", G1_NEUTRAL_JOINTS["right_shoulder_roll_joint"]))
        # Negative right roll is outward abduction on the G1. Pull it back toward neutral/cross-body.
        target = -0.18 + 0.38 * right_inward
        named["right_shoulder_roll_joint"] = round(max(current, target), 6)
        named["right_shoulder_yaw_joint"] = round(float(named.get("right_shoulder_yaw_joint", 0.0)) * (1.0 - 0.35 * right_inward), 6)


def _apply_forward_arm_pitch_convention(named: Dict[str, float]) -> None:
    """Convert MediaPipe forward-arm pitch to the Isaac G1 pitch convention."""
    for prefix in ("left", "right"):
        joint = f"{prefix}_shoulder_pitch_joint"
        current = float(named.get(joint, G1_NEUTRAL_JOINTS[joint]))
        if current > 0.05:
            # In the current Isaac G1 action path, positive shoulder pitch moves
            # the upper arm backward. Mirror only that positive side so video
            # forward reach stays forward while neutral/slight-backward motion
            # remains stable.
            current = -0.85 * current
        named[joint] = round(_clamp(current, -1.35, 0.35), 6)

def _apply_closed_stance_leg_roll_correction(named: Dict[str, float], landmarks: Dict[str, Any]) -> None:
    """Dampen lateral leg roll when MediaPipe knees/ankles indicate a closed stance."""
    left_hip = _point3(landmarks, "LEFT_HIP")
    right_hip = _point3(landmarks, "RIGHT_HIP")
    left_knee = _point3(landmarks, "LEFT_KNEE")
    right_knee = _point3(landmarks, "RIGHT_KNEE")
    left_ankle = _point3(landmarks, "LEFT_ANKLE")
    right_ankle = _point3(landmarks, "RIGHT_ANKLE")
    hip_width = _distance3(left_hip, right_hip)
    if not hip_width or hip_width <= 1.0e-5:
        return

    knee_width = _distance3(left_knee, right_knee) or hip_width
    ankle_width = _distance3(left_ankle, right_ankle) or knee_width
    stance_ratio = min(knee_width, ankle_width) / hip_width
    if stance_ratio >= 1.22:
        return

    # A closed or neutral stance should not command symmetric outward hip roll.
    # The stronger the leg centers move together, the closer we pull roll axes to neutral.
    damp = _clamp((stance_ratio - 0.62) / 0.60, 0.08, 0.35)
    for prefix in ("left", "right"):
        hip_roll_joint = f"{prefix}_hip_roll_joint"
        ankle_roll_joint = f"{prefix}_ankle_roll_joint"
        named[hip_roll_joint] = round(float(named.get(hip_roll_joint, 0.0)) * damp, 6)
        named[ankle_roll_joint] = round(float(named.get(ankle_roll_joint, 0.0)) * min(0.30, damp), 6)


def _constrain_live_rgbd_g1_targets(named: Dict[str, float]) -> tuple[Dict[str, float], Dict[str, Any]]:
    enabled = _to_bool(os.getenv("RGBD_RETARGET_CONSTRAIN_LIVE_G1_TARGETS"), True)
    joint_order = _g1_retarget_joint_order()
    raw_values = {
        joint: float(named.get(joint, G1_NEUTRAL_JOINTS.get(joint, 0.0)))
        for joint in joint_order
    }
    if not enabled:
        return dict(named), {
            "enabled": False,
            "input_range": _numeric_range(list(raw_values.values())),
            "output_range": _numeric_range(list(raw_values.values())),
            "clipped": 0,
        }

    constrained: Dict[str, float] = {}
    clipped: Dict[str, Dict[str, float]] = {}
    for joint in joint_order:
        value = raw_values[joint]
        limits = LIVE_RGBD_G1_LIMITS_RAD.get(joint)
        if limits is not None:
            limited = _clamp(value, limits[0], limits[1])
            if abs(limited - value) > 1.0e-6:
                clipped[joint] = {"raw": round(value, 6), "limited": round(limited, 6)}
            value = limited
        constrained[joint] = round(value, 6)

    clipped_ranked = sorted(
        clipped.items(),
        key=lambda item: abs(item[1]["raw"] - item[1]["limited"]),
        reverse=True,
    )
    debug = {
        "enabled": True,
        "input_range": _numeric_range(list(raw_values.values())),
        "output_range": _numeric_range(list(constrained.values())),
        "clipped": len(clipped),
        "top_clipped": {joint: values for joint, values in clipped_ranked[:6]},
    }
    return constrained, debug


def _scaled_g1_named_targets(named: Dict[str, float], scale: float) -> Dict[str, float]:
    scale = _clamp(float(scale), 0.05, 1.45)
    joint_order = list(g1_full_joint_order())
    for joint in ("waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint"):
        if joint in named and joint not in joint_order:
            joint_order.append(joint)
    return {
        joint: round(
            float(G1_NEUTRAL_JOINTS.get(joint, 0.0))
            + (float(named.get(joint, G1_NEUTRAL_JOINTS.get(joint, 0.0))) - float(G1_NEUTRAL_JOINTS.get(joint, 0.0))) * scale,
            6,
        )
        for joint in joint_order
    }


def _g1_action_payload_from_named(
    named: Dict[str, float],
    *,
    source: str,
    window: int,
    selection: str = "",
    frame_indices: List[int] | None = None,
    constrain_motion_learning: bool = False,
) -> Dict[str, Any]:
    joint_names = _g1_retarget_joint_order()
    if constrain_motion_learning:
        named_targets = _constrain_motion_learning_g1_targets(named)
    else:
        named_targets = {
            joint: round(float(named.get(joint, G1_NEUTRAL_JOINTS.get(joint, 0.0))), 6)
            for joint in joint_names
        }
    joint_targets = [named_targets[joint] for joint in joint_names]
    joint_groups = {
        group_name: [named_targets[joint] for joint in G1_JOINT_GROUPS[group_name]]
        for group_name in G1_GROUP_ORDER
    }
    payload = {
        "embodiment_tag": "REAL_G1",
        "joint_schema": g1_schema_payload(),
        "joint_names": joint_names,
        "joint_order": list(joint_names),
        "joint_targets": joint_targets,
        "joint_positions": joint_targets,
        "joint_target_map": dict(named_targets),
        "named_joint_targets": dict(named_targets),
        "g1_named_targets": dict(named_targets),
        "joint_order_source": "g1_schema_named",
        "joint_groups": joint_groups,
        "retarget_source": source,
        "retarget_window": int(window),
        **joint_groups,
    }
    if selection:
        payload["retarget_selection"] = selection
    if frame_indices is not None:
        payload["retarget_frame_indices"] = [int(index) for index in frame_indices]
    return payload


def _g1_pose_activity_score(targets: Dict[str, float]) -> float:
    def value(joint: str) -> float:
        return float(targets.get(joint, G1_NEUTRAL_JOINTS.get(joint, 0.0)))

    left_knee = max(0.0, value("left_knee_joint") - G1_NEUTRAL_JOINTS["left_knee_joint"])
    right_knee = max(0.0, value("right_knee_joint") - G1_NEUTRAL_JOINTS["right_knee_joint"])
    left_hip = value("left_hip_pitch_joint") - G1_NEUTRAL_JOINTS["left_hip_pitch_joint"]
    right_hip = value("right_hip_pitch_joint") - G1_NEUTRAL_JOINTS["right_hip_pitch_joint"]

    knee_peak = max(left_knee, right_knee)
    knee_asymmetry = abs(left_knee - right_knee)
    knee_collapse = min(left_knee, right_knee)
    hip_asymmetry = abs(left_hip - right_hip)
    hip_extreme = max(0.0, abs(value("left_hip_pitch_joint")) - 0.75) + max(
        0.0,
        abs(value("right_hip_pitch_joint")) - 0.75,
    )
    torso_twist = abs(value("torso_joint"))
    arm_motion = 0.0
    for joint in (
        "left_shoulder_pitch_joint",
        "right_shoulder_pitch_joint",
        "left_shoulder_roll_joint",
        "right_shoulder_roll_joint",
        "left_elbow_pitch_joint",
        "right_elbow_pitch_joint",
    ):
        arm_motion += abs(value(joint) - G1_NEUTRAL_JOINTS.get(joint, 0.0))

    return (
        3.5 * knee_asymmetry
        + 1.4 * knee_peak
        + 1.2 * hip_asymmetry
        + 0.08 * arm_motion
        - 2.2 * knee_collapse
        - 2.2 * hip_extreme
        - 0.5 * torso_twist
    )


def _g1_balanced_pose_score(targets: Dict[str, float]) -> float:
    def value(joint: str) -> float:
        return float(targets.get(joint, G1_NEUTRAL_JOINTS.get(joint, 0.0)))

    left_knee = max(0.0, value("left_knee_joint") - G1_NEUTRAL_JOINTS["left_knee_joint"])
    right_knee = max(0.0, value("right_knee_joint") - G1_NEUTRAL_JOINTS["right_knee_joint"])
    left_hip = value("left_hip_pitch_joint") - G1_NEUTRAL_JOINTS["left_hip_pitch_joint"]
    right_hip = value("right_hip_pitch_joint") - G1_NEUTRAL_JOINTS["right_hip_pitch_joint"]
    shoulder_pitch_sum = value("left_shoulder_pitch_joint") + value("right_shoulder_pitch_joint")
    shoulder_pitch_diff = abs(value("left_shoulder_pitch_joint") - value("right_shoulder_pitch_joint"))
    elbow_flex = max(0.0, value("left_elbow_pitch_joint") - 0.35) + max(
        0.0,
        value("right_elbow_pitch_joint") - 0.35,
    )
    lateral_noise = (
        abs(value("left_hip_roll_joint"))
        + abs(value("right_hip_roll_joint"))
        + abs(value("left_hip_yaw_joint"))
        + abs(value("right_hip_yaw_joint"))
        + abs(value("torso_joint"))
    )
    shoulder_lateral = abs(value("left_shoulder_roll_joint")) + abs(value("right_shoulder_roll_joint"))
    return (
        3.0 * (left_knee + right_knee)
        - 4.0 * abs(left_knee - right_knee)
        - 1.0 * abs(left_hip - right_hip)
        - 0.55 * lateral_noise
        + 0.30 * shoulder_pitch_sum
        - 0.30 * shoulder_pitch_diff
        + 0.20 * elbow_flex
        - 0.25 * shoulder_lateral
    )


def _stabilize_g1_balanced_pose(named: Dict[str, float]) -> Dict[str, float]:
    stabilized = dict(named)
    left_knee = float(stabilized.get("left_knee_joint", G1_NEUTRAL_JOINTS["left_knee_joint"]))
    right_knee = float(stabilized.get("right_knee_joint", G1_NEUTRAL_JOINTS["right_knee_joint"]))
    left_flex = max(0.0, left_knee - G1_NEUTRAL_JOINTS["left_knee_joint"])
    right_flex = max(0.0, right_knee - G1_NEUTRAL_JOINTS["right_knee_joint"])
    if min(left_flex, right_flex) < 0.45:
        return stabilized

    knee = _clamp_rad((left_knee + right_knee) * 0.5, 0.75, 1.35)
    hip_pitch = _clamp_rad(
        (
            float(stabilized.get("left_hip_pitch_joint", G1_NEUTRAL_JOINTS["left_hip_pitch_joint"]))
            + float(stabilized.get("right_hip_pitch_joint", G1_NEUTRAL_JOINTS["right_hip_pitch_joint"]))
        )
        * 0.5,
        0.12,
        0.62,
    )
    ankle_pitch = _clamp_rad(-0.12 - 0.28 * max(0.0, knee - 0.22), -0.55, -0.18)

    for side in ("left", "right"):
        stabilized[f"{side}_knee_joint"] = knee
        stabilized[f"{side}_hip_pitch_joint"] = hip_pitch
        stabilized[f"{side}_ankle_pitch_joint"] = ankle_pitch
        stabilized[f"{side}_hip_roll_joint"] = _clamp_rad(float(stabilized.get(f"{side}_hip_roll_joint", 0.0)) * 0.12, -0.18, 0.18)
        stabilized[f"{side}_hip_yaw_joint"] = _clamp_rad(float(stabilized.get(f"{side}_hip_yaw_joint", 0.0)) * 0.15, -0.16, 0.16)
        stabilized[f"{side}_ankle_roll_joint"] = _clamp_rad(float(stabilized.get(f"{side}_ankle_roll_joint", 0.0)) * 0.15, -0.12, 0.12)

    stabilized["torso_joint"] = _clamp_rad(float(stabilized.get("torso_joint", 0.0)) * 0.10, -0.05, 0.05)

    left_shoulder_pitch = float(stabilized.get("left_shoulder_pitch_joint", 0.0))
    right_shoulder_pitch = float(stabilized.get("right_shoulder_pitch_joint", 0.0))
    if max(left_shoulder_pitch, right_shoulder_pitch) > 0.35:
        shoulder_pitch = _clamp_rad((left_shoulder_pitch + right_shoulder_pitch) * 0.5, 0.45, 0.95)
        stabilized["left_shoulder_pitch_joint"] = shoulder_pitch
        stabilized["right_shoulder_pitch_joint"] = shoulder_pitch
        stabilized["left_shoulder_roll_joint"] = 0.18
        stabilized["right_shoulder_roll_joint"] = -0.18
        stabilized["left_shoulder_yaw_joint"] = _clamp_rad(float(stabilized.get("left_shoulder_yaw_joint", 0.0)) * 0.18, -0.22, 0.22)
        stabilized["right_shoulder_yaw_joint"] = _clamp_rad(float(stabilized.get("right_shoulder_yaw_joint", 0.0)) * 0.18, -0.22, 0.22)
        elbow_values = [
            float(stabilized.get(joint, 0.0))
            for joint in ("left_elbow_pitch_joint", "right_elbow_pitch_joint")
            if float(stabilized.get(joint, 0.0)) > 0.25
        ]
        elbow = _clamp_rad(sum(elbow_values) / len(elbow_values) if elbow_values else 0.65, 0.50, 1.05)
        stabilized["left_elbow_pitch_joint"] = elbow
        stabilized["right_elbow_pitch_joint"] = elbow

    return stabilized


def _average_g1_named_targets(frames: List[Dict[str, float]]) -> Dict[str, float]:
    joint_order = _g1_retarget_joint_order()
    named = {joint: float(G1_NEUTRAL_JOINTS.get(joint, 0.0)) for joint in joint_order}
    for joint in joint_order:
        values = [frame_targets[joint] for frame_targets in frames if joint in frame_targets]
        if values:
            named[joint] = sum(values) / len(values)
    return named


def _g1_joint_targets_from_pose_sequence(
    pose_sequence: List[Dict[str, Any]] | None,
    *,
    average_window: int = 5,
    selection: str = "recent",
    constrain_motion_learning: bool = False,
    prefer_pose_joints: bool = False,
) -> Dict[str, Any]:
    if not pose_sequence:
        return {}

    average_window = max(1, min(12, int(average_window or 5)))
    selection_key = _text(selection).lower().replace("-", "_") or "recent"
    named_frames: List[tuple[int, Dict[str, float]]] = []
    for index, candidate in enumerate(pose_sequence):
        if not isinstance(candidate, dict):
            continue
        if prefer_pose_joints:
            continue
        targets = candidate.get("g1_named_targets")
        if isinstance(targets, dict) and targets:
            named_frames.append((index, {str(name): float(value) for name, value in targets.items()}))

    if named_frames:
        selected_pairs: List[tuple[int, Dict[str, float]]]
        if selection_key in {"balanced", "symmetric", "squat", "crouch", "balanced_peak"}:
            ranked = sorted(
                named_frames,
                key=lambda item: (_g1_balanced_pose_score(item[1]), item[0]),
                reverse=True,
            )
            selected_pairs = ranked[:average_window]
        elif selection_key in {"peak", "representative", "best", "max", "motion_peak"}:
            ranked = sorted(
                named_frames,
                key=lambda item: (_g1_pose_activity_score(item[1]), item[0]),
                reverse=True,
            )
            selected_pairs = ranked[:average_window]
        elif selection_key in {"average", "mean", "all"}:
            selected_pairs = named_frames
        else:
            selected_pairs = named_frames[-average_window:]

        selected = [targets for _, targets in selected_pairs]
        selected_indices = [index for index, _ in selected_pairs]
        named = _average_g1_named_targets(selected)
        if selection_key in {"balanced", "symmetric", "squat", "crouch", "balanced_peak"}:
            named = _stabilize_g1_balanced_pose(named)
        return _g1_action_payload_from_named(
            named,
            source="pose_sequence_g1_targets",
            window=len(selected),
            selection=selection_key,
            frame_indices=selected_indices,
            constrain_motion_learning=constrain_motion_learning,
        )

    frame = next(
        (
            candidate
            for candidate in reversed(pose_sequence)
            if isinstance(candidate, dict) and isinstance(candidate.get("joints"), dict)
        ),
        None,
    )
    if frame is None:
        return {}

    named = {joint: float(G1_NEUTRAL_JOINTS.get(joint, 0.0)) for joint in g1_full_joint_order()}

    left_arm_pitch = _frame_joint_rotation(frame, "LeftArm", 0)
    right_arm_pitch = _frame_joint_rotation(frame, "RightArm", 0)
    left_arm_roll = _frame_joint_rotation(frame, "LeftArm", 2)
    right_arm_roll = _frame_joint_rotation(frame, "RightArm", 2)
    left_arm_yaw = _frame_joint_rotation(frame, "LeftArm", 1)
    right_arm_yaw = _frame_joint_rotation(frame, "RightArm", 1)
    left_elbow = _frame_joint_rotation(frame, "LeftForeArm", 0)
    right_elbow = _frame_joint_rotation(frame, "RightForeArm", 0)
    left_leg = _frame_joint_rotation(frame, "LeftUpLeg", 0) or _frame_joint_rotation(frame, "LeftLeg", 0)
    right_leg = _frame_joint_rotation(frame, "RightUpLeg", 0) or _frame_joint_rotation(frame, "RightLeg", 0)
    left_knee = _frame_joint_rotation(frame, "LeftKnee", 0)
    right_knee = _frame_joint_rotation(frame, "RightKnee", 0)

    named["left_shoulder_pitch_joint"] = _clamp_rad(left_arm_pitch, G1_SHOULDER_PITCH_MIN_RAD, 1.0)
    named["right_shoulder_pitch_joint"] = _clamp_rad(right_arm_pitch, G1_SHOULDER_PITCH_MIN_RAD, 1.0)
    named["left_shoulder_roll_joint"] = _clamp_rad(0.18 + left_arm_roll, -0.35, 1.15)
    named["right_shoulder_roll_joint"] = _clamp_rad(-0.18 + right_arm_roll, -1.15, 0.35)
    named["left_shoulder_yaw_joint"] = _clamp_rad(left_arm_yaw, -1.0, 1.0)
    named["right_shoulder_yaw_joint"] = _clamp_rad(right_arm_yaw, -1.0, 1.0)
    named["left_elbow_pitch_joint"] = _clamp_rad(0.35 + left_elbow, 0.0, 1.7)
    named["right_elbow_pitch_joint"] = _clamp_rad(0.35 + right_elbow, 0.0, 1.7)

    named["left_hip_pitch_joint"] = _clamp_rad(-0.08 + left_leg * 0.7, -0.9, 0.9)
    named["right_hip_pitch_joint"] = _clamp_rad(-0.08 + right_leg * 0.7, -0.9, 0.9)
    named["left_knee_joint"] = _clamp_rad(0.22 + left_knee, 0.0, 1.5)
    named["right_knee_joint"] = _clamp_rad(0.22 + right_knee, 0.0, 1.5)
    named["left_ankle_pitch_joint"] = _clamp_rad(-0.12 - left_knee * 0.45, -0.8, 0.6)
    named["right_ankle_pitch_joint"] = _clamp_rad(-0.12 - right_knee * 0.45, -0.8, 0.6)

    return _g1_action_payload_from_named(
        named,
        source="pose_joints",
        window=1,
        selection=selection_key,
        constrain_motion_learning=constrain_motion_learning,
    )


def _g1_joint_trajectory_from_pose_sequence(
    pose_sequence: List[Dict[str, Any]] | None,
    *,
    duration_sec: float,
    constrain_motion_learning: bool = False,
) -> Dict[str, Any]:
    if not pose_sequence:
        return {}

    joint_names = _g1_retarget_joint_order()
    frames: List[Dict[str, Any]] = []
    raw_times: List[float] = []
    for index, frame in enumerate(pose_sequence):
        if not isinstance(frame, dict):
            continue
        targets = frame.get("g1_named_targets")
        if not isinstance(targets, dict) or not targets:
            continue
        raw_named_targets = {
            joint: round(float(targets.get(joint, G1_NEUTRAL_JOINTS.get(joint, 0.0))), 6)
            for joint in joint_names
        }
        for joint in ("waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint"):
            if joint in targets:
                raw_named_targets[joint] = round(float(targets.get(joint, G1_NEUTRAL_JOINTS.get(joint, 0.0))), 6)
        named_targets = (
            _constrain_motion_learning_g1_targets(raw_named_targets)
            if constrain_motion_learning
            else raw_named_targets
        )
        try:
            raw_time = float(frame.get("timestamp_sec", index))
        except Exception:
            raw_time = float(index)
        raw_times.append(raw_time)
        frames.append(
            {
                "index": int(frame.get("index", index)),
                "time_sec": raw_time,
                "joint_schema": g1_schema_payload(),
                "joint_names": joint_names,
                "joint_order": list(joint_names),
                "joint_order_source": "g1_schema_named",
                "joint_targets": [named_targets[joint] for joint in joint_names],
                "joint_positions": [named_targets[joint] for joint in joint_names],
                "joint_target_map": dict(named_targets),
                "named_joint_targets": dict(named_targets),
                "g1_named_targets": dict(named_targets),
                "root_translation": frame.get("root_translation") or frame.get("rootTranslation"),
                "rootTranslation": frame.get("rootTranslation") or frame.get("root_translation"),
                "root_translation_mode": frame.get("root_translation_mode")
                or frame.get("rootTranslationMode")
                or "offset_from_initial",
                "rootTranslationMode": frame.get("rootTranslationMode")
                or frame.get("root_translation_mode")
                or "offset_from_initial",
                "root_motion_mode": frame.get("root_motion_mode") or frame.get("rootMotionMode"),
                "rootMotionMode": frame.get("rootMotionMode") or frame.get("root_motion_mode"),
                "foot_lock": bool(frame.get("foot_lock") or frame.get("footLock")),
                "footLock": bool(frame.get("footLock") or frame.get("foot_lock")),
                "pelvis_offset": frame.get("pelvis_offset") or frame.get("pelvisOffset"),
                "pelvisOffset": frame.get("pelvisOffset") or frame.get("pelvis_offset"),
                "in_place_pelvis_leg_compensation": frame.get("in_place_pelvis_leg_compensation"),
                "root_rotation": frame.get("root_rotation") or frame.get("rootRotation"),
                "rootRotation": frame.get("rootRotation") or frame.get("root_rotation"),
                "root_rotation_mode": frame.get("root_rotation_mode")
                or frame.get("rootRotationMode")
                or "offset_from_initial",
                "rootRotationMode": frame.get("rootRotationMode")
                or frame.get("root_rotation_mode")
                or "offset_from_initial",
            }
        )

    if not frames:
        return {}

    first_time = raw_times[0] if raw_times else 0.0
    normalized_times = [max(0.0, value - first_time) for value in raw_times]
    span = normalized_times[-1] if normalized_times else 0.0
    target_duration = max(0.0, float(duration_sec or 0.0))
    if target_duration <= 0.0:
        target_duration = span if span > 0.0 else max(0.1, (len(frames) - 1) / 15.0)
    scale = target_duration / span if span > 1.0e-6 else 0.0
    for index, frame in enumerate(frames):
        frame["time_sec"] = round(normalized_times[index] * scale if scale > 0.0 else index * target_duration / max(1, len(frames) - 1), 6)

    frames = _densify_g1_joint_trajectory_frames(frames, target_duration)
    trajectory_delta_debug = _limit_g1_joint_trajectory_delta(
        frames,
        max_delta_rad=_to_float(os.getenv("VLAGRAPH_MOTION_TRAJECTORY_MAX_FRAME_DELTA_RAD"), 0.10),
        arm_max_delta_rad=_to_float(os.getenv("VLAGRAPH_MOTION_TRAJECTORY_ARM_MAX_FRAME_DELTA_RAD"), 0.35),
    )
    root_values: List[float] = []
    root_rotation_values: List[float] = []
    for frame in frames:
        root_translation = frame.get("root_translation") or frame.get("rootTranslation")
        if isinstance(root_translation, (list, tuple)):
            root_values.extend(float(value) for value in list(root_translation)[:3])
        root_rotation = frame.get("root_rotation") or frame.get("rootRotation")
        if isinstance(root_rotation, (list, tuple)):
            root_rotation_values.extend(float(value) for value in list(root_rotation)[:3])
    print(
        "[MOTION_TRAJECTORY] "
        f"frames={len(frames)} duration={round(target_duration, 6)} "
        f"delta_debug={trajectory_delta_debug} "
        f"root_range={_numeric_range(root_values)} "
        f"root_rotation_range={_numeric_range(root_rotation_values)}"
    )

    return {
        "embodiment_tag": "REAL_G1",
        "joint_schema": g1_schema_payload(),
        "joint_names": joint_names,
        "joint_order": list(joint_names),
        "joint_order_source": "g1_schema_named",
        "joint_trajectory": frames,
        "g1_joint_trajectory": frames,
        "joint_trajectory_count": len(frames),
        "joint_trajectory_duration_sec": round(target_duration, 6),
        "joint_trajectory_delta_debug": trajectory_delta_debug,
        "retarget_mode": "joint_trajectory",
        "animation": False,
    }


def _densify_g1_joint_trajectory_frames(
    frames: List[Dict[str, Any]],
    duration_sec: float,
    *,
    target_hz: float = 8.0,
    max_frames: int = 120,
) -> List[Dict[str, Any]]:
    if len(frames) < 2:
        return frames

    duration_sec = max(0.0, float(duration_sec or 0.0))
    desired_count = int(duration_sec * target_hz) + 1 if duration_sec > 0.0 else len(frames)
    desired_count = max(len(frames), min(max_frames, desired_count))
    if desired_count <= len(frames):
        return frames

    source = sorted(frames, key=lambda item: float(item.get("time_sec", 0.0)))
    joint_names = list(source[0].get("joint_names") or g1_full_joint_order())
    source_times = [float(item.get("time_sec", index)) for index, item in enumerate(source)]
    if source_times[-1] <= source_times[0]:
        return frames

    dense_frames: List[Dict[str, Any]] = []
    cursor = 0
    for index in range(desired_count):
        target_time = duration_sec * index / max(1, desired_count - 1)
        while cursor < len(source_times) - 2 and source_times[cursor + 1] < target_time:
            cursor += 1

        left = source[cursor]
        right = source[min(cursor + 1, len(source) - 1)]
        left_time = float(left.get("time_sec", 0.0))
        right_time = float(right.get("time_sec", left_time))
        alpha = 0.0 if right_time <= left_time else _clamp((target_time - left_time) / (right_time - left_time), 0.0, 1.0)
        left_targets = left.get("g1_named_targets") if isinstance(left.get("g1_named_targets"), dict) else {}
        right_targets = right.get("g1_named_targets") if isinstance(right.get("g1_named_targets"), dict) else {}
        left_root = left.get("root_translation") or left.get("rootTranslation")
        right_root = right.get("root_translation") or right.get("rootTranslation")
        left_pelvis = left.get("pelvis_offset") or left.get("pelvisOffset")
        right_pelvis = right.get("pelvis_offset") or right.get("pelvisOffset")
        left_rotation = left.get("root_rotation") or left.get("rootRotation")
        right_rotation = right.get("root_rotation") or right.get("rootRotation")
        root_translation = None
        if isinstance(left_root, (list, tuple)) and isinstance(right_root, (list, tuple)):
            root_translation = [
                round(
                    float(left_root[axis] if axis < len(left_root) else 0.0) * (1.0 - alpha)
                    + float(right_root[axis] if axis < len(right_root) else 0.0) * alpha,
                    6,
                )
                for axis in range(3)
            ]
        pelvis_offset = None
        if isinstance(left_pelvis, (list, tuple)) and isinstance(right_pelvis, (list, tuple)):
            pelvis_offset = [
                round(
                    float(left_pelvis[axis] if axis < len(left_pelvis) else 0.0) * (1.0 - alpha)
                    + float(right_pelvis[axis] if axis < len(right_pelvis) else 0.0) * alpha,
                    6,
                )
                for axis in range(3)
            ]
        root_rotation = None
        if isinstance(left_rotation, (list, tuple)) and isinstance(right_rotation, (list, tuple)):
            root_rotation = [
                round(
                    float(left_rotation[axis] if axis < len(left_rotation) else 0.0) * (1.0 - alpha)
                    + float(right_rotation[axis] if axis < len(right_rotation) else 0.0) * alpha,
                    6,
                )
                for axis in range(3)
            ]
        named_targets = {
            joint: round(
                float(left_targets.get(joint, G1_NEUTRAL_JOINTS.get(joint, 0.0))) * (1.0 - alpha)
                + float(right_targets.get(joint, G1_NEUTRAL_JOINTS.get(joint, 0.0))) * alpha,
                6,
            )
            for joint in joint_names
        }
        for joint in ("waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint"):
            if joint in left_targets or joint in right_targets:
                named_targets[joint] = round(
                    float(left_targets.get(joint, G1_NEUTRAL_JOINTS.get(joint, 0.0))) * (1.0 - alpha)
                    + float(right_targets.get(joint, G1_NEUTRAL_JOINTS.get(joint, 0.0))) * alpha,
                    6,
                )
        dense_frames.append(
            {
                "index": index,
                "time_sec": round(target_time, 6),
                "joint_schema": g1_schema_payload(),
                "joint_names": joint_names,
                "joint_order": list(joint_names),
                "joint_order_source": "g1_schema_named",
                "joint_targets": [named_targets[joint] for joint in joint_names],
                "joint_positions": [named_targets[joint] for joint in joint_names],
                "joint_target_map": dict(named_targets),
                "named_joint_targets": dict(named_targets),
                "g1_named_targets": named_targets,
                "root_translation": root_translation,
                "rootTranslation": root_translation,
                "root_translation_mode": left.get("root_translation_mode")
                or left.get("rootTranslationMode")
                or "offset_from_initial",
                "rootTranslationMode": left.get("rootTranslationMode")
                or left.get("root_translation_mode")
                or "offset_from_initial",
                "root_motion_mode": left.get("root_motion_mode") or left.get("rootMotionMode"),
                "rootMotionMode": left.get("rootMotionMode") or left.get("root_motion_mode"),
                "foot_lock": bool(left.get("foot_lock") or left.get("footLock")),
                "footLock": bool(left.get("footLock") or left.get("foot_lock")),
                "pelvis_offset": pelvis_offset,
                "pelvisOffset": pelvis_offset,
                "in_place_pelvis_leg_compensation": left.get("in_place_pelvis_leg_compensation"),
                "root_rotation": root_rotation,
                "rootRotation": root_rotation,
                "root_rotation_mode": left.get("root_rotation_mode")
                or left.get("rootRotationMode")
                or "offset_from_initial",
                "rootRotationMode": left.get("rootRotationMode")
                or left.get("root_rotation_mode")
                or "offset_from_initial",
                "interpolated": True,
            }
        )

    dense_frames[0]["interpolated"] = bool(source[0].get("interpolated", False))
    dense_frames[-1]["interpolated"] = bool(source[-1].get("interpolated", False))
    return dense_frames


def _is_g1_arm_joint(joint_name: str) -> bool:
    normalized = str(joint_name or "").lower()
    return normalized.startswith(("left_shoulder_", "right_shoulder_", "left_elbow_", "right_elbow_"))


def _limit_g1_joint_trajectory_delta(
    frames: List[Dict[str, Any]],
    *,
    max_delta_rad: float = 0.10,
    arm_max_delta_rad: float | None = None,
) -> Dict[str, Any]:
    max_delta_rad = max(0.0, float(max_delta_rad))
    if arm_max_delta_rad is None:
        arm_max_delta_rad = max_delta_rad
    arm_max_delta_rad = max(0.0, float(arm_max_delta_rad))
    if max(max_delta_rad, arm_max_delta_rad) <= 0.0 or len(frames) < 2:
        return {"enabled": False, "limited_values": 0, "max_input_delta_rad": 0.0}

    previous: Dict[str, float] = {}
    limited_values = 0
    max_input_delta = 0.0
    for frame_index, frame in enumerate(frames):
        named = frame.get("g1_named_targets")
        if not isinstance(named, dict):
            named = frame.get("joint_target_map") if isinstance(frame.get("joint_target_map"), dict) else {}
        if not isinstance(named, dict) or not named:
            continue

        next_named: Dict[str, float] = {}
        joint_order = list(g1_full_joint_order())
        named_order = list(joint_order)
        for joint in ("waist_yaw_joint", "waist_roll_joint", "waist_pitch_joint"):
            if joint in named and joint not in named_order:
                named_order.append(joint)
        for joint in named_order:
            value = float(named.get(joint, G1_NEUTRAL_JOINTS.get(joint, 0.0)))
            if frame_index > 0 and joint in previous:
                raw_delta = value - previous[joint]
                max_input_delta = max(max_input_delta, abs(raw_delta))
                joint_max_delta = arm_max_delta_rad if _is_g1_arm_joint(joint) else max_delta_rad
                delta = _clamp(raw_delta, -joint_max_delta, joint_max_delta)
                if abs(delta - raw_delta) > 1e-9:
                    limited_values += 1
                value = previous[joint] + delta
            next_named[joint] = round(value, 6)

        previous = dict(next_named)
        joint_names = list(named_order)
        frame["joint_names"] = joint_names
        frame["joint_order"] = list(joint_names)
        frame["joint_targets"] = [next_named[joint] for joint in joint_names]
        frame["joint_positions"] = list(frame["joint_targets"])
        frame["joint_target_map"] = dict(next_named)
        frame["named_joint_targets"] = dict(next_named)
        frame["g1_named_targets"] = dict(next_named)

    return {
        "enabled": True,
        "max_delta_rad": round(max_delta_rad, 6),
        "arm_max_delta_rad": round(arm_max_delta_rad, 6),
        "limited_values": limited_values,
        "max_input_delta_rad": round(max_input_delta, 6),
    }


def _apply_g1_joint_smoothing(
    node_id: str,
    action: Dict[str, Any],
    smoothing: float,
    max_delta_rad: float = 0.0,
    deadband_rad: float = 0.0,
) -> Dict[str, Any]:
    if "joint_targets" not in action or "joint_names" not in action:
        return {}
    smoothing = _clamp(float(smoothing), 0.0, 0.95)
    max_delta_rad = max(0.0, float(max_delta_rad))
    deadband_rad = max(0.0, float(deadband_rad))
    if smoothing <= 0.0 and max_delta_rad <= 0.0 and deadband_rad <= 0.0:
        return {}

    joint_names = action.get("joint_names")
    joint_targets = action.get("joint_targets")
    if not isinstance(joint_names, list) or not isinstance(joint_targets, list):
        return {}

    previous = _RETARGET_SMOOTHING_BY_NODE.get(node_id, {})
    current = {
        str(name): float(value)
        for name, value in zip(joint_names, joint_targets)
    }
    smoothed: Dict[str, float] = {}
    deadband_held = 0
    delta_limited = 0
    max_raw_delta = 0.0
    max_output_delta = 0.0
    for name, value in current.items():
        old = previous.get(name)
        if old is None:
            smoothed[name] = value
            continue
        raw_delta = value - old
        max_raw_delta = max(max_raw_delta, abs(raw_delta))
        if deadband_rad > 0.0 and abs(value - old) < deadband_rad:
            smoothed[name] = old
            deadband_held += 1
            continue
        next_value = old * smoothing + value * (1.0 - smoothing)
        if max_delta_rad > 0.0:
            unclamped_delta = next_value - old
            delta = _clamp(unclamped_delta, -max_delta_rad, max_delta_rad)
            if abs(delta - unclamped_delta) > 1e-9:
                delta_limited += 1
            next_value = old + delta
        smoothed[name] = next_value
        max_output_delta = max(max_output_delta, abs(next_value - old))

    _RETARGET_SMOOTHING_BY_NODE[node_id] = smoothed
    smoothing_debug = {
        "joint_count": len(current),
        "previous_joint_count": len(previous),
        "deadband_held": deadband_held,
        "delta_limited": delta_limited,
        "max_raw_delta_rad": round(max_raw_delta, 6),
        "max_output_delta_rad": round(max_output_delta, 6),
        "smoothing": round(float(smoothing), 6),
        "max_delta_rad": round(float(max_delta_rad), 6),
        "deadband_rad": round(float(deadband_rad), 6),
    }
    action["joint_schema"] = g1_schema_payload()
    action["joint_order"] = list(joint_names)
    action["joint_order_source"] = "g1_schema_named"
    action["joint_smoothing"] = round(float(smoothing), 6)
    action["joint_max_delta_rad"] = round(float(max_delta_rad), 6)
    action["joint_deadband_rad"] = round(float(deadband_rad), 6)
    action["joint_targets"] = [round(smoothed.get(str(name), 0.0), 6) for name in joint_names]
    action["joint_positions"] = list(action["joint_targets"])
    action["joint_target_map"] = {str(name): round(smoothed.get(str(name), 0.0), 6) for name in joint_names}
    action["named_joint_targets"] = dict(action["joint_target_map"])
    action["g1_named_targets"] = dict(action["joint_target_map"])
    action["joint_smoothing_debug"] = dict(smoothing_debug)
    joint_groups = {
        group_name: [
            round(smoothed.get(joint, float(G1_NEUTRAL_JOINTS.get(joint, 0.0))), 6)
            for joint in G1_JOINT_GROUPS[group_name]
        ]
        for group_name in G1_GROUP_ORDER
    }
    action["joint_groups"] = joint_groups
    for group_name, values in joint_groups.items():
        action[group_name] = values
    return smoothing_debug


def _maybe_log_retarget_diagnostics(
    node_id: str,
    action: Dict[str, Any],
    diagnostics: Dict[str, Any],
    smoothing_debug: Dict[str, Any],
) -> None:
    mode = str(action.get("retarget_mode") or action.get("retargetMode") or "").strip().lower()
    if mode not in {"joint_targets", "streamed_joint_targets"}:
        return

    interval_sec = max(0.0, _to_float(os.getenv("VLAGRAPH_RETARGET_LOG_INTERVAL_SEC"), 1.0))
    if interval_sec <= 0.0:
        return
    now = time.monotonic()
    key = f"{node_id}:{mode}"
    last = _RETARGET_DIAGNOSTIC_LAST_LOG_AT.get(key, 0.0)
    if now - last < interval_sec:
        return
    _RETARGET_DIAGNOSTIC_LAST_LOG_AT[key] = now

    targets = action.get("joint_targets")
    named_targets = action.get("g1_named_targets") or action.get("joint_target_map") or {}
    if not isinstance(targets, list):
        targets = list(named_targets.values()) if isinstance(named_targets, dict) else []
    numeric_targets = [float(value) for value in targets if isinstance(value, (int, float))]
    nonzero_count = sum(1 for value in numeric_targets if abs(value) > 1e-4)
    root_translation = action.get("root_translation") or action.get("rootTranslation") or []
    print(
        "[RGBD_RETARGET] "
        f"node={node_id} mode={mode} "
        f"pose_frames={diagnostics.get('frames', diagnostics.get('pose_frames', 0))} "
        f"stream_frame={diagnostics.get('stream_frame_index', 0)}/"
        f"{diagnostics.get('stream_frame_count', 0)} "
        f"joints={len(numeric_targets)} nonzero={nonzero_count} "
        f"range={_numeric_range(numeric_targets)} "
        f"root={root_translation} "
        f"smoothing={diagnostics.get('joint_smoothing')} "
        f"max_delta={diagnostics.get('joint_max_delta_rad')} "
        f"deadband={diagnostics.get('joint_deadband_rad')} "
        f"g1_map_clip={diagnostics.get('g1_mapping_clipped')} "
        f"g1_map_in_abs={diagnostics.get('g1_mapping_input_abs')} "
        f"g1_map_out_abs={diagnostics.get('g1_mapping_output_abs')} "
        f"g1_map_top={diagnostics.get('g1_mapping_top_clipped')} "
        f"smooth_debug={smoothing_debug or {}}"
    )


def _apply_g1_joint_scale(action: Dict[str, Any], scale: float) -> None:
    named = action.get("g1_named_targets")
    if not isinstance(named, dict):
        named = action.get("named_joint_targets")
    if not isinstance(named, dict):
        named = action.get("joint_target_map")
    if not isinstance(named, dict):
        return

    scaled = _constrain_motion_learning_g1_targets(_scaled_g1_named_targets({str(k): float(v) for k, v in named.items()}, scale))
    joint_names = _g1_retarget_joint_order()
    joint_targets = [round(float(scaled.get(joint, G1_NEUTRAL_JOINTS.get(joint, 0.0))), 6) for joint in joint_names]
    joint_groups = {
        group_name: [scaled[joint] for joint in G1_JOINT_GROUPS[group_name]]
        for group_name in G1_GROUP_ORDER
    }
    action["joint_names"] = joint_names
    action["joint_schema"] = g1_schema_payload()
    action["joint_order"] = list(joint_names)
    action["joint_order_source"] = "g1_schema_named"
    action["joint_targets"] = joint_targets
    action["joint_positions"] = list(joint_targets)
    action["joint_target_map"] = dict(scaled)
    action["named_joint_targets"] = dict(scaled)
    action["g1_named_targets"] = dict(scaled)
    action["joint_groups"] = joint_groups
    for group_name, values in joint_groups.items():
        action[group_name] = values


def _set_g1_action_neutral_joints(action: Dict[str, Any], joint_names_to_neutral: List[str]) -> None:
    named = action.get("g1_named_targets")
    if not isinstance(named, dict):
        named = action.get("named_joint_targets")
    if not isinstance(named, dict):
        named = action.get("joint_target_map")
    if not isinstance(named, dict):
        return

    updated = {str(joint): float(value) for joint, value in named.items()}
    for joint in joint_names_to_neutral:
        updated[joint] = float(G1_NEUTRAL_JOINTS.get(joint, 0.0))

    joint_names = _g1_retarget_joint_order()
    joint_targets = [round(float(updated.get(joint, G1_NEUTRAL_JOINTS.get(joint, 0.0))), 6) for joint in joint_names]
    joint_groups = {
        group_name: [round(float(updated.get(joint, G1_NEUTRAL_JOINTS.get(joint, 0.0))), 6) for joint in G1_JOINT_GROUPS[group_name]]
        for group_name in G1_GROUP_ORDER
    }
    action["joint_names"] = joint_names
    action["joint_schema"] = g1_schema_payload()
    action["joint_order"] = list(joint_names)
    action["joint_order_source"] = "g1_schema_named"
    action["joint_targets"] = joint_targets
    action["joint_positions"] = list(joint_targets)
    action["joint_target_map"] = {joint: joint_targets[index] for index, joint in enumerate(joint_names)}
    action["named_joint_targets"] = dict(action["joint_target_map"])
    action["g1_named_targets"] = dict(action["joint_target_map"])
    action["joint_groups"] = joint_groups
    for group_name, values in joint_groups.items():
        action[group_name] = values


def _pose_sequence_from_motion(
    motion: Any,
    *,
    enabled: bool,
    max_pose_frames: int,
    pose_scale: float,
    pose_calibration: str = "none",
    lower_body_mode: str = "auto",
    lower_body_scale: float = 1.0,
    inactive_arm_deadzone: float = 0.14,
    limb_min_visibility: float = 0.42,
    prefer_pose_joints: bool = False,
    constrain_live_g1_targets: bool = False,
) -> List[Dict[str, Any]]:
    if not enabled:
        return []

    trace = _load_motion_trace(motion)
    frames = trace.get("frames") if isinstance(trace, dict) else None
    if not isinstance(frames, list) or not frames:
        return []

    max_pose_frames = max(1, int(max_pose_frames or 1))
    stride = max(1, len(frames) // max_pose_frames)
    sampled = frames[::stride][:max_pose_frames]
    return [
        _pose_frame_from_trace_frame(
            frame,
            index=index,
            pose_scale=pose_scale,
            pose_calibration=pose_calibration,
            lower_body_mode=lower_body_mode,
            lower_body_scale=lower_body_scale,
            inactive_arm_deadzone=inactive_arm_deadzone,
            limb_min_visibility=limb_min_visibility,
            prefer_pose_joints=prefer_pose_joints,
            constrain_live_g1_targets=constrain_live_g1_targets,
        )
        for index, frame in enumerate(sampled)
        if isinstance(frame, dict)
    ]


def _numeric_range(values: List[float]) -> Dict[str, Any]:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if not finite:
        return {"count": 0, "min": None, "max": None, "abs_max": None}
    return {
        "count": len(finite),
        "min": round(min(finite), 6),
        "max": round(max(finite), 6),
        "abs_max": round(max(abs(value) for value in finite), 6),
    }


def _pose_sequence_diagnostics(pose_sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
    rotations: List[float] = []
    raw_rotations: List[float] = []
    joint_counts: List[int] = []
    timestamps: List[float] = []
    root_translation_values: List[float] = []
    calibration_profiles: set[str] = set()
    lower_body_locked_count = 0
    arm_activity_left: List[float] = []
    arm_activity_right: List[float] = []
    g1_mapping_clipped: List[float] = []
    g1_mapping_input_abs: List[float] = []
    g1_mapping_output_abs: List[float] = []
    g1_mapping_top_clipped: Dict[str, Dict[str, float]] = {}
    for frame in pose_sequence:
        if not isinstance(frame, dict):
            continue
        profile = _text(frame.get("pose_calibration"))
        if profile:
            calibration_profiles.add(profile)
        joints = frame.get("joints")
        if isinstance(joints, dict):
            joint_counts.append(len(joints))
            for rotation in joints.values():
                if isinstance(rotation, dict):
                    rotations.extend(
                        float(rotation.get(axis, 0.0))
                        for axis in ("x", "y", "z")
                    )
                elif isinstance(rotation, (list, tuple)):
                    rotations.extend(float(value) for value in list(rotation)[:3])
        raw_joints = frame.get("raw_joints")
        if isinstance(raw_joints, dict):
            for rotation in raw_joints.values():
                if isinstance(rotation, dict):
                    raw_rotations.extend(
                        float(rotation.get(axis, 0.0))
                        for axis in ("x", "y", "z")
                    )
                elif isinstance(rotation, (list, tuple)):
                    raw_rotations.extend(float(value) for value in list(rotation)[:3])
        try:
            timestamps.append(float(frame.get("timestamp_sec")))
        except Exception:
            pass
        root_translation = frame.get("root_translation") or frame.get("rootTranslation")
        if isinstance(root_translation, (list, tuple)):
            for value in list(root_translation)[:3]:
                try:
                    root_translation_values.append(float(value))
                except Exception:
                    pass
        limb_filter = frame.get("limb_filter")
        if isinstance(limb_filter, dict):
            if bool(limb_filter.get("lower_body_locked")):
                lower_body_locked_count += 1
            try:
                arm_activity_left.append(float(limb_filter.get("left_arm_activity")))
            except Exception:
                pass
            try:
                arm_activity_right.append(float(limb_filter.get("right_arm_activity")))
            except Exception:
                pass
            mapping = limb_filter.get("g1_mapping")
            if isinstance(mapping, dict):
                try:
                    g1_mapping_clipped.append(float(mapping.get("clipped", 0)))
                except Exception:
                    pass
                input_range = mapping.get("input_range")
                if isinstance(input_range, dict) and input_range.get("abs_max") is not None:
                    try:
                        g1_mapping_input_abs.append(float(input_range.get("abs_max")))
                    except Exception:
                        pass
                output_range = mapping.get("output_range")
                if isinstance(output_range, dict) and output_range.get("abs_max") is not None:
                    try:
                        g1_mapping_output_abs.append(float(output_range.get("abs_max")))
                    except Exception:
                        pass
                top_clipped = mapping.get("top_clipped")
                if isinstance(top_clipped, dict):
                    for joint, values in top_clipped.items():
                        if isinstance(values, dict):
                            g1_mapping_top_clipped[str(joint)] = values

    return {
        "pose_frame_count": len(pose_sequence),
        "pose_joint_count_min": min(joint_counts) if joint_counts else 0,
        "pose_joint_count_max": max(joint_counts) if joint_counts else 0,
        "pose_rotation_deg": _numeric_range(rotations),
        "raw_pose_rotation_deg": _numeric_range(raw_rotations),
        "pose_calibration_profiles": sorted(calibration_profiles),
        "lower_body_locked_frames": lower_body_locked_count,
        "left_arm_activity": _numeric_range(arm_activity_left),
        "right_arm_activity": _numeric_range(arm_activity_right),
        "timestamp_sec": _numeric_range(timestamps),
        "root_translation": _numeric_range(root_translation_values),
        "g1_mapping_clipped": _numeric_range(g1_mapping_clipped),
        "g1_mapping_input_abs": _numeric_range(g1_mapping_input_abs),
        "g1_mapping_output_abs": _numeric_range(g1_mapping_output_abs),
        "g1_mapping_top_clipped": dict(list(g1_mapping_top_clipped.items())[:8]),
    }


def _debug_motion_retarget_arm_targets(
    action: Dict[str, Any],
    pose_sequence: List[Dict[str, Any]],
) -> Dict[str, Any]:
    named = action.get("g1_named_targets")
    if not isinstance(named, dict):
        named = action.get("named_joint_targets")
    if not isinstance(named, dict):
        named = action.get("joint_target_map")
    if not isinstance(named, dict):
        named = {}

    def named_value(joint_name: str) -> Any:
        value = named.get(joint_name)
        try:
            return round(float(value), 6)
        except Exception:
            return None

    latest_frame = pose_sequence[-1] if pose_sequence and isinstance(pose_sequence[-1], dict) else {}
    joints = latest_frame.get("joints") if isinstance(latest_frame.get("joints"), dict) else {}
    left_arm = joints.get("LeftArm")
    right_arm = joints.get("RightArm")
    limb_filter = latest_frame.get("limb_filter") if isinstance(latest_frame.get("limb_filter"), dict) else {}

    def joint_line(value: Any) -> str:
        if not isinstance(value, list):
            return "missing"
        try:
            return "[" + ", ".join(f"{float(item):.3f}" for item in value[:3]) + "]"
        except Exception:
            return str(value)

    return {
        "skill": str(action.get("skill", "")),
        "left_shoulder_pitch_joint": named_value("left_shoulder_pitch_joint"),
        "right_shoulder_pitch_joint": named_value("right_shoulder_pitch_joint"),
        "left_shoulder_roll_joint": named_value("left_shoulder_roll_joint"),
        "right_shoulder_roll_joint": named_value("right_shoulder_roll_joint"),
        "left_shoulder_yaw_joint": named_value("left_shoulder_yaw_joint"),
        "right_shoulder_yaw_joint": named_value("right_shoulder_yaw_joint"),
        "left_elbow_pitch_joint": named_value("left_elbow_pitch_joint"),
        "right_elbow_pitch_joint": named_value("right_elbow_pitch_joint"),
        "left_elbow_roll_joint": named_value("left_elbow_roll_joint"),
        "right_elbow_roll_joint": named_value("right_elbow_roll_joint"),
        "arm_filter": (
            f"L_act={float(limb_filter.get('left_arm_activity', 0.0)):.4f} "
            f"R_act={float(limb_filter.get('right_arm_activity', 0.0)):.4f} "
            f"L_inactive={bool(limb_filter.get('left_arm_inactive', False))} "
            f"R_inactive={bool(limb_filter.get('right_arm_inactive', False))}"
        ),
        "pose_arm_joints_deg": f"LeftArm={joint_line(left_arm)} RightArm={joint_line(right_arm)}",
    }


def _debug_motion_retarget_lower_body_targets(
    action: Dict[str, Any],
    pose_sequence: List[Dict[str, Any]],
) -> Dict[str, Any]:
    named = action.get("g1_named_targets")
    if not isinstance(named, dict):
        named = action.get("named_joint_targets")
    if not isinstance(named, dict):
        named = action.get("joint_target_map")
    if not isinstance(named, dict):
        named = {}

    def named_value(joint_name: str) -> Any:
        value = named.get(joint_name)
        try:
            return round(float(value), 6)
        except Exception:
            return None

    latest_frame = pose_sequence[-1] if pose_sequence and isinstance(pose_sequence[-1], dict) else {}
    joints = latest_frame.get("joints") if isinstance(latest_frame.get("joints"), dict) else {}
    left_leg = joints.get("LeftUpLeg") or joints.get("LeftLeg")
    right_leg = joints.get("RightUpLeg") or joints.get("RightLeg")
    left_knee = joints.get("LeftKnee")
    right_knee = joints.get("RightKnee")
    limb_filter = latest_frame.get("limb_filter") if isinstance(latest_frame.get("limb_filter"), dict) else {}

    def joint_line(value: Any) -> str:
        if not isinstance(value, list):
            return "missing"
        try:
            return "[" + ", ".join(f"{float(item):.3f}" for item in value[:3]) + "]"
        except Exception:
            return str(value)

    return {
        "left_hip_pitch_joint": named_value("left_hip_pitch_joint"),
        "left_knee_joint": named_value("left_knee_joint"),
        "left_ankle_pitch_joint": named_value("left_ankle_pitch_joint"),
        "right_hip_pitch_joint": named_value("right_hip_pitch_joint"),
        "right_knee_joint": named_value("right_knee_joint"),
        "right_ankle_pitch_joint": named_value("right_ankle_pitch_joint"),
        "lower_body_filter": (
            f"locked={bool(limb_filter.get('lower_body_locked', False))} "
            f"mode={str(limb_filter.get('lower_body_mode', ''))}"
        ),
        "pose_leg_joints_deg": (
            f"LeftLeg={joint_line(left_leg)} LeftKnee={joint_line(left_knee)} "
            f"RightLeg={joint_line(right_leg)} RightKnee={joint_line(right_knee)}"
        ),
    }


def _pose_frame_hip_center(frame: Dict[str, Any]) -> tuple[float, float, float] | None:
    landmarks = frame.get("landmarks") if isinstance(frame.get("landmarks"), dict) else {}
    return _midpoint3(_point3(landmarks, "LEFT_HIP"), _point3(landmarks, "RIGHT_HIP"))


def _pose_frame_pelvis_height(frame: Dict[str, Any]) -> float | None:
    """Measure pelvis height above the lowest foot in metric pose space."""
    landmarks = frame.get("retarget_landmarks") if isinstance(frame.get("retarget_landmarks"), dict) else {}
    if not landmarks:
        landmarks = frame.get("world_landmarks") if isinstance(frame.get("world_landmarks"), dict) else {}
    hip = _midpoint3(_point3(landmarks, "LEFT_HIP"), _point3(landmarks, "RIGHT_HIP"))
    feet = [
        point
        for name in ("LEFT_ANKLE", "RIGHT_ANKLE", "LEFT_HEEL", "RIGHT_HEEL", "LEFT_FOOT_INDEX", "RIGHT_FOOT_INDEX")
        for point in [_point3(landmarks, name)]
        if point is not None
    ]
    if hip is None or not feet:
        return None
    axes = _g1_pelvis_axes_from_landmarks(landmarks)
    if axes is None:
        return None
    return min(abs(_dot3(_vec3(point, hip), axes[1])) for point in feet)


def _pose_frame_pelvis_foot_offset(frame: Dict[str, Any]) -> tuple[float, float, float] | None:
    """Return pelvis relative to feet as (forward, lateral, vertical)."""
    landmarks = frame.get("retarget_landmarks") if isinstance(frame.get("retarget_landmarks"), dict) else {}
    if not landmarks:
        landmarks = frame.get("world_landmarks") if isinstance(frame.get("world_landmarks"), dict) else {}
    hip = _midpoint3(_point3(landmarks, "LEFT_HIP"), _point3(landmarks, "RIGHT_HIP"))
    left_foot = _midpoint3(_point3(landmarks, "LEFT_ANKLE"), _point3(landmarks, "LEFT_HEEL"))
    right_foot = _midpoint3(_point3(landmarks, "RIGHT_ANKLE"), _point3(landmarks, "RIGHT_HEEL"))
    foot = _midpoint3(left_foot, right_foot)
    axes = _g1_pelvis_axes_from_landmarks(landmarks)
    if hip is None or foot is None or axes is None:
        return None
    offset = _vec3(foot, hip)
    return (
        _dot3(offset, axes[2]),
        _dot3(offset, axes[0]),
        _dot3(offset, axes[1]),
    )


def _root_translation_from_centers(
    base_center: tuple[float, float, float],
    target_center: tuple[float, float, float],
    *,
    lateral_scale: float,
    vertical_scale: float,
    depth_scale: float,
    image_x_depth_scale: float,
    max_lateral: float,
    max_vertical: float,
    max_depth: float,
    mirror_image_x: bool = False,
) -> tuple[List[float], Dict[str, float]]:
    delta_x = target_center[0] - base_center[0]
    if mirror_image_x:
        delta_x = -delta_x
    delta_y = target_center[1] - base_center[1]
    delta_z = target_center[2] - base_center[2]
    depth_from_z = -delta_z * depth_scale
    depth_from_image_x = delta_x * image_x_depth_scale
    translation = [
        round(_clamp(depth_from_z + depth_from_image_x, -max_depth, max_depth), 6),
        round(_clamp(delta_x * lateral_scale, -max_lateral, max_lateral), 6),
        round(_clamp(-delta_y * vertical_scale, -max_vertical, max_vertical), 6),
    ]
    return translation, {
        "image_x": round(delta_x, 6),
        "image_x_mirrored": bool(mirror_image_x),
        "image_y": round(delta_y, 6),
        "image_z": round(delta_z, 6),
        "depth_from_image_x": round(depth_from_image_x, 6),
        "depth_from_image_z": round(depth_from_z, 6),
    }


def _root_pitch_from_pose_frame(
    frame: Dict[str, Any],
    *,
    pitch_scale: float,
    max_pitch_rad: float,
) -> tuple[List[float], Dict[str, float]] | None:
    landmarks = frame.get("retarget_landmarks") if isinstance(frame.get("retarget_landmarks"), dict) else {}
    if not landmarks:
        landmarks = frame.get("world_landmarks") if isinstance(frame.get("world_landmarks"), dict) else {}
    if not landmarks:
        landmarks = frame.get("landmarks") if isinstance(frame.get("landmarks"), dict) else {}
    if not landmarks:
        return None

    left_shoulder = _point3(landmarks, "LEFT_SHOULDER")
    right_shoulder = _point3(landmarks, "RIGHT_SHOULDER")
    left_hip = _point3(landmarks, "LEFT_HIP")
    right_hip = _point3(landmarks, "RIGHT_HIP")
    shoulder_center = _midpoint3(left_shoulder, right_shoulder)
    hip_center = _midpoint3(left_hip, right_hip)
    if shoulder_center is None or hip_center is None:
        return None

    pelvis_axes = _g1_pelvis_axes_from_landmarks(landmarks)
    if pelvis_axes is None:
        return None
    torso = _normalize3(_vec3(hip_center, shoulder_center))
    vertical = max(1.0e-5, _dot3(torso, pelvis_axes[1]))
    forward_sign = _to_float(os.getenv("VLAGRAPH_MOTION_TORSO_FORWARD_SIGN"), -1.0)
    forward = _dot3(torso, pelvis_axes[2]) * forward_sign
    lateral = _dot3(torso, pelvis_axes[0])
    raw_pitch = math.atan2(forward, vertical)
    pitch = _clamp(raw_pitch * max(0.0, float(pitch_scale)), -abs(float(max_pitch_rad)), abs(float(max_pitch_rad)))
    roll_scale = max(0.0, _to_float(os.getenv("VLAGRAPH_MOTION_TORSO_ROLL_SCALE"), pitch_scale))
    roll = _clamp(math.atan2(lateral, vertical) * roll_scale, -math.radians(20.0), math.radians(20.0))
    rotation = [round(roll, 6), round(pitch, 6), 0.0]
    return rotation, {
        "torso_forward": round(forward, 6),
        "torso_lateral": round(lateral, 6),
        "torso_vertical": round(vertical, 6),
        "torso_rotation_source": "mediapipe_world_pelvis_relative",
        "torso_root_roll_rad": round(roll, 6),
        "torso_root_pitch_rad": round(pitch, 6),
    }


def _apply_root_rotation_to_waist_targets(frame: Dict[str, Any], rotation: List[float]) -> None:
    if not _to_bool(os.getenv("VLAGRAPH_MOTION_ROOT_ROTATION_TO_WAIST"), True):
        return
    targets = frame.get("g1_named_targets")
    if not isinstance(targets, dict):
        return
    roll = float(rotation[0]) if len(rotation) > 0 else 0.0
    pitch = float(rotation[1]) if len(rotation) > 1 else 0.0
    roll_scale = _to_float(os.getenv("VLAGRAPH_MOTION_ROOT_ROLL_TO_WAIST_SCALE"), 0.65)
    pitch_scale = _to_float(os.getenv("VLAGRAPH_MOTION_ROOT_PITCH_TO_WAIST_SCALE"), 0.90)
    pitch_sign = _to_float(os.getenv("VLAGRAPH_MOTION_WAIST_PITCH_SIGN"), 1.0)
    roll_sign = _to_float(os.getenv("VLAGRAPH_MOTION_WAIST_ROLL_SIGN"), 1.0)
    if abs(roll) > 1.0e-5:
        targets.setdefault(
            "waist_roll_joint",
            _clamp_rad(roll * roll_scale * roll_sign, -0.35, 0.35),
        )
    if abs(pitch) > 1.0e-5:
        targets.setdefault(
            "waist_pitch_joint",
            _clamp_rad(pitch * pitch_scale * pitch_sign, -0.55, 0.55),
        )
        # Keep torso_joint as yaw-only compatibility alias. Do not overload it
        # with pitch, because the Isaac G1 schema maps it to waist_yaw_joint.


def _smooth_root_translation_sequence(
    values: List[List[float]],
    *,
    window: int,
) -> None:
    """Apply an offline centred filter without adding playback latency."""
    if len(values) < 3 or window <= 1:
        return
    radius = max(1, min(15, int(window) // 2))
    source = [list(value[:3]) for value in values]
    for index, value in enumerate(values):
        start = max(0, index - radius)
        end = min(len(source), index + radius + 1)
        count = float(max(1, end - start))
        for axis in (0, 2):
            value[axis] = round(sum(source[item][axis] for item in range(start, end)) / count, 6)


def _apply_in_place_pelvis_motion_to_leg_targets(
    frame: Dict[str, Any],
    translation: List[float],
    delta: Dict[str, float],
) -> None:
    if not _to_bool(os.getenv("VLAGRAPH_MOTION_IN_PLACE_PELVIS_TO_LEGS"), False):
        return
    targets = frame.get("g1_named_targets")
    if not isinstance(targets, dict):
        return

    forward = float(translation[0] if len(translation) > 0 else 0.0)
    down = max(0.0, -float(translation[2] if len(translation) > 2 else 0.0))
    hip_delta, knee_delta, ankle_delta = _foot_locked_sagittal_leg_ik_delta(
        forward=forward,
        down=down,
        hip_to_ankle_height=_to_float(os.getenv("VLAGRAPH_MOTION_G1_HIP_TO_ANKLE_HEIGHT"), 0.52),
        thigh_length=_to_float(os.getenv("VLAGRAPH_MOTION_G1_THIGH_LENGTH"), 0.27),
        shin_length=_to_float(os.getenv("VLAGRAPH_MOTION_G1_SHIN_LENGTH"), 0.27),
    )
    for side in ("left", "right"):
        hip = f"{side}_hip_pitch_joint"
        knee = f"{side}_knee_joint"
        ankle = f"{side}_ankle_pitch_joint"
        targets[hip] = _clamp_rad(float(targets.get(hip, G1_NEUTRAL_JOINTS[hip])) + hip_delta, -0.55, 0.32)
        targets[knee] = _clamp_rad(float(targets.get(knee, G1_NEUTRAL_JOINTS[knee])) + knee_delta, 0.10, 0.68)
        targets[ankle] = _clamp_rad(float(targets.get(ankle, G1_NEUTRAL_JOINTS[ankle])) + ankle_delta, -0.45, 0.24)
    frame["in_place_pelvis_leg_compensation"] = {
        "down": round(down, 6),
        "forward": round(forward, 6),
        "hip_delta": round(hip_delta, 6),
        "knee_delta": round(knee_delta, 6),
        "ankle_delta": round(ankle_delta, 6),
        "solver": "foot_locked_sagittal_ik",
    }


def _foot_locked_sagittal_leg_ik_delta(
    *,
    forward: float,
    down: float,
    hip_to_ankle_height: float,
    thigh_length: float,
    shin_length: float,
) -> tuple[float, float, float]:
    thigh = max(0.12, float(thigh_length))
    shin = max(0.12, float(shin_length))
    base_height = _clamp(float(hip_to_ankle_height), 0.20, thigh + shin - 1.0e-3)
    target_forward = _clamp(float(forward), -0.20, 0.20)
    target_height = _clamp(base_height - float(down), 0.16, thigh + shin - 1.0e-3)

    def solve(x: float, z: float) -> tuple[float, float, float]:
        distance = _clamp(math.sqrt(x * x + z * z), 0.06, thigh + shin - 1.0e-3)
        knee_inside = _clamp((thigh * thigh + shin * shin - distance * distance) / (2.0 * thigh * shin), -1.0, 1.0)
        knee = max(0.0, math.pi - math.acos(knee_inside))
        hip_inside = _clamp((thigh * thigh + distance * distance - shin * shin) / (2.0 * thigh * distance), -1.0, 1.0)
        hip = math.atan2(x, z) - math.acos(hip_inside)
        ankle = -(hip + knee)
        return hip, knee, ankle

    neutral_hip, neutral_knee, neutral_ankle = solve(0.0, base_height)
    target_hip, target_knee, target_ankle = solve(target_forward, target_height)
    strength = _clamp(_to_float(os.getenv("VLAGRAPH_MOTION_FOOT_LOCK_IK_STRENGTH"), 0.85), 0.0, 1.5)
    return (
        (target_hip - neutral_hip) * strength,
        (target_knee - neutral_knee) * strength,
        (target_ankle - neutral_ankle) * strength,
    )


def _detect_root_motion_mode(
    pose_sequence: List[Dict[str, Any]] | None,
    *,
    requested_mode: str = "auto",
    text: str = "",
) -> tuple[str, Dict[str, Any]]:
    mode = _text(requested_mode).lower().replace("-", "_")
    if mode in {"inplace", "in_place", "fixed_feet", "foot_lock", "feet_locked"}:
        return "in_place", {"requested": requested_mode, "reason": "manual_in_place"}
    if mode in {"locomotion", "root_translation", "walk", "walking"}:
        return "locomotion", {"requested": requested_mode, "reason": "manual_locomotion"}

    if any(token in text for token in ("walk", "walking", "run", "forward", "backward", "전진", "후진", "걷", "달리")):
        return "locomotion", {"requested": requested_mode, "reason": "prompt_locomotion"}

    frames = [frame for frame in (pose_sequence or []) if isinstance(frame, dict)]
    if len(frames) < 3:
        return "in_place", {"requested": requested_mode, "reason": "insufficient_pose_frames"}

    def center(frame: Dict[str, Any], left: str, right: str) -> tuple[float, float, float] | None:
        landmarks = frame.get("landmarks") if isinstance(frame.get("landmarks"), dict) else {}
        return _midpoint3(_point3(landmarks, left), _point3(landmarks, right))

    hip_centers = [value for value in (center(frame, "LEFT_HIP", "RIGHT_HIP") for frame in frames) if value is not None]
    ankle_centers = [value for value in (center(frame, "LEFT_ANKLE", "RIGHT_ANKLE") for frame in frames) if value is not None]
    if len(hip_centers) < 3 or len(ankle_centers) < 3:
        return "in_place", {"requested": requested_mode, "reason": "missing_hip_or_ankle_centers"}

    def planar_span(points: List[tuple[float, float, float]]) -> float:
        xs = [point[0] for point in points]
        zs = [point[2] for point in points]
        return max(max(xs) - min(xs), max(zs) - min(zs))

    hip_span = planar_span(hip_centers)
    ankle_span = planar_span(ankle_centers)
    hip_widths = []
    for frame in frames:
        landmarks = frame.get("landmarks") if isinstance(frame.get("landmarks"), dict) else {}
        hip_width = _distance3(_point3(landmarks, "LEFT_HIP"), _point3(landmarks, "RIGHT_HIP"))
        if hip_width > 1.0e-5:
            hip_widths.append(hip_width)
    body_scale = sum(hip_widths) / len(hip_widths) if hip_widths else 0.15
    locomotion_threshold = max(0.025, body_scale * 0.35, hip_span * 0.45)
    detected = "locomotion" if ankle_span >= locomotion_threshold else "in_place"
    return detected, {
        "requested": requested_mode or "auto",
        "reason": "feet_move_with_body" if detected == "locomotion" else "feet_stable_pelvis_motion",
        "hip_planar_span": round(hip_span, 6),
        "ankle_planar_span": round(ankle_span, 6),
        "body_scale": round(body_scale, 6),
        "locomotion_threshold": round(locomotion_threshold, 6),
    }


def _average_centers(centers: List[tuple[float, float, float]]) -> tuple[float, float, float] | None:
    if not centers:
        return None
    count = float(len(centers))
    return (
        sum(center[0] for center in centers) / count,
        sum(center[1] for center in centers) / count,
        sum(center[2] for center in centers) / count,
    )


def _root_translation_from_pose_sequence(
    pose_sequence: List[Dict[str, Any]] | None,
    *,
    frame_indices: List[int] | None,
    lateral_scale: float,
    vertical_scale: float,
    depth_scale: float,
    image_x_depth_scale: float,
    max_lateral: float,
    max_vertical: float,
    max_depth: float,
    mirror_image_x: bool = False,
) -> Dict[str, Any]:
    if not pose_sequence:
        return {}

    valid_centers = [
        center
        for center in (_pose_frame_hip_center(frame) for frame in pose_sequence[:5])
        if center is not None
    ]
    base_center = _average_centers(valid_centers)
    if base_center is None:
        return {}
    base_pelvis_heights = [
        height
        for height in (_pose_frame_pelvis_height(frame) for frame in pose_sequence[:5])
        if height is not None
    ]
    base_pelvis_height = (
        sum(base_pelvis_heights) / len(base_pelvis_heights)
        if base_pelvis_heights
        else None
    )
    base_offsets = [
        offset
        for offset in (_pose_frame_pelvis_foot_offset(frame) for frame in pose_sequence[:5])
        if offset is not None
    ]
    base_pelvis_foot_offset = _average_centers(base_offsets)

    selected_centers: List[tuple[float, float, float]] = []
    for raw_index in frame_indices or []:
        try:
            index = int(raw_index)
        except Exception:
            continue
        if 0 <= index < len(pose_sequence):
            center = _pose_frame_hip_center(pose_sequence[index])
            if center is not None:
                selected_centers.append(center)

    if not selected_centers:
        center = _pose_frame_hip_center(pose_sequence[-1])
        if center is not None:
            selected_centers.append(center)

    target_center = _average_centers(selected_centers)
    if target_center is None:
        return {}

    translation, delta = _root_translation_from_centers(
        base_center,
        target_center,
        lateral_scale=lateral_scale,
        vertical_scale=vertical_scale,
        depth_scale=depth_scale,
        image_x_depth_scale=image_x_depth_scale,
        mirror_image_x=mirror_image_x,
        max_lateral=max_lateral,
        max_vertical=max_vertical,
        max_depth=max_depth,
    )
    if max(abs(value) for value in translation) < 1.0e-5:
        return {}

    return {
        "root_translation": translation,
        "rootTranslation": translation,
        "root_translation_mode": "offset_from_initial",
        "rootTranslationMode": "offset_from_initial",
        "root_motion_source": "hip_center",
        "root_motion_delta": delta,
    }


def _annotate_pose_sequence_root_translation(
    pose_sequence: List[Dict[str, Any]] | None,
    *,
    lateral_scale: float,
    vertical_scale: float,
    depth_scale: float,
    image_x_depth_scale: float,
    max_lateral: float,
    max_vertical: float,
    max_depth: float,
    mirror_image_x: bool = False,
    root_pitch_enabled: bool = True,
    root_pitch_scale: float = 1.15,
    root_max_pitch_rad: float = math.radians(10.0),
    in_place_pelvis_to_legs: bool = False,
) -> Dict[str, Any]:
    if not pose_sequence:
        return {}

    valid_centers = [
        center
        for center in (_pose_frame_hip_center(frame) for frame in pose_sequence[:5])
        if center is not None
    ]
    base_center = _average_centers(valid_centers)
    if base_center is None:
        return {}
    base_pelvis_heights = [
        height
        for height in (_pose_frame_pelvis_height(frame) for frame in pose_sequence[:5])
        if height is not None
    ]
    base_pelvis_height = (
        sum(base_pelvis_heights) / len(base_pelvis_heights)
        if base_pelvis_heights
        else None
    )
    base_offsets = [
        offset
        for offset in (_pose_frame_pelvis_foot_offset(frame) for frame in pose_sequence[:5])
        if offset is not None
    ]
    base_pelvis_foot_offset = _average_centers(base_offsets)

    translations: List[List[float]] = []
    root_translations: List[List[float]] = []
    rotations: List[List[float]] = []
    nonzero_count = 0
    root_nonzero_count = 0
    rotation_nonzero_count = 0
    for frame in pose_sequence:
        if not isinstance(frame, dict):
            translations.append([0.0, 0.0, 0.0])
            root_translations.append([0.0, 0.0, 0.0])
            rotations.append([0.0, 0.0, 0.0])
            continue
        center = _pose_frame_hip_center(frame)
        if center is None:
            translation = [0.0, 0.0, 0.0]
            delta = {"image_x": 0.0, "image_y": 0.0, "image_z": 0.0}
        else:
            translation, delta = _root_translation_from_centers(
                base_center,
                center,
                lateral_scale=lateral_scale,
                vertical_scale=vertical_scale,
                depth_scale=depth_scale,
                image_x_depth_scale=image_x_depth_scale,
                mirror_image_x=mirror_image_x,
                max_lateral=max_lateral,
                max_vertical=max_vertical,
                max_depth=max_depth,
            )
            current_pelvis_height = _pose_frame_pelvis_height(frame)
            if base_pelvis_height is not None and current_pelvis_height is not None:
                pelvis_height_scale = max(0.0, _to_float(os.getenv("VLAGRAPH_MOTION_PELVIS_HEIGHT_SCALE"), 1.0))
                pelvis_vertical = (current_pelvis_height - base_pelvis_height) * pelvis_height_scale
                translation[2] = round(_clamp(pelvis_vertical, -max_vertical, max_vertical), 6)
                delta["pelvis_height"] = round(current_pelvis_height, 6)
                delta["pelvis_height_delta"] = round(current_pelvis_height - base_pelvis_height, 6)
            current_offset = _pose_frame_pelvis_foot_offset(frame)
            if base_pelvis_foot_offset is not None and current_offset is not None:
                forward_scale = _to_float(os.getenv("VLAGRAPH_MOTION_PELVIS_FORWARD_SCALE"), 1.0)
                forward_sign = _to_float(os.getenv("VLAGRAPH_MOTION_PELVIS_FORWARD_SIGN"), 1.0)
                pelvis_forward = (current_offset[0] - base_pelvis_foot_offset[0]) * forward_scale * forward_sign
                translation[0] = round(_clamp(pelvis_forward, -max_depth, max_depth), 6)
                delta["pelvis_forward"] = round(current_offset[0], 6)
                delta["pelvis_forward_delta"] = round(current_offset[0] - base_pelvis_foot_offset[0], 6)
        if max(abs(value) for value in translation) >= 1.0e-5:
            nonzero_count += 1
        translations.append(translation)
        root_translation = [translation[0], 0.0, translation[2]] if in_place_pelvis_to_legs else translation
        if max(abs(value) for value in root_translation) >= 1.0e-5:
            root_nonzero_count += 1
        root_translations.append(root_translation)
        frame["root_translation"] = root_translation
        frame["rootTranslation"] = root_translation
        frame["root_motion_delta"] = delta
        translation_mode = "foot_locked_pelvis_offset" if in_place_pelvis_to_legs else "offset_from_initial"
        frame["rootTranslationMode"] = translation_mode
        frame["root_translation_mode"] = translation_mode
        frame["root_motion_mode"] = "in_place" if in_place_pelvis_to_legs else "locomotion"
        frame["rootMotionMode"] = frame["root_motion_mode"]
        frame["foot_lock"] = bool(in_place_pelvis_to_legs)
        frame["footLock"] = bool(in_place_pelvis_to_legs)
        frame["pelvis_offset"] = translation
        frame["pelvisOffset"] = translation
        frame["root_position"] = root_translation
        frame["rootPosition"] = root_translation
        frame["hips_position"] = root_translation
        frame["hipsPosition"] = root_translation
        if in_place_pelvis_to_legs:
            _apply_in_place_pelvis_motion_to_leg_targets(frame, translation, delta)
        rotation_update = (
            _root_pitch_from_pose_frame(
                frame,
                pitch_scale=root_pitch_scale,
                max_pitch_rad=root_max_pitch_rad,
            )
            if root_pitch_enabled
            else None
        )
        if rotation_update is None:
            rotation = [0.0, 0.0, 0.0]
            rotation_delta = {"torso_forward": 0.0, "torso_vertical": 0.0, "torso_root_pitch_rad": 0.0}
        else:
            rotation, rotation_delta = rotation_update
        # In-place torso lean belongs to the waist joints. Applying the same
        # pitch to the articulation root rotates the entire robot, including
        # both planted feet, and breaks ground contact.
        applied_root_rotation = [0.0, 0.0, 0.0] if in_place_pelvis_to_legs else rotation
        if max(abs(value) for value in applied_root_rotation) >= 1.0e-5:
            rotation_nonzero_count += 1
        rotations.append(applied_root_rotation)
        frame["root_rotation"] = applied_root_rotation
        frame["rootRotation"] = applied_root_rotation
        frame["root_rotation_mode"] = "offset_from_initial"
        frame["rootRotationMode"] = "offset_from_initial"
        frame["root_rotation_source"] = "torso_forward_lean"
        frame["root_rotation_delta"] = rotation_delta
        _apply_root_rotation_to_waist_targets(frame, rotation)

    smoothing_window = max(1, _to_int(os.getenv("VLAGRAPH_MOTION_ROOT_SMOOTH_WINDOW"), 7))
    _smooth_root_translation_sequence(root_translations, window=smoothing_window)

    return {
        "root_translation_sequence": root_translations,
        "rootTranslationSequence": root_translations,
        "pelvis_offset_sequence": translations,
        "pelvisOffsetSequence": translations,
        "root_rotation_sequence": rotations,
        "rootRotationSequence": rotations,
        "root_translation_mode": "foot_locked_pelvis_offset" if in_place_pelvis_to_legs else "offset_from_initial",
        "rootTranslationMode": "foot_locked_pelvis_offset" if in_place_pelvis_to_legs else "offset_from_initial",
        "root_rotation_mode": "offset_from_initial",
        "rootRotationMode": "offset_from_initial",
        "root_motion_source": "hip_center_sequence",
        "root_translation_frame_count": len(translations),
        "root_translation_nonzero_frames": root_nonzero_count,
        "pelvis_offset_nonzero_frames": nonzero_count,
        "root_rotation_frame_count": len(rotations),
        "root_rotation_nonzero_frames": rotation_nonzero_count,
    }


def _strip_pose_sequence_joint_targets(pose_sequence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    stripped: List[Dict[str, Any]] = []
    target_keys = {
        "g1_named_targets",
        "g1NamedTargets",
        "joint_target_map",
        "jointTargetMap",
        "named_joint_targets",
        "namedJointTargets",
        "joint_targets",
        "jointTargets",
        "joint_positions",
        "jointPositions",
        "joint_groups",
        "jointGroups",
    }
    for frame in pose_sequence:
        if not isinstance(frame, dict):
            continue
        stripped.append({key: value for key, value in frame.items() if key not in target_keys})
    return stripped


def _stop_humanoid_action(*, prompt: str, reason: str) -> Dict[str, Any]:
    return {
        "type": "humanoid_motion_action",
        "command": "stop",
        "robot_type": "humanoid",
        "controller_mode": "locomotion",
        "skill": "stop",
        "gesture": "none",
        "move_x": 0.0,
        "move_z": 0.0,
        "turn_yaw": 0.0,
        "speed": 0.0,
        "duration_sec": 0.0,
        "animation": False,
        "stop": True,
        "terminate": True,
        "freeze": True,
        "prompt": prompt,
        "retarget_mode": "stop",
        "stop_reason": reason,
        "pose_sequence": [],
    }


def _action_from_skill(
    *,
    skill: str,
    prompt: str,
    motion: Any,
    speed: float,
    step_scale: float,
    turn_scale: float,
    duration_sec: float,
    pose_sequence: List[Dict[str, Any]] | None = None,
    emit_g1_joint_targets: bool = False,
    emit_g1_trajectory: bool = False,
    use_isaac_usd_ik: bool = False,
    root_motion_enabled: bool = True,
    joint_average_window: int = 5,
    joint_selection: str = "recent",
    root_translation_enabled: bool = False,
    root_lateral_scale: float = 1.5,
    root_vertical_scale: float = 0.9,
    root_depth_scale: float = 0.0,
    root_image_x_depth_scale: float = 0.0,
    root_mirror_image_x: bool = False,
    root_max_lateral: float = 0.18,
    root_max_vertical: float = 0.14,
    root_max_depth: float = 0.18,
    root_motion_mode: str = "in_place",
    root_pitch_enabled: bool = True,
    root_pitch_scale: float = 1.15,
    root_max_pitch_rad: float = math.radians(10.0),
    prefer_pose_joints: bool = False,
    constrain_joint_targets: bool = False,
) -> Dict[str, Any]:
    summary = _summary_from_motion(motion)
    labels = summary.get("heuristic_labels") if isinstance(summary, dict) else []
    labels_text = " ".join(str(item) for item in labels) if isinstance(labels, list) else ""
    text = _lower_words(skill, prompt, labels_text)
    detected_root_mode, root_mode_debug = _detect_root_motion_mode(
        pose_sequence,
        requested_mode=root_motion_mode,
        text=text,
    )
    effective_root_translation_enabled = bool(root_translation_enabled and detected_root_mode in {"in_place", "locomotion"})
    in_place_root_translation = bool(root_translation_enabled and detected_root_mode == "in_place")

    move_x = 0.0
    move_z = 0.0
    turn_yaw = 0.0
    gesture = "none"

    if root_motion_enabled and any(token in text for token in ("walk", "forward", "body_translation", "leg_motion", "앞", "전진")):
        move_z = step_scale

    if root_motion_enabled and any(token in text for token in ("back", "backward", "후진", "뒤")):
        move_z = -abs(step_scale)

    if root_motion_enabled and any(token in text for token in ("left", "turn_left", "왼쪽", "좌회전")):
        turn_yaw = -abs(turn_scale)

    if root_motion_enabled and any(token in text for token in ("right", "turn_right", "오른쪽", "우회전")):
        turn_yaw = abs(turn_scale)

    if any(token in text for token in ("stop", "idle", "정지", "멈춰")):
        move_x = 0.0
        move_z = 0.0
        turn_yaw = 0.0

    effective_duration_sec = max(0.0, float(duration_sec or 0.0))
    if emit_g1_trajectory and effective_duration_sec <= 0.0:
        effective_duration_sec = _motion_duration_sec(motion)
        if pose_sequence and len(pose_sequence) > 1:
            effective_duration_sec = max(effective_duration_sec, 2.0)

    action_pose_sequence = pose_sequence or []
    if use_isaac_usd_ik:
        action_pose_sequence = _strip_pose_sequence_joint_targets(action_pose_sequence)

    action = {
        "type": "humanoid_motion_action",
        "command": "apply_humanoid_motion",
        "robot_type": "humanoid",
        "controller_mode": "locomotion",
        "skill": skill or "unknown",
        "gesture": gesture,
        "move_x": move_x,
        "move_z": move_z,
        "turn_yaw": turn_yaw,
        "speed": speed,
        "duration_sec": effective_duration_sec,
        "animation": not (emit_g1_joint_targets or emit_g1_trajectory),
        "motion_summary": summary,
        "root_motion_mode": detected_root_mode,
        "root_motion_mode_debug": root_mode_debug,
        "trace_path": motion.get("trace_path") if isinstance(motion, dict) else "",
        "pose_sequence": action_pose_sequence if use_isaac_usd_ik else [] if (emit_g1_joint_targets or emit_g1_trajectory) else action_pose_sequence,
        "retarget_mode": "isaac_usd_ik" if use_isaac_usd_ik else "joint_trajectory" if emit_g1_trajectory else "joint_targets" if emit_g1_joint_targets else "pose_sequence",
        "use_isaac_usd_ik": bool(use_isaac_usd_ik),
        "prompt": prompt,
    }
    if (effective_root_translation_enabled or root_pitch_enabled) and pose_sequence:
        action.update(
            _annotate_pose_sequence_root_translation(
                pose_sequence,
                lateral_scale=0.0 if in_place_root_translation else root_lateral_scale if effective_root_translation_enabled else 0.0,
                vertical_scale=root_vertical_scale if effective_root_translation_enabled else 0.0,
                depth_scale=root_depth_scale if effective_root_translation_enabled else 0.0,
                image_x_depth_scale=root_image_x_depth_scale if effective_root_translation_enabled else 0.0,
                mirror_image_x=root_mirror_image_x,
                max_lateral=0.0 if in_place_root_translation else root_max_lateral if effective_root_translation_enabled else 0.0,
                max_vertical=root_max_vertical if effective_root_translation_enabled else 0.0,
                max_depth=root_max_depth if effective_root_translation_enabled else 0.0,
                root_pitch_enabled=root_pitch_enabled,
                root_pitch_scale=root_pitch_scale,
                root_max_pitch_rad=root_max_pitch_rad,
                in_place_pelvis_to_legs=in_place_root_translation,
            )
        )
    if emit_g1_trajectory and not use_isaac_usd_ik:
        action.update(
            _g1_joint_trajectory_from_pose_sequence(
                pose_sequence,
                duration_sec=effective_duration_sec,
                constrain_motion_learning=True,
            )
        )
    if (emit_g1_joint_targets or emit_g1_trajectory) and not use_isaac_usd_ik:
        action.update(
            _g1_joint_targets_from_pose_sequence(
                pose_sequence,
                average_window=joint_average_window,
                selection=joint_selection,
                constrain_motion_learning=emit_g1_trajectory or constrain_joint_targets,
                prefer_pose_joints=prefer_pose_joints,
            )
        )
        if effective_root_translation_enabled and not in_place_root_translation:
            action.update(
                _root_translation_from_pose_sequence(
                    pose_sequence,
                    frame_indices=action.get("retarget_frame_indices")
                    if isinstance(action.get("retarget_frame_indices"), list)
                    else [],
                    lateral_scale=root_lateral_scale,
                    vertical_scale=root_vertical_scale,
                    depth_scale=root_depth_scale,
                    image_x_depth_scale=root_image_x_depth_scale,
                    mirror_image_x=root_mirror_image_x,
                    max_lateral=root_max_lateral,
                    max_vertical=root_max_vertical,
                    max_depth=root_max_depth,
                )
            )
    return action


def exec_video_motion_input(node: Dict[str, Any], context: Dict[str, Any], edges: List[Dict[str, Any]]) -> Dict[str, Any]:
    props = node.get("data", {}) or {}
    video_path = _resolve_video_path(_text(props.get("videoPath")))
    label = _text(props.get("motionLabel"))
    prompt = _text(props.get("prompt"))

    return {
        "ok": bool(video_path),
        "type": "video_motion_input",
        "video": video_path,
        "video_path": video_path,
        "label": label,
        "prompt": prompt,
        "source": "video_motion_input",
    }


def exec_motion_extract(node: Dict[str, Any], context: Dict[str, Any], edges: List[Dict[str, Any]]) -> Dict[str, Any]:
    props = node.get("data", {}) or {}
    inputs = _incoming_values(node["id"], edges, context)

    video_path = _video_path_from_value(
        inputs.get("video")
        or inputs.get("video_path")
        or inputs.get("file")
        or props.get("videoPath")
    )
    if not video_path:
        raise ValueError("Motion Extract requires a video input or videoPath")
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Motion video not found: {video_path}")

    prompt = _text(inputs.get("prompt") or props.get("prompt"))
    label = _text(inputs.get("label") or props.get("motionLabel"))
    output_name = _text(props.get("outputName"))
    output_path = _trace_path_for_video(video_path, output_name)

    every_n_frames = max(1, _to_int(props.get("everyNFrames"), 2))
    max_frames = max(0, _to_int(props.get("maxFrames"), 0))
    min_visibility = _to_float(props.get("minVisibility"), 0.35)
    cache_key = {
        "video_path": video_path,
        "prompt": prompt,
        "label": label,
        "output_name": output_name,
        "every_n_frames": every_n_frames,
        "max_frames": max_frames,
        "min_visibility": round(min_visibility, 5),
    }
    cache_slot = f"_motion_extract_cache:{node.get('id', 'motion_extract')}"
    cached = context.get(cache_slot)
    if isinstance(cached, dict) and cached.get("key") == cache_key and isinstance(cached.get("result"), dict):
        result = copy.deepcopy(cached["result"])
        result["cached"] = True
        return result

    trace = extract_video_motion(
        video_path=video_path,
        output_path=output_path,
        label=label,
        prompt=prompt,
        every_n_frames=every_n_frames,
        max_frames=max_frames,
        min_visibility=min_visibility,
    )
    sampled_frames = int((trace.get("sampling") or {}).get("sampled_frames", 0) or 0)
    video_meta = trace.get("video") if isinstance(trace.get("video"), dict) else {}
    frame_count = int(video_meta.get("frame_count", 0) or 0)
    if sampled_frames < 12 and frame_count > 30 and min_visibility > 0.16:
        trace = extract_video_motion(
            video_path=video_path,
            output_path=output_path,
            label=label,
            prompt=prompt,
            every_n_frames=1,
            max_frames=max_frames,
            min_visibility=0.15,
        )
        trace.setdefault("sampling", {})
        if isinstance(trace["sampling"], dict):
            trace["sampling"]["auto_relaxed_visibility"] = True
            trace["sampling"]["requested_min_visibility"] = min_visibility
            trace["sampling"]["requested_every_n_frames"] = every_n_frames

    motion = trace if _to_bool(props.get("includeFrames"), False) else _compact_motion(trace, output_path)
    summary = trace.get("summary", {})
    skill = _text(summary.get("primary_skill")) or label or "unknown"
    isaaclab_bridge = _isaaclab_bridge_commands(output_path)
    dataset_path = str(
        Path(UPLOAD_DIR)
        / "humanoid_datasets"
        / f"{Path(output_path).stem}.humanoid.jsonl"
    )
    training_dataset = save_humanoid_training_dataset(trace, dataset_path)

    result = {
        "ok": True,
        "type": "motion_extract_result",
        "motion": motion,
        "pose_preview": _pose_preview_from_trace(trace),
        "trace_path": output_path,
        "trace_path_host": isaaclab_bridge["trace_path_host"],
        "dataset": training_dataset,
        "dataset_path": training_dataset["path"],
        "training_dataset": training_dataset,
        "humanoid_meaning": summary.get("meaning_ko", []),
        "skill": skill,
        "label": label,
        "prompt": prompt,
        "summary": summary,
        "sampled_frames": (trace.get("sampling") or {}).get("sampled_frames", 0),
        "video": trace.get("video", {}),
        "isaaclab_bridge": isaaclab_bridge,
        "train_command": isaaclab_bridge["powershell"],
    }
    context[cache_slot] = {"key": cache_key, "result": copy.deepcopy(result)}
    return result


def exec_motion_retarget(node: Dict[str, Any], context: Dict[str, Any], edges: List[Dict[str, Any]]) -> Dict[str, Any]:
    props = node.get("data", {}) or {}
    inputs = _incoming_values(node["id"], edges, context)

    motion = inputs.get("motion")
    if motion is None:
        motion = inputs.get("trace") or inputs.get("dataset") or props.get("motion")

    skill = _text(inputs.get("skill") or props.get("motionLabel") or props.get("skill"))
    if not skill:
        skill = _skill_from_motion(motion)

    prompt = _text(inputs.get("prompt") or props.get("prompt"))
    speed = _to_float(props.get("speed"), 1.0)
    step_scale = _to_float(props.get("stepScale"), 0.45)
    turn_scale = _to_float(props.get("turnScale"), 0.2)
    duration_sec = _to_float(props.get("durationSec"), 2.0)
    full_body = _to_bool(props.get("fullBodyRetarget"), True)
    max_pose_frames = _to_int(props.get("maxPoseFrames"), 40)
    pose_scale = _to_float(props.get("poseScale"), 1.0)
    target_embodiment = _text(props.get("targetEmbodiment") or props.get("embodimentTag")).upper()
    live_mocap_motion = _looks_like_live_mocap_motion(motion)
    if live_mocap_motion and not target_embodiment:
        target_embodiment = "REAL_G1"
    use_isaac_usd_ik = _to_bool(
        props.get("useIsaacUsdIk", props.get("useIsaacUSDIk")),
        False,
    )
    emit_g1_joint_targets = _to_bool(
        props.get("emitG1JointTargets", props.get("emitJointTargets")),
        target_embodiment in {"REAL_G1", "G1", "UNITREE_G1"},
    )
    emit_g1_trajectory = _to_bool(
        props.get("emitG1Trajectory", props.get("emitJointTrajectory")),
        False,
    )
    if live_mocap_motion:
        emit_g1_joint_targets = True
        emit_g1_trajectory = False
    if use_isaac_usd_ik:
        emit_g1_joint_targets = False
        emit_g1_trajectory = False
    pose_calibration = _pose_calibration_profile_name(
        props.get("poseCalibration") or props.get("poseAxisCalibration")
    )
    if pose_calibration == "auto":
        pose_calibration = (
            "kyle_usdskel_v1"
            if use_isaac_usd_ik or target_embodiment in {"KYLE", "KYLE_USDSKEL", "USD_SKEL", "USDSKEL"}
            else "none"
        )
    root_motion_enabled = _to_bool(
        props.get("rootMotionEnabled"),
        not emit_g1_joint_targets,
    )
    if live_mocap_motion and (emit_g1_joint_targets or use_isaac_usd_ik):
        root_motion_enabled = False
    root_translation_enabled = _to_bool(
        props.get("rootTranslationEnabled", props.get("rootPositionEnabled")),
        False,
    )
    joint_smoothing_default = 0.08 if emit_g1_joint_targets and live_mocap_motion else 0.0
    joint_smoothing = _to_float(props.get("jointSmoothing"), joint_smoothing_default)
    joint_max_delta_rad = _to_float(props.get("jointMaxDeltaRad"), 0.30 if emit_g1_joint_targets and live_mocap_motion else 0.0)
    joint_deadband_rad = _to_float(props.get("jointDeadbandRad"), 0.003 if emit_g1_joint_targets and live_mocap_motion else 0.0)
    joint_average_window = _to_int(props.get("jointAverageWindow"), 5)
    joint_selection = _text(props.get("jointSelection") or props.get("jointTargetSelection"))
    if not joint_selection:
        joint_selection = "recent" if live_mocap_motion else "balanced"
    stream_video_frames_requested = (
        _to_bool(props.get("streamVideoFrames", props.get("stream_video_frames")), False)
        and not live_mocap_motion
    )
    pose_sequence = _pose_sequence_from_motion(
        motion,
        enabled=full_body,
        max_pose_frames=max_pose_frames,
        pose_scale=pose_scale,
        pose_calibration=pose_calibration,
        lower_body_mode=_text(props.get("lowerBodyMode") or props.get("lower_body_mode") or "auto"),
        lower_body_scale=_to_float(
            props.get("lowerBodyScale"),
            1.0,
        ),
        inactive_arm_deadzone=_to_float(props.get("inactiveArmDeadzone"), 0.14),
        limb_min_visibility=_to_float(props.get("limbMinVisibility"), 0.42),
        prefer_pose_joints=stream_video_frames_requested,
        constrain_live_g1_targets=bool(live_mocap_motion and emit_g1_joint_targets),
    )
    motion_invalid = isinstance(motion, dict) and bool(motion.get("invalid_current_frame"))
    if live_mocap_motion and (motion_invalid or not pose_sequence):
        reset_motion_retarget_runtime_state([str(node.get("id", "motion_retarget"))])
        reason = "invalid_current_rgbd_pose" if motion_invalid else "empty_live_rgbd_pose"
        action = _stop_humanoid_action(prompt=prompt, reason=reason)
        diagnostics = {
            "reason": reason,
            "pose_scale": pose_scale,
            "pose_calibration": pose_calibration,
            "target_embodiment": target_embodiment,
            "retarget_mode": "stop",
            **_pose_sequence_diagnostics([]),
        }
        return {
            "ok": False,
            "type": "motion_retarget_result",
            "action": action,
            "skill": "stop",
            "gesture": "none",
            "pose_frames": 0,
            "live_mocap_motion": live_mocap_motion,
            "emit_g1_joint_targets": False,
            "use_isaac_usd_ik": use_isaac_usd_ik,
            "joint_target_count": 0,
            "joint_selection": joint_selection,
            "root_translation_enabled": False,
            "retarget_mode": "stop",
            "diagnostics": diagnostics,
            "motion": motion if isinstance(motion, dict) else {},
            "message": f"Live RGB-D pose is not valid; emitted stop action ({reason}).",
        }

    stream_video_frames = (
        stream_video_frames_requested
        and bool(pose_sequence)
    )
    stream_frame_index = 0
    if stream_video_frames:
        live_frame = max(1, _to_int(context.get("_live_frame"), 1))
        stream_frame_index = (live_frame - 1) % max(1, len(pose_sequence))
        selected_pose_sequence = [pose_sequence[stream_frame_index]]
        action = _action_from_skill(
            skill=skill,
            prompt=prompt,
            motion=motion,
            speed=speed,
            step_scale=step_scale,
            turn_scale=turn_scale,
            duration_sec=0.0,
            pose_sequence=selected_pose_sequence,
            emit_g1_joint_targets=True,
            emit_g1_trajectory=False,
            use_isaac_usd_ik=False,
            root_motion_enabled=False,
            joint_average_window=1,
            joint_selection="recent",
            root_translation_enabled=False,
            prefer_pose_joints=True,
            constrain_joint_targets=True,
        )
        stream_joint_scale = _to_float(props.get("streamJointScale"), 0.62)
        _apply_g1_joint_scale(action, stream_joint_scale)
        _set_g1_action_neutral_joints(
            action,
            [
                "left_shoulder_yaw_joint",
                "right_shoulder_yaw_joint",
                "left_elbow_roll_joint",
                "right_elbow_roll_joint",
                "left_zero_joint",
                "left_one_joint",
                "left_two_joint",
                "left_three_joint",
                "left_four_joint",
                "left_five_joint",
                "left_six_joint",
                "right_zero_joint",
                "right_one_joint",
                "right_two_joint",
                "right_three_joint",
                "right_four_joint",
                "right_five_joint",
                "right_six_joint",
            ],
        )
        root_update = _root_translation_from_pose_sequence(
            pose_sequence,
            frame_indices=[stream_frame_index],
            lateral_scale=_to_float(props.get("streamRootLateralScale", props.get("rootLateralScale")), 0.9),
            vertical_scale=_to_float(props.get("streamRootVerticalScale", props.get("rootVerticalScale")), 1.8),
            depth_scale=_to_float(props.get("streamRootDepthScale", props.get("rootDepthScale")), 0.25),
            image_x_depth_scale=_to_float(props.get("streamRootImageXDepthScale", props.get("rootImageXDepthScale")), 0.0),
            mirror_image_x=_to_bool(
                props.get("streamRootMirrorImageX", props.get("rootMirrorImageX")),
                True,
            ),
            max_lateral=_to_float(props.get("streamRootMaxLateral", props.get("rootMaxLateral")), 0.12),
            max_vertical=_to_float(props.get("streamRootMaxVertical", props.get("rootMaxVertical")), 0.18),
            max_depth=_to_float(props.get("streamRootMaxDepth", props.get("rootMaxDepth")), 0.08),
        )
        if root_update:
            action.update(root_update)
        action["retarget_mode"] = "streamed_joint_targets"
        action["stream_video_frames"] = True
        action["stream_frame_index"] = stream_frame_index
        action["stream_frame_count"] = len(pose_sequence)
        action["stream_retarget_source"] = "pose_joints_2d"
        action["stream_joint_scale"] = stream_joint_scale
        action["duration_sec"] = 0.0
    else:
        action = _action_from_skill(
            skill=skill,
            prompt=prompt,
            motion=motion,
            speed=speed,
            step_scale=step_scale,
            turn_scale=turn_scale,
            duration_sec=duration_sec,
            pose_sequence=pose_sequence,
            emit_g1_joint_targets=emit_g1_joint_targets,
            emit_g1_trajectory=emit_g1_trajectory,
            use_isaac_usd_ik=use_isaac_usd_ik,
            root_motion_enabled=root_motion_enabled,
            joint_average_window=joint_average_window,
            joint_selection=joint_selection,
            root_translation_enabled=root_translation_enabled,
            root_lateral_scale=_to_float(props.get("rootLateralScale"), 1.5),
            root_vertical_scale=_to_float(props.get("rootVerticalScale"), 0.9),
            root_depth_scale=_to_float(props.get("rootDepthScale"), 0.35),
            root_image_x_depth_scale=_to_float(props.get("rootImageXDepthScale"), 0.0),
            root_mirror_image_x=_to_bool(props.get("rootMirrorImageX"), True),
            root_max_lateral=_to_float(props.get("rootMaxLateral"), 0.18),
            root_max_vertical=_to_float(props.get("rootMaxVertical"), 0.35),
            root_max_depth=_to_float(props.get("rootMaxDepth"), 0.20),
            root_motion_mode=_text(props.get("rootMotionMode") or props.get("retargetRootMode") or "in_place"),
            root_pitch_enabled=_to_bool(props.get("rootPitchEnabled", props.get("rootRotationEnabled")), True),
            root_pitch_scale=_to_float(props.get("rootPitchScale"), 1.15),
            root_max_pitch_rad=math.radians(_to_float(props.get("rootMaxPitchDeg"), 30.0)),
        )
    smoothing_debug: Dict[str, Any] = {}
    if emit_g1_joint_targets and not use_isaac_usd_ik and not emit_g1_trajectory and not stream_video_frames:
        smoothing_debug = _apply_g1_joint_smoothing(
            str(node.get("id", "motion_retarget")),
            action,
            joint_smoothing,
            max_delta_rad=joint_max_delta_rad,
            deadband_rad=joint_deadband_rad,
        )

    joint_targets = action.get("joint_targets") if isinstance(action.get("joint_targets"), list) else []
    joint_names = action.get("joint_names") if isinstance(action.get("joint_names"), list) else []
    joint_trajectory = (
        action.get("g1_joint_trajectory")
        if isinstance(action.get("g1_joint_trajectory"), list)
        else action.get("joint_trajectory")
        if isinstance(action.get("joint_trajectory"), list)
        else []
    )
    diagnostics = {
        **_pose_sequence_diagnostics(pose_sequence),
        "pose_scale": pose_scale,
        "pose_calibration": pose_calibration,
        "target_embodiment": target_embodiment,
        "retarget_mode": action.get("retarget_mode", ""),
        "joint_trajectory_count": len(joint_trajectory),
        "joint_trajectory_duration_sec": action.get("joint_trajectory_duration_sec", 0.0),
        "action_duration_sec": action.get("duration_sec", 0.0),
        "joint_target_rad": _numeric_range([float(value) for value in joint_targets]),
        "joint_smoothing": joint_smoothing,
        "joint_max_delta_rad": joint_max_delta_rad,
        "joint_deadband_rad": joint_deadband_rad,
        "joint_smoothing_debug": smoothing_debug,
        "joint_average_window": joint_average_window,
        "joint_selection": joint_selection,
        "live_mocap_motion": live_mocap_motion,
        "stream_video_frames": stream_video_frames,
        "stream_frame_index": stream_frame_index,
        "stream_frame_count": len(pose_sequence) if stream_video_frames else 0,
        "stream_retarget_source": action.get("stream_retarget_source", ""),
        "stream_joint_scale": action.get("stream_joint_scale", None),
        "root_translation": action.get("root_translation", []),
        "root_motion_mode": action.get("root_motion_mode", ""),
        "root_motion_mode_debug": action.get("root_motion_mode_debug", {}),
    }
    _maybe_log_retarget_diagnostics(
        str(node.get("id", "motion_retarget")),
        action,
        diagnostics,
        smoothing_debug,
    )
    return {
        "ok": True,
        "type": "motion_retarget_result",
        "debug_arm_targets": _debug_motion_retarget_arm_targets(action, pose_sequence),
        "debug_lower_body_targets": _debug_motion_retarget_lower_body_targets(action, pose_sequence),
        "action": action,
        "skill": action["skill"],
        "gesture": action["gesture"],
        "pose_frames": len(pose_sequence),
        "live_mocap_motion": live_mocap_motion,
        "emit_g1_joint_targets": emit_g1_joint_targets,
        "emit_g1_trajectory": emit_g1_trajectory,
        "use_isaac_usd_ik": use_isaac_usd_ik,
        "joint_target_count": min(len(joint_names), len(joint_targets)),
        "joint_trajectory_count": len(joint_trajectory),
        "joint_trajectory_duration_sec": action.get("joint_trajectory_duration_sec", 0.0),
        "joint_selection": joint_selection,
        "stream_video_frames": stream_video_frames,
        "stream_frame_index": stream_frame_index,
        "stream_frame_count": len(pose_sequence) if stream_video_frames else 0,
        "root_translation_enabled": root_translation_enabled,
        "root_motion_mode": action.get("root_motion_mode", ""),
        "retarget_mode": action.get("retarget_mode", ""),
        "diagnostics": diagnostics,
        "motion": motion if isinstance(motion, dict) else {},
        "message": "Motion trace retargeted to a humanoid motion action.",
    }
