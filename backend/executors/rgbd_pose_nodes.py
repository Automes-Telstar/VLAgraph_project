from __future__ import annotations

import base64
import io
import math
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlsplit, urlunsplit

import numpy as np
import requests
from PIL import Image, ImageDraw

from backend.executors.mediapipe_g1_mapping import (
    g1_action_payload_from_named_targets,
    landmarks_to_g1_named_targets,
)
from backend.config import UPLOAD_DIR
from backend.motion.extractor import frame_features, summarize_motion


POSE_CONNECTIONS: List[Tuple[str, str]] = [
    ("LEFT_SHOULDER", "RIGHT_SHOULDER"),
    ("LEFT_SHOULDER", "LEFT_ELBOW"),
    ("LEFT_ELBOW", "LEFT_WRIST"),
    ("RIGHT_SHOULDER", "RIGHT_ELBOW"),
    ("RIGHT_ELBOW", "RIGHT_WRIST"),
    ("LEFT_SHOULDER", "LEFT_HIP"),
    ("RIGHT_SHOULDER", "RIGHT_HIP"),
    ("LEFT_HIP", "RIGHT_HIP"),
    ("LEFT_HIP", "LEFT_KNEE"),
    ("LEFT_KNEE", "LEFT_ANKLE"),
    ("RIGHT_HIP", "RIGHT_KNEE"),
    ("RIGHT_KNEE", "RIGHT_ANKLE"),
]

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
REQUIRED_RETARGET_LANDMARKS = {
    "LEFT_SHOULDER",
    "RIGHT_SHOULDER",
    "LEFT_HIP",
    "RIGHT_HIP",
    "LEFT_KNEE",
    "RIGHT_KNEE",
    "LEFT_ANKLE",
    "RIGHT_ANKLE",
}

_FUSION_HISTORY_BY_NODE: Dict[str, List[Dict[str, Any]]] = {}
_FUSION_SMOOTHING_BY_NODE: Dict[str, Dict[str, Dict[str, float]]] = {}
_MEDIAPIPE_POSE_CACHE: Dict[Tuple[bool, int, float, float], Dict[str, Any]] = {}
_MEDIAPIPE_POSE_CACHE_LOCK = threading.Lock()


def reset_rgbd_pose_runtime_state(node_ids: List[str] | None = None) -> None:
    if node_ids is None:
        _FUSION_HISTORY_BY_NODE.clear()
        _FUSION_SMOOTHING_BY_NODE.clear()
        return

    for node_id in node_ids:
        key = str(node_id)
        _FUSION_HISTORY_BY_NODE.pop(key, None)
        _FUSION_SMOOTHING_BY_NODE.pop(key, None)


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

        result[str(target_handle or source_handle or source_id)] = value
    return result


def _node_props(node: Dict[str, Any]) -> Dict[str, Any]:
    data = (node or {}).get("data") or {}
    return data if isinstance(data, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


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


def _split_data_uri(value: str) -> Tuple[str, bytes]:
    header, encoded = value.split(",", 1)
    mime = header[5:].split(";")[0] if header.startswith("data:") else "application/octet-stream"
    return mime or "application/octet-stream", base64.b64decode(encoded)


def _data_uri(raw: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def _array_to_jpeg_data_uri(array: np.ndarray, quality: int = 86) -> str:
    image = Image.fromarray(np.asarray(array).astype("uint8"), mode="RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    return _data_uri(buffer.getvalue(), "image/jpeg")


def _depth_to_png_data_uri(depth_units: np.ndarray) -> str:
    depth = np.asarray(depth_units).astype(np.uint16)
    image = Image.fromarray(depth, mode="I;16")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", compress_level=1)
    return _data_uri(buffer.getvalue(), "image/png")


def _depth_preview_data_uri(
    depth_units: np.ndarray,
    *,
    scale_meters_per_unit: float,
    min_meters: float,
    max_meters: float,
) -> str:
    depth_m = np.asarray(depth_units).astype("float32") * float(scale_meters_per_unit)
    valid = depth_m > 0
    span = max(max_meters - min_meters, 0.01)
    norm = np.clip((depth_m - min_meters) / span, 0.0, 1.0)

    rgb = np.zeros((*depth_m.shape, 3), dtype=np.uint8)
    rgb[..., 0] = (255.0 * norm).astype(np.uint8)
    rgb[..., 1] = (255.0 * (1.0 - np.abs(norm * 2.0 - 1.0))).astype(np.uint8)
    rgb[..., 2] = (255.0 * (1.0 - norm)).astype(np.uint8)
    rgb[~valid] = np.array([10, 16, 28], dtype=np.uint8)
    return _array_to_jpeg_data_uri(rgb, quality=82)


def _resolve_upload_path(value: str) -> Optional[Path]:
    parsed = urlsplit(value)
    if parsed.path.startswith("/uploads/"):
        return Path(UPLOAD_DIR) / Path(unquote(parsed.path)).name
    if value.startswith("/uploads/") or value.startswith("\\uploads\\"):
        return Path(UPLOAD_DIR) / Path(value.replace("\\", "/")).name

    path = Path(value)
    if path.exists():
        return path
    upload_candidate = Path(UPLOAD_DIR) / path.name
    return upload_candidate if upload_candidate.exists() else None


def _image_bytes_from_value(value: Any) -> bytes:
    text = _text(value)
    if not text:
        raise ValueError("image input is empty")

    if text.startswith("data:"):
        return _split_data_uri(text)[1]

    if text.startswith("http://") or text.startswith("https://"):
        response = requests.get(text, timeout=10)
        response.raise_for_status()
        return response.content

    path = _resolve_upload_path(text)
    if path is None:
        raise FileNotFoundError(f"Image not found: {text}")
    return path.read_bytes()


def _image_array_from_value(value: Any) -> np.ndarray:
    raw = _image_bytes_from_value(value)
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    return np.asarray(image)


def _depth_array_from_payload(payload: Any) -> Tuple[np.ndarray, Dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("depth input must be a depth JSON payload")

    data_uri = _text(payload.get("data_uri") or payload.get("depth_data_uri") or payload.get("png"))
    if data_uri:
        _, raw = _split_data_uri(data_uri)
        image = Image.open(io.BytesIO(raw))
        return np.asarray(image).astype(np.uint16), payload

    values = payload.get("values")
    if isinstance(values, list):
        return np.asarray(values).astype(np.uint16), payload

    raise ValueError("depth payload requires data_uri or values")


def _intrinsics_dict(intrinsics: Any, *, width: int, height: int) -> Dict[str, Any]:
    if intrinsics is None:
        return {
            "width": width,
            "height": height,
            "fx": float(width),
            "fy": float(width),
            "ppx": width / 2.0,
            "ppy": height / 2.0,
            "model": "pinhole_fallback",
            "coeffs": [0.0, 0.0, 0.0, 0.0, 0.0],
        }

    coeffs = list(getattr(intrinsics, "coeffs", []) or [])
    return {
        "width": int(getattr(intrinsics, "width", width) or width),
        "height": int(getattr(intrinsics, "height", height) or height),
        "fx": float(getattr(intrinsics, "fx", width) or width),
        "fy": float(getattr(intrinsics, "fy", width) or width),
        "ppx": float(getattr(intrinsics, "ppx", width / 2.0) or width / 2.0),
        "ppy": float(getattr(intrinsics, "ppy", height / 2.0) or height / 2.0),
        "model": str(getattr(intrinsics, "model", "unknown")),
        "coeffs": [float(item) for item in coeffs[:5]],
    }


def _rs_frame_number(frame: Any) -> Any:
    try:
        return int(frame.get_frame_number())
    except Exception:
        return None


def _rs_frame_timestamp_ms(frame: Any) -> Any:
    try:
        return float(frame.get_timestamp())
    except Exception:
        return None


def _rgbd_frame_id(source: str, color_frame_number: Any, depth_frame_number: Any, timestamp: float) -> str:
    if color_frame_number is not None or depth_frame_number is not None:
        color_part = color_frame_number if color_frame_number is not None else "x"
        depth_part = depth_frame_number if depth_frame_number is not None else "x"
        return f"{source}-c{color_part}-d{depth_part}"
    return f"{source}-{timestamp:.6f}"


def _mock_realsense_frame(width: int, height: int) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any], float]:
    x = np.linspace(0, 1, width, dtype=np.float32)
    y = np.linspace(0, 1, height, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)
    rgb = np.stack(
        [
            (40 + xx * 160).astype(np.uint8),
            (70 + yy * 120).astype(np.uint8),
            (120 + (1.0 - xx) * 80).astype(np.uint8),
        ],
        axis=-1,
    )
    depth_m = 0.7 + yy * 1.6 + np.sin(xx * math.pi) * 0.2
    scale = 0.001
    depth_units = np.clip(depth_m / scale, 0, 65535).astype(np.uint16)
    intrinsics = _intrinsics_dict(None, width=width, height=height)
    return rgb, depth_units, intrinsics, scale


def _capture_realsense_frame(props: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any], float, Dict[str, Any]]:
    width = max(160, _to_int(props.get("captureWidth"), 640))
    height = max(120, _to_int(props.get("captureHeight"), 480))
    fps = max(1, _to_int(props.get("fps"), 30))
    timeout_ms = max(100, _to_int(props.get("frameTimeoutMs"), 5000))
    warmup_frames = max(0, _to_int(props.get("warmupFrames"), 4))
    serial = _text(props.get("realsenseSerial"))

    try:
        import pyrealsense2 as rs  # type: ignore
    except Exception as exc:
        if _to_bool(props.get("mockWhenUnavailable"), False):
            rgb, depth_units, intrinsics, scale = _mock_realsense_frame(width, height)
            return rgb, depth_units, intrinsics, scale, {"device": "mock", "warning": str(exc)}
        raise RuntimeError(
            "RealSense D435i Sensor requires pyrealsense2 and a connected camera. "
            "Install pyrealsense2 on the backend host or enable mockWhenUnavailable for testing. "
            f"Import error: {exc}"
        ) from exc

    context = rs.context()
    devices = context.query_devices()
    if len(devices) == 0:
        if _to_bool(props.get("mockWhenUnavailable"), False):
            rgb, depth_units, intrinsics, scale = _mock_realsense_frame(width, height)
            return rgb, depth_units, intrinsics, scale, {
                "device": "mock",
                "warning": "pyrealsense2 is installed, but no RealSense camera is visible.",
            }
        raise RuntimeError(
            "pyrealsense2 is installed, but no RealSense camera is visible inside the backend "
            "container. Attach the Intel D435i to WSL2/Docker USB, run the backend on the host "
            "machine, or enable mockWhenUnavailable for a pipeline test."
        )

    pipeline = rs.pipeline()
    config = rs.config()
    if serial:
        config.enable_device(serial)
    config.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)
    config.enable_stream(rs.stream.color, width, height, rs.format.rgb8, fps)

    profile = pipeline.start(config)
    try:
        align = rs.align(rs.stream.color)
        frames = None
        for _ in range(max(1, warmup_frames + 1)):
            frames = pipeline.wait_for_frames(timeout_ms)
        aligned = align.process(frames)
        depth_frame = aligned.get_depth_frame()
        color_frame = aligned.get_color_frame()
        if not depth_frame or not color_frame:
            raise RuntimeError("RealSense returned incomplete color/depth frames")

        rgb = np.asanyarray(color_frame.get_data()).astype(np.uint8)
        depth_units = np.asanyarray(depth_frame.get_data()).astype(np.uint16)
        intrinsics = _intrinsics_dict(
            color_frame.profile.as_video_stream_profile().get_intrinsics(),
            width=int(rgb.shape[1]),
            height=int(rgb.shape[0]),
        )
        depth_scale = float(profile.get_device().first_depth_sensor().get_depth_scale())
        color_frame_number = _rs_frame_number(color_frame)
        depth_frame_number = _rs_frame_number(depth_frame)
        metadata = {
            "device": "realsense",
            "serial": serial,
            "fps": fps,
            "warmup_frames": warmup_frames,
            "color_frame_number": color_frame_number,
            "depth_frame_number": depth_frame_number,
            "color_timestamp_ms": _rs_frame_timestamp_ms(color_frame),
            "depth_timestamp_ms": _rs_frame_timestamp_ms(depth_frame),
        }
        return rgb, depth_units, intrinsics, depth_scale, metadata
    finally:
        pipeline.stop()


def _running_in_container() -> bool:
    return Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()


def _replace_url_hostname(url: str, hostname: str) -> str:
    parsed = urlsplit(url)
    if not parsed.hostname:
        return url

    netloc = hostname
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    if parsed.username:
        credentials = parsed.username
        if parsed.password:
            credentials = f"{credentials}:{parsed.password}"
        netloc = f"{credentials}@{netloc}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def _remote_rgbd_url_candidates(url: str) -> List[str]:
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower()
    candidates = [url]

    if hostname == "host.docker.internal":
        local_candidates = [
            _replace_url_hostname(url, "127.0.0.1"),
            _replace_url_hostname(url, "localhost"),
        ]
        candidates = candidates + local_candidates if _running_in_container() else local_candidates + candidates
    elif hostname in {"localhost", "127.0.0.1"}:
        docker_host = _replace_url_hostname(url, "host.docker.internal")
        candidates = candidates + [docker_host] if not _running_in_container() else [docker_host] + candidates

    unique: List[str] = []
    for candidate in candidates:
        if candidate and candidate not in unique:
            unique.append(candidate)
    return unique


def _fetch_remote_rgbd_result(props: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    url = _text(props.get("remoteRgbdUrl") or props.get("remoteRGBDUrl"))
    if not url:
        return None

    timeout_sec = max(0.5, _to_float(props.get("requestTimeoutSec"), 10.0))
    errors: List[str] = []
    payload: Dict[str, Any] | None = None
    resolved_url = url
    for candidate_url in _remote_rgbd_url_candidates(url):
        try:
            response = requests.get(candidate_url, timeout=timeout_sec)
            response.raise_for_status()
            candidate_payload = response.json()
            if not isinstance(candidate_payload, dict):
                raise ValueError("Remote RGB-D endpoint must return a JSON object")
            payload = candidate_payload
            resolved_url = candidate_url
            break
        except Exception as exc:
            errors.append(f"{candidate_url} -> {exc}")

    if payload is None:
        raise RuntimeError("Remote RGB-D endpoint unavailable. " + "; ".join(errors))

    if not isinstance(payload, dict):
        raise ValueError("Remote RGB-D endpoint must return a JSON object")

    image = _text(payload.get("image"))
    depth = payload.get("depth")
    if not image:
        raise ValueError("Remote RGB-D endpoint response requires image")
    if not isinstance(depth, dict):
        raise ValueError("Remote RGB-D endpoint response requires depth JSON")

    depth_image = _text(payload.get("depth_image") or depth.get("preview_image"))
    sensor = payload.get("sensor") if isinstance(payload.get("sensor"), dict) else {}
    if not sensor:
        sensor = {
            "type": "remote_realsense_d435i_frame",
            "source": "remote_rgbd",
            "remote_url": resolved_url,
            "timestamp": payload.get("timestamp", time.time()),
        }
    sensor["remote_url"] = resolved_url
    if resolved_url != url:
        sensor["configured_remote_url"] = url
    sensor["source"] = sensor.get("source", "remote_rgbd")
    sensor_source = _text(sensor.get("source")).lower()
    bridge_source = _text(sensor.get("bridge_source")).lower()
    if (
        "mock" in {sensor_source, bridge_source}
        and not _to_bool(props.get("mockWhenUnavailable"), False)
    ):
        raise RuntimeError(
            "Remote RealSense bridge is returning mock frames instead of a real camera frame. "
            "Attach the D435i to Docker/WSL USB or enable mockWhenUnavailable for testing."
        )

    frame_id = _text(payload.get("frame_id") or sensor.get("frame_id") or depth.get("frame_id"))
    if frame_id:
        sensor["frame_id"] = frame_id
        depth = dict(depth)
        depth["frame_id"] = frame_id

    return {
        "ok": True,
        "type": "realsense_d435i_sensor_result",
        "frame_id": frame_id,
        "image": image,
        "depth_image": depth_image,
        "depth": depth,
        "sensor": sensor,
        "timestamp": payload.get("timestamp", time.time()),
    }


def _capture_realsense_result(props: Dict[str, Any]) -> Dict[str, Any]:
    remote_warning = ""
    try:
        remote_result = _fetch_remote_rgbd_result(props)
    except Exception as exc:
        if not _to_bool(props.get("mockWhenUnavailable"), False):
            raise
        remote_warning = f"Remote RGB-D endpoint unavailable; using mock frame. {exc}"
        remote_result = None
    if remote_result is not None:
        return remote_result

    rgb, depth_units, intrinsics, depth_scale, metadata = _capture_realsense_frame(props)
    if remote_warning:
        metadata = dict(metadata)
        metadata["warning"] = remote_warning
    now = time.time()
    depth_min = _to_float(props.get("depthMinMeters"), 0.2)
    depth_max = _to_float(props.get("depthMaxMeters"), 4.0)
    color_frame_number = metadata.get("color_frame_number")
    depth_frame_number = metadata.get("depth_frame_number")
    frame_id = _text(metadata.get("frame_id")) or _rgbd_frame_id(
        _text(metadata.get("device") or "realsense"),
        color_frame_number,
        depth_frame_number,
        now,
    )

    color_image = _array_to_jpeg_data_uri(rgb)
    depth_data_uri = _depth_to_png_data_uri(depth_units)
    depth_image = _depth_preview_data_uri(
        depth_units,
        scale_meters_per_unit=depth_scale,
        min_meters=depth_min,
        max_meters=depth_max,
    )
    valid_depth = depth_units[depth_units > 0]
    nearest_depth = float(valid_depth.min() * depth_scale) if valid_depth.size else None

    depth_payload = {
        "type": "realsense_aligned_depth",
        "format": "z16_png",
        "data_uri": depth_data_uri,
        "preview_image": depth_image,
        "width": int(depth_units.shape[1]),
        "height": int(depth_units.shape[0]),
        "scale_meters_per_unit": depth_scale,
        "intrinsics": intrinsics,
        "aligned_to": "color",
        "timestamp": now,
        "frame_id": frame_id,
        "frame_number": depth_frame_number,
        "nearest_depth_m": None if nearest_depth is None else round(nearest_depth, 4),
    }

    sensor_packet = {
        "type": "realsense_d435i_frame",
        "source": metadata.get("device", "realsense"),
        "serial": metadata.get("serial", ""),
        "frame_id": frame_id,
        "color_frame_number": color_frame_number,
        "depth_frame_number": depth_frame_number,
        "color_timestamp_ms": metadata.get("color_timestamp_ms"),
        "depth_timestamp_ms": metadata.get("depth_timestamp_ms"),
        "rgb": {
            "width": int(rgb.shape[1]),
            "height": int(rgb.shape[0]),
            "content_type": "image/jpeg",
        },
        "depth": {
            "width": int(depth_units.shape[1]),
            "height": int(depth_units.shape[0]),
            "format": "z16_png",
            "scale_meters_per_unit": depth_scale,
            "nearest_depth_m": depth_payload["nearest_depth_m"],
            "frame_number": depth_frame_number,
        },
        "intrinsics": intrinsics,
        "timestamp": now,
        "metadata": metadata,
    }

    return {
        "ok": True,
        "type": "realsense_d435i_sensor_result",
        "frame_id": frame_id,
        "image": color_image,
        "depth_image": depth_image,
        "depth": depth_payload,
        "sensor": sensor_packet,
        "timestamp": now,
    }


def exec_realsense_d435i_sensor(
    node: Dict[str, Any],
    context: Dict[str, Any],
    edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    props = _node_props(node)
    return _capture_realsense_result(props)


def _landmarks_from_mediapipe_result(result: Any, mp_pose: Any, *, min_visibility: float) -> Tuple[Dict[str, Any], Dict[str, Any], int]:
    landmarks: Dict[str, Any] = {}
    world_landmarks: Dict[str, Any] = {}
    visible_count = 0

    if result.pose_landmarks:
        for index, landmark in enumerate(result.pose_landmarks.landmark):
            name = mp_pose.PoseLandmark(index).name
            visibility = float(getattr(landmark, "visibility", 0.0))
            if visibility >= min_visibility:
                visible_count += 1
            landmarks[name] = {
                "x": round(float(landmark.x), 6),
                "y": round(float(landmark.y), 6),
                "z": round(float(landmark.z), 6),
                "visibility": round(visibility, 6),
            }

    if result.pose_world_landmarks:
        for index, landmark in enumerate(result.pose_world_landmarks.landmark):
            name = mp_pose.PoseLandmark(index).name
            world_landmarks[name] = {
                "x": round(float(landmark.x), 6),
                "y": round(float(landmark.y), 6),
                "z": round(float(landmark.z), 6),
                "visibility": round(float(getattr(landmark, "visibility", 0.0)), 6),
            }

    return landmarks, world_landmarks, visible_count


def _point_for_landmark(landmark: Dict[str, Any], width: int, height: int) -> Optional[Tuple[float, float]]:
    x = _to_float(landmark.get("x"), float("nan"))
    y = _to_float(landmark.get("y"), float("nan"))
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    return x * width, y * height


def _draw_pose_overlay(
    image_array: np.ndarray,
    landmarks: Dict[str, Any],
    *,
    min_visibility: float,
    label: str = "",
    depth_by_name: Optional[Dict[str, float]] = None,
) -> str:
    image = Image.fromarray(np.asarray(image_array).astype("uint8"), mode="RGB")
    draw = ImageDraw.Draw(image)
    width, height = image.size

    def point(name: str) -> Optional[Tuple[float, float]]:
        landmark = landmarks.get(name)
        if not isinstance(landmark, dict):
            return None
        if _to_float(landmark.get("visibility"), 1.0) < min_visibility:
            return None
        return _point_for_landmark(landmark, width, height)

    for start_name, end_name in POSE_CONNECTIONS:
        start = point(start_name)
        end = point(end_name)
        if not start or not end:
            continue
        draw.line([start, end], fill=(45, 212, 191), width=max(2, width // 220))

    radius = max(3, width // 160)
    for name, landmark in landmarks.items():
        if not isinstance(landmark, dict):
            continue
        if _to_float(landmark.get("visibility"), 1.0) < min_visibility:
            continue
        p = _point_for_landmark(landmark, width, height)
        if not p:
            continue
        x, y = p
        depth = depth_by_name.get(name) if depth_by_name else None
        fill = (249, 115, 22) if depth is not None else (248, 250, 252)
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=fill, outline=(15, 23, 42), width=2)

    if label:
        draw.rectangle([8, 8, min(width - 8, 8 + len(label) * 8 + 16), 32], fill=(15, 23, 42))
        draw.text((16, 13), label, fill=(219, 234, 254))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=86)
    return _data_uri(buffer.getvalue(), "image/jpeg")


def _pose_preview(landmarks: Dict[str, Any], *, width: int, height: int) -> Dict[str, Any]:
    compact: Dict[str, Any] = {}
    for name in POSE_PREVIEW_LANDMARKS:
        value = landmarks.get(name)
        if isinstance(value, dict):
            compact[name] = {
                "x": value.get("x"),
                "y": value.get("y"),
                "visibility": value.get("visibility", 1.0),
            }
    return {
        "type": "mediapipe_pose_preview",
        "landmarks": sorted(POSE_PREVIEW_LANDMARKS),
        "frames": [
            {
                "frame_index": 0,
                "timestamp_sec": 0.0,
                "landmarks": compact,
            }
        ],
        "video": {
            "width": width,
            "height": height,
            "frame_count": 1,
            "fps": 0,
            "duration_sec": None,
        },
    }


def _detect_mediapipe_pose(
    image_array: np.ndarray,
    props: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        import mediapipe as mp
    except Exception as exc:
        raise RuntimeError(f"MediaPipe Pose requires mediapipe to be installed: {exc}") from exc

    height, width = int(image_array.shape[0]), int(image_array.shape[1])
    min_visibility = _to_float(props.get("minPoseVisibility"), 0.35)
    model_complexity = _to_int(props.get("modelComplexity"), 1)
    min_detection = _to_float(props.get("minDetectionConfidence"), 0.5)
    min_tracking = _to_float(props.get("minTrackingConfidence"), 0.5)
    static_image_mode = _to_bool(props.get("staticImageMode"), False)
    mp_pose = mp.solutions.pose

    cache_key = (
        bool(static_image_mode),
        int(model_complexity),
        round(float(min_detection), 3),
        round(float(min_tracking), 3),
    )
    with _MEDIAPIPE_POSE_CACHE_LOCK:
        pose_entry = _MEDIAPIPE_POSE_CACHE.get(cache_key)
        if pose_entry is None:
            pose_entry = {
                "pose": mp_pose.Pose(
                    static_image_mode=static_image_mode,
                    model_complexity=model_complexity,
                    enable_segmentation=False,
                    min_detection_confidence=min_detection,
                    min_tracking_confidence=min_tracking,
                ),
                "lock": threading.Lock(),
            }
            _MEDIAPIPE_POSE_CACHE[cache_key] = pose_entry

    with pose_entry["lock"]:
        pose = pose_entry["pose"]
        result = pose.process(image_array)

    if not result.pose_landmarks:
        return {
            "ok": False,
            "pose": {
                "type": "mediapipe_pose",
                "landmarks": {},
                "world_landmarks": {},
                "image_width": width,
                "image_height": height,
            },
            "visible_landmarks": 0,
            "message": "No pose landmarks detected.",
        }

    landmarks, world_landmarks, visible_count = _landmarks_from_mediapipe_result(
        result,
        mp_pose,
        min_visibility=min_visibility,
    )
    return {
        "ok": True,
        "pose": {
            "type": "mediapipe_pose",
            "landmarks": landmarks,
            "world_landmarks": world_landmarks,
            "image_width": width,
            "image_height": height,
            "visible_landmarks": visible_count,
            "min_visibility": min_visibility,
            "timestamp": time.time(),
        },
        "visible_landmarks": visible_count,
    }


def exec_mediapipe_pose(
    node: Dict[str, Any],
    context: Dict[str, Any],
    edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    props = _node_props(node)
    inputs = _incoming_values(node["id"], edges, context)
    image_value = inputs.get("image") or props.get("image")
    if not image_value:
        raise ValueError("MediaPipe Pose requires an image input")

    image_array = _image_array_from_value(image_value)
    height, width = int(image_array.shape[0]), int(image_array.shape[1])
    min_visibility = _to_float(props.get("minPoseVisibility"), 0.35)
    detection = _detect_mediapipe_pose(image_array, props)

    if not detection.get("ok"):
        annotated = _array_to_jpeg_data_uri(image_array)
        return {
            "ok": False,
            "type": "mediapipe_pose_result",
            "image": annotated,
            "pose": detection.get("pose", {}),
            "message": detection.get("message", "No pose landmarks detected."),
        }

    pose_payload = detection["pose"]
    landmarks = pose_payload.get("landmarks", {})
    visible_count = int(detection.get("visible_landmarks", 0) or 0)
    annotated = _draw_pose_overlay(
        image_array,
        landmarks,
        min_visibility=min_visibility,
        label=f"MediaPipe pose {visible_count}",
    )

    return {
        "ok": True,
        "type": "mediapipe_pose_result",
        "image": annotated,
        "pose": pose_payload,
        "pose_preview": _pose_preview(landmarks, width=width, height=height),
        "visible_landmarks": visible_count,
    }


def _depth_sample_stats(
    depth_units: np.ndarray,
    *,
    px: int,
    py: int,
    radius: int,
    scale_meters_per_unit: float,
) -> Optional[Dict[str, Any]]:
    height, width = depth_units.shape[:2]
    x0 = max(0, px - radius)
    x1 = min(width, px + radius + 1)
    y0 = max(0, py - radius)
    y1 = min(height, py + radius + 1)
    patch = np.asarray(depth_units[y0:y1, x0:x1]).reshape(-1)
    total_count = int(patch.size)
    if total_count <= 0:
        return None
    valid = patch[patch > 0].astype(np.float64) * float(scale_meters_per_unit)
    if valid.size == 0:
        return None
    q25, q75 = np.percentile(valid, [25, 75])
    median = float(np.median(valid))
    return {
        "depth_m": median,
        "valid_count": int(valid.size),
        "total_count": total_count,
        "valid_ratio": float(valid.size) / float(total_count),
        "iqr_m": float(q75 - q25),
        "min_m": float(np.min(valid)),
        "max_m": float(np.max(valid)),
    }


def _landmarks_3d_from_depth(
    pose_payload: Dict[str, Any],
    depth_units: np.ndarray,
    depth_payload: Dict[str, Any],
    *,
    radius: int,
    min_visibility: float,
) -> Tuple[Dict[str, Any], Dict[str, float]]:
    landmarks = pose_payload.get("landmarks")
    if not isinstance(landmarks, dict):
        raise ValueError("pose payload requires landmarks")

    intrinsics = depth_payload.get("intrinsics") if isinstance(depth_payload.get("intrinsics"), dict) else {}
    fx = _to_float(intrinsics.get("fx"), float(depth_units.shape[1]))
    fy = _to_float(intrinsics.get("fy"), float(depth_units.shape[1]))
    ppx = _to_float(intrinsics.get("ppx"), depth_units.shape[1] / 2.0)
    ppy = _to_float(intrinsics.get("ppy"), depth_units.shape[0] / 2.0)
    scale = _to_float(depth_payload.get("scale_meters_per_unit"), 0.001)
    image_width = _to_int(pose_payload.get("image_width"), int(depth_units.shape[1]))
    image_height = _to_int(pose_payload.get("image_height"), int(depth_units.shape[0]))
    depth_height, depth_width = depth_units.shape[:2]
    min_valid_ratio = _to_float(os.getenv("RGBD_DEPTH_SAMPLE_MIN_VALID_RATIO"), 0.35)
    max_iqr_m = _to_float(os.getenv("RGBD_DEPTH_SAMPLE_MAX_IQR_M"), 0.18)

    fused: Dict[str, Any] = {}
    depth_by_name: Dict[str, float] = {}
    for name, landmark in landmarks.items():
        if not isinstance(landmark, dict):
            continue
        visibility = _to_float(landmark.get("visibility"), 1.0)
        if visibility < min_visibility:
            continue

        x_norm = _to_float(landmark.get("x"), float("nan"))
        y_norm = _to_float(landmark.get("y"), float("nan"))
        if not math.isfinite(x_norm) or not math.isfinite(y_norm):
            continue

        color_px = int(round(x_norm * max(1, image_width - 1)))
        color_py = int(round(y_norm * max(1, image_height - 1)))
        depth_px = int(round(color_px * depth_width / max(1, image_width)))
        depth_py = int(round(color_py * depth_height / max(1, image_height)))
        stats = _depth_sample_stats(
            depth_units,
            px=depth_px,
            py=depth_py,
            radius=radius,
            scale_meters_per_unit=scale,
        )
        if not stats:
            continue
        depth_m = float(stats["depth_m"])
        if depth_m is None or depth_m <= 0:
            continue
        if float(stats.get("valid_ratio", 0.0)) < min_valid_ratio:
            continue
        if float(stats.get("iqr_m", 0.0)) > max_iqr_m:
            continue

        x_m = (depth_px - ppx) / max(fx, 1e-6) * depth_m
        y_m = (depth_py - ppy) / max(fy, 1e-6) * depth_m
        fused[name] = {
            "x": round(x_m, 6),
            "y": round(y_m, 6),
            "z": round(depth_m, 6),
            "visibility": round(visibility, 6),
            "pixel_x": color_px,
            "pixel_y": color_py,
            "depth_m": round(depth_m, 6),
            "depth_valid_ratio": round(float(stats.get("valid_ratio", 0.0)), 6),
            "depth_iqr_m": round(float(stats.get("iqr_m", 0.0)), 6),
            "depth_sample_count": int(stats.get("valid_count", 0)),
            "depth_sample_total": int(stats.get("total_count", 0)),
            "source": "realsense_depth",
        }
        depth_by_name[name] = depth_m

    return fused, depth_by_name


def _point3_from_landmark(landmarks: Dict[str, Any], name: str) -> Optional[Tuple[float, float, float]]:
    landmark = landmarks.get(name)
    if not isinstance(landmark, dict):
        return None
    try:
        point = (float(landmark["x"]), float(landmark["y"]), float(landmark["z"]))
    except Exception:
        return None
    if not all(math.isfinite(item) for item in point):
        return None
    return point


def _vec_sub(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _vec_scale(v: Tuple[float, float, float], scale: float) -> Tuple[float, float, float]:
    return (v[0] * scale, v[1] * scale, v[2] * scale)


def _vec_dot(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _vec_cross(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _vec_len(v: Tuple[float, float, float]) -> float:
    return math.sqrt(_vec_dot(v, v))


def _vec_normalize(v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    length = _vec_len(v)
    if length <= 1.0e-8:
        return (0.0, 0.0, 0.0)
    return (v[0] / length, v[1] / length, v[2] / length)


def _midpoint(
    a: Tuple[float, float, float],
    b: Tuple[float, float, float],
) -> Tuple[float, float, float]:
    return ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, (a[2] + b[2]) * 0.5)


def _body_centered_axes(
    depth_landmarks: Dict[str, Any],
) -> Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float], float]]:
    left_shoulder = _point3_from_landmark(depth_landmarks, "LEFT_SHOULDER")
    right_shoulder = _point3_from_landmark(depth_landmarks, "RIGHT_SHOULDER")
    left_hip = _point3_from_landmark(depth_landmarks, "LEFT_HIP")
    right_hip = _point3_from_landmark(depth_landmarks, "RIGHT_HIP")

    shoulder_center = _midpoint(left_shoulder, right_shoulder) if left_shoulder and right_shoulder else None
    hip_center = _midpoint(left_hip, right_hip) if left_hip and right_hip else None
    origin = hip_center or shoulder_center
    if origin is None:
        return None

    if left_shoulder and right_shoulder:
        right_axis = _vec_normalize(_vec_sub(right_shoulder, left_shoulder))
        shoulder_width = _vec_len(_vec_sub(right_shoulder, left_shoulder))
    elif left_hip and right_hip:
        right_axis = _vec_normalize(_vec_sub(right_hip, left_hip))
        shoulder_width = 0.0
    else:
        return None

    if shoulder_center and hip_center:
        up_axis = _vec_normalize(_vec_sub(shoulder_center, hip_center))
        torso_scale = _vec_len(_vec_sub(shoulder_center, hip_center))
    else:
        # RealSense camera coordinates use +Y downward, so camera-up is -Y.
        up_axis = (0.0, -1.0, 0.0)
        torso_scale = 0.0

    # Anatomical forward points out of the chest. For a person facing the
    # camera, right_axis x up_axis points toward the person's back, so flip it.
    forward_axis = _vec_normalize(_vec_scale(_vec_cross(right_axis, up_axis), -1.0))
    if _vec_len(forward_axis) <= 1.0e-6:
        forward_axis = (0.0, 0.0, -1.0)
    up_axis = _vec_normalize(_vec_cross(right_axis, forward_axis))

    hip_width = _vec_len(_vec_sub(right_hip, left_hip)) if left_hip and right_hip else 0.0
    body_scale = shoulder_width or hip_width or torso_scale or 0.35
    return origin, right_axis, up_axis, forward_axis, max(body_scale, 1.0e-6)


def _body_centered_landmarks_from_depth(depth_landmarks: Dict[str, Any]) -> Dict[str, Any]:
    axes = _body_centered_axes(depth_landmarks)
    if axes is None:
        return depth_landmarks

    origin, right_axis, up_axis, forward_axis, body_scale = axes
    normalized: Dict[str, Any] = {}
    for name, landmark in depth_landmarks.items():
        if not isinstance(landmark, dict):
            continue
        point = _point3_from_landmark(depth_landmarks, str(name))
        if point is None:
            continue
        rel = _vec_sub(point, origin)
        item = {
            "x": round(_vec_dot(rel, right_axis) / body_scale, 6),
            "y": round(_vec_dot(rel, up_axis) / body_scale, 6),
            "z": round(_vec_dot(rel, forward_axis) / body_scale, 6),
            "visibility": landmark.get("visibility", 1.0),
            "coordinate_frame": "body_centered_3d",
            "body_scale_m": round(body_scale, 6),
            "camera_x": landmark.get("x"),
            "camera_y": landmark.get("y"),
            "camera_z": landmark.get("z"),
        }
        for key in ("depth_m", "pixel_x", "pixel_y"):
            if key in landmark:
                item[key] = landmark.get(key)
        normalized[str(name)] = item
    return normalized or depth_landmarks


def _body_centered_landmarks_from_world(world_landmarks: Dict[str, Any]) -> Dict[str, Any]:
    axes = _body_centered_axes(world_landmarks)
    if axes is None:
        return {}

    origin, right_axis, up_axis, forward_axis, body_scale = axes
    normalized: Dict[str, Any] = {}
    for name, landmark in world_landmarks.items():
        if not isinstance(landmark, dict):
            continue
        point = _point3_from_landmark(world_landmarks, str(name))
        if point is None:
            continue
        rel = _vec_sub(point, origin)
        normalized[str(name)] = {
            "x": round(_vec_dot(rel, right_axis) / body_scale, 6),
            "y": round(_vec_dot(rel, up_axis) / body_scale, 6),
            "z": round(_vec_dot(rel, forward_axis) / body_scale, 6),
            "visibility": landmark.get("visibility", 1.0),
            "coordinate_frame": "body_centered_world_3d",
            "body_scale_m": round(body_scale, 6),
            "source": "mediapipe_world",
        }
    return normalized


def _arm_chain_outlier_score(landmarks: Dict[str, Any], side: str) -> float:
    prefix = "LEFT" if side == "left" else "RIGHT"
    shoulder = _point3_from_landmark(landmarks, f"{prefix}_SHOULDER")
    elbow = _point3_from_landmark(landmarks, f"{prefix}_ELBOW")
    wrist = _point3_from_landmark(landmarks, f"{prefix}_WRIST")
    if shoulder is None or elbow is None or wrist is None:
        return 0.0

    upper = _vec_sub(elbow, shoulder)
    lower = _vec_sub(wrist, elbow)
    reach = _vec_sub(wrist, shoulder)
    upper_len = _vec_len(upper)
    lower_len = _vec_len(lower)
    reach_len = _vec_len(reach)
    if min(upper_len, lower_len, reach_len) <= 1.0e-6:
        return 0.0

    extension = max(0.0, min(1.0, (reach_len / max(upper_len + lower_len, reach_len) - 0.70) / 0.30))
    alignment = _vec_dot(_vec_normalize(upper), _vec_normalize(reach))
    disagreement = max(0.0, min(1.0, (0.72 - alignment) / 1.44))
    # Depth can occasionally sample the background around wrists/elbows. In body-centered
    # units, human arm chains should not span many shoulder widths even if fully extended.
    length_excess = max(upper_len - 1.8, lower_len - 1.8, reach_len - 2.4)
    length_outlier = max(0.0, min(1.0, length_excess / 2.0))
    return max(extension * disagreement, length_outlier)


def _merge_world_pose_for_unreliable_arms(
    depth_centered: Dict[str, Any],
    world_centered: Dict[str, Any],
) -> Dict[str, Any]:
    if not depth_centered or not world_centered:
        return depth_centered

    merged = {str(name): dict(value) if isinstance(value, dict) else value for name, value in depth_centered.items()}
    prefer_world_arms = _to_bool(os.getenv("RGBD_RETARGET_PREFER_WORLD_ARMS"), False)
    for side in ("left", "right"):
        prefix = "LEFT" if side == "left" else "RIGHT"
        shoulder_name = f"{prefix}_SHOULDER"
        arm_names = [f"{prefix}_ELBOW", f"{prefix}_WRIST"]
        required = [shoulder_name, *arm_names]
        if not all(name in world_centered for name in required):
            continue

        depth_score = _arm_chain_outlier_score(merged, side)
        world_score = _arm_chain_outlier_score(world_centered, side)
        should_repair = depth_score > max(0.18, world_score + 0.08)
        should_prefer_world = prefer_world_arms and world_score <= 0.35
        depth_missing = any(name not in merged for name in arm_names)
        if not (should_repair or should_prefer_world or depth_missing):
            continue

        # Keep each arm chain in one coordinate frame. Mixing a depth-space
        # shoulder with world-space elbow/wrist makes raised/lowered arm tests
        # flip because the shoulder origin no longer matches the arm points.
        replacement_names = [shoulder_name, *arm_names]
        for name in replacement_names:
            replacement = dict(world_centered[name])
            replacement["source"] = (
                "mediapipe_world_arm"
                if should_prefer_world and not should_repair
                else "mediapipe_world_repaired_arm"
            )
            replacement["repaired_from_depth_score"] = round(depth_score, 6)
            merged[name] = replacement
    return merged


def _leg_chain_outlier_score(landmarks: Dict[str, Any], side: str) -> float:
    prefix = "LEFT" if side == "left" else "RIGHT"
    hip = _point3_from_landmark(landmarks, f"{prefix}_HIP")
    knee = _point3_from_landmark(landmarks, f"{prefix}_KNEE")
    ankle = _point3_from_landmark(landmarks, f"{prefix}_ANKLE")
    if hip is None or knee is None or ankle is None:
        return 0.0

    thigh_len = _vec_len(_vec_sub(knee, hip))
    shin_len = _vec_len(_vec_sub(ankle, knee))
    reach_len = _vec_len(_vec_sub(ankle, hip))
    if min(thigh_len, shin_len, reach_len) <= 1.0e-6:
        return 0.0

    length_excess = max(thigh_len - 1.9, shin_len - 1.9, reach_len - 2.8)
    length_outlier = max(0.0, min(1.0, length_excess / 2.0))
    folded_too_far = max(0.0, min(1.0, (0.25 - reach_len / max(thigh_len + shin_len, 1.0e-6)) / 0.25))
    return max(length_outlier, folded_too_far)


def _suppress_unreliable_retarget_limbs(landmarks: Dict[str, Any]) -> Dict[str, Any]:
    if not landmarks:
        return landmarks

    filtered = {str(name): dict(value) if isinstance(value, dict) else value for name, value in landmarks.items()}
    arm_threshold = _to_float(os.getenv("RGBD_RETARGET_ARM_OUTLIER_DROP_THRESHOLD"), 0.32)
    leg_threshold = _to_float(os.getenv("RGBD_RETARGET_LEG_OUTLIER_DROP_THRESHOLD"), 0.38)

    for side in ("left", "right"):
        prefix = "LEFT" if side == "left" else "RIGHT"
        arm_score = _arm_chain_outlier_score(filtered, side)
        if arm_score > arm_threshold:
            for name in (f"{prefix}_ELBOW", f"{prefix}_WRIST"):
                if name in filtered and isinstance(filtered[name], dict):
                    filtered[name] = {
                        **filtered[name],
                        "suppressed": True,
                        "suppressed_reason": "arm_depth_outlier",
                        "outlier_score": round(arm_score, 6),
                    }
                    filtered.pop(name, None)

        leg_score = _leg_chain_outlier_score(filtered, side)
        if leg_score > leg_threshold:
            for name in (f"{prefix}_KNEE", f"{prefix}_ANKLE"):
                if name in filtered and isinstance(filtered[name], dict):
                    filtered[name] = {
                        **filtered[name],
                        "suppressed": True,
                        "suppressed_reason": "leg_depth_outlier",
                        "outlier_score": round(leg_score, 6),
                    }
                    filtered.pop(name, None)

    return filtered


def _retarget_landmarks_from_pose_and_depth(
    pose_payload: Dict[str, Any],
    depth_landmarks: Dict[str, Any],
    *,
    min_visibility: float,
) -> Dict[str, Any]:
    depth_centered = _body_centered_landmarks_from_depth(depth_landmarks)
    world_landmarks = pose_payload.get("world_landmarks")
    if not isinstance(world_landmarks, dict) or not world_landmarks:
        return _suppress_unreliable_retarget_limbs(depth_centered)
    world_centered = _body_centered_landmarks_from_world(world_landmarks)
    return _suppress_unreliable_retarget_limbs(
        _merge_world_pose_for_unreliable_arms(depth_centered, world_centered)
    )


def _center_of_landmarks(landmarks: Dict[str, Any], names: Tuple[str, ...]) -> Optional[Tuple[float, float, float]]:
    points = [point for name in names if (point := _point3_from_landmark(landmarks, name)) is not None]
    if not points:
        return None
    count = float(len(points))
    return (
        sum(point[0] for point in points) / count,
        sum(point[1] for point in points) / count,
        sum(point[2] for point in points) / count,
    )


def _retarget_diagnostics(
    depth_landmarks: Dict[str, Any],
    retarget_landmarks: Dict[str, Any],
    depth_by_name: Dict[str, float],
) -> Dict[str, Any]:
    required = (
        "LEFT_SHOULDER",
        "RIGHT_SHOULDER",
        "LEFT_HIP",
        "RIGHT_HIP",
        "LEFT_KNEE",
        "RIGHT_KNEE",
        "LEFT_ANKLE",
        "RIGHT_ANKLE",
    )
    missing = [name for name in required if name not in retarget_landmarks]
    warnings: List[str] = []
    if missing:
        warnings.append(f"missing landmarks: {', '.join(missing)}")

    left_shoulder = _point3_from_landmark(retarget_landmarks, "LEFT_SHOULDER")
    right_shoulder = _point3_from_landmark(retarget_landmarks, "RIGHT_SHOULDER")
    left_hip = _point3_from_landmark(retarget_landmarks, "LEFT_HIP")
    right_hip = _point3_from_landmark(retarget_landmarks, "RIGHT_HIP")
    shoulder_center = _center_of_landmarks(retarget_landmarks, ("LEFT_SHOULDER", "RIGHT_SHOULDER"))
    hip_center = _center_of_landmarks(retarget_landmarks, ("LEFT_HIP", "RIGHT_HIP"))

    right_minus_left_x = None
    if left_shoulder and right_shoulder:
        right_minus_left_x = round(right_shoulder[0] - left_shoulder[0], 6)
        if right_minus_left_x <= 0.0:
            warnings.append("left/right shoulder order is inverted")

    shoulder_minus_hip_y = None
    if shoulder_center and hip_center:
        shoulder_minus_hip_y = round(shoulder_center[1] - hip_center[1], 6)
        if shoulder_minus_hip_y <= 0.0:
            warnings.append("shoulder center is not above hip center")

    depth_values = [float(value) for value in depth_by_name.values() if math.isfinite(float(value))]
    body_scales = [
        float(value.get("body_scale_m"))
        for value in retarget_landmarks.values()
        if isinstance(value, dict)
        and value.get("body_scale_m") is not None
        and math.isfinite(float(value.get("body_scale_m")))
    ]
    depth_valid_ratios = [
        float(value.get("depth_valid_ratio"))
        for value in depth_landmarks.values()
        if isinstance(value, dict)
        and value.get("depth_valid_ratio") is not None
        and math.isfinite(float(value.get("depth_valid_ratio")))
    ]
    depth_iqrs = [
        float(value.get("depth_iqr_m"))
        for value in depth_landmarks.values()
        if isinstance(value, dict)
        and value.get("depth_iqr_m") is not None
        and math.isfinite(float(value.get("depth_iqr_m")))
    ]

    def _relative_z(name: str, parent: str) -> Optional[float]:
        point = _point3_from_landmark(retarget_landmarks, name)
        parent_point = _point3_from_landmark(retarget_landmarks, parent)
        if point is None or parent_point is None:
            return None
        return round(point[2] - parent_point[2], 6)

    left_arm_outlier = _arm_chain_outlier_score(retarget_landmarks, "left")
    right_arm_outlier = _arm_chain_outlier_score(retarget_landmarks, "right")
    if left_arm_outlier > 0.18:
        warnings.append(f"left arm depth outlier score {left_arm_outlier:.2f}")
    if right_arm_outlier > 0.18:
        warnings.append(f"right arm depth outlier score {right_arm_outlier:.2f}")
    repaired = [
        str(name)
        for name, value in retarget_landmarks.items()
        if isinstance(value, dict) and str(value.get("source", "")).startswith("mediapipe_world_repaired")
    ]
    axis_values = {"x": [], "y": [], "z": []}
    source_counts: Dict[str, int] = {}
    sample_names = (
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
    )
    landmark_sample: Dict[str, Any] = {}
    for name, value in retarget_landmarks.items():
        if not isinstance(value, dict):
            continue
        source = str(value.get("source") or "")
        source_counts[source] = source_counts.get(source, 0) + 1
        for axis in ("x", "y", "z"):
            try:
                axis_values[axis].append(float(value.get(axis)))
            except Exception:
                pass
        if name in sample_names:
            landmark_sample[str(name)] = {
                axis: round(float(value.get(axis, 0.0)), 5)
                for axis in ("x", "y", "z")
            }

    diagnostics = {
        "retarget_coordinate_frame": next(
            (
                str(value.get("coordinate_frame"))
                for value in retarget_landmarks.values()
                if isinstance(value, dict) and value.get("coordinate_frame")
            ),
            "",
        ),
        "landmark_count": len(depth_landmarks),
        "retarget_landmark_count": len(retarget_landmarks),
        "missing_required_landmarks": missing,
        "right_shoulder_minus_left_shoulder_x": right_minus_left_x,
        "shoulder_center_minus_hip_center_y": shoulder_minus_hip_y,
        "left_wrist_forward_z": _relative_z("LEFT_WRIST", "LEFT_SHOULDER"),
        "right_wrist_forward_z": _relative_z("RIGHT_WRIST", "RIGHT_SHOULDER"),
        "left_ankle_forward_z": _relative_z("LEFT_ANKLE", "LEFT_HIP"),
        "right_ankle_forward_z": _relative_z("RIGHT_ANKLE", "RIGHT_HIP"),
        "left_arm_outlier_score": round(left_arm_outlier, 4),
        "right_arm_outlier_score": round(right_arm_outlier, 4),
        "repaired_landmarks": repaired,
        "depth_m_min": round(min(depth_values), 4) if depth_values else None,
        "depth_m_max": round(max(depth_values), 4) if depth_values else None,
        "depth_sample_valid_ratio_min": round(min(depth_valid_ratios), 4) if depth_valid_ratios else None,
        "depth_sample_valid_ratio_median": round(float(np.median(depth_valid_ratios)), 4) if depth_valid_ratios else None,
        "depth_sample_iqr_m_max": round(max(depth_iqrs), 4) if depth_iqrs else None,
        "depth_sample_iqr_m_median": round(float(np.median(depth_iqrs)), 4) if depth_iqrs else None,
        "body_scale_m": round(float(np.median(body_scales)), 4) if body_scales else None,
        "retarget_axis_ranges": {
            axis: {
                "min": round(min(values), 5) if values else None,
                "max": round(max(values), 5) if values else None,
                "abs_max": round(max(abs(item) for item in values), 5) if values else None,
            }
            for axis, values in axis_values.items()
        },
        "retarget_source_counts": source_counts,
        "retarget_landmark_sample": landmark_sample,
        "warnings": warnings,
    }
    if left_hip and right_hip:
        diagnostics["hip_width_normalized"] = round(_vec_len(_vec_sub(right_hip, left_hip)), 6)
    return diagnostics


def _debug_retarget_landmark_lines(diagnostics: Dict[str, Any]) -> Dict[str, str]:
    sample = diagnostics.get("retarget_landmark_sample")
    if not isinstance(sample, dict):
        return {}

    debug: Dict[str, str] = {}
    for name in (
        "LEFT_SHOULDER",
        "LEFT_ELBOW",
        "LEFT_WRIST",
        "RIGHT_SHOULDER",
        "RIGHT_ELBOW",
        "RIGHT_WRIST",
    ):
        value = sample.get(name)
        if not isinstance(value, dict):
            debug[name] = "missing"
            continue
        try:
            debug[name] = (
                f"x={float(value.get('x', 0.0)):.5f} "
                f"y={float(value.get('y', 0.0)):.5f} "
                f"z={float(value.get('z', 0.0)):.5f} "
                f"src={str(value.get('source', '')) or str(value.get('coordinate_frame', ''))}"
            )
        except Exception:
            debug[name] = str(value)
    return debug


def _stable_retarget_torso(landmarks: Dict[str, Any]) -> Tuple[bool, str]:
    if not isinstance(landmarks, dict):
        return False, "retarget_landmarks_missing"

    required = ("LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_HIP", "RIGHT_HIP")
    missing = [name for name in required if _point3_from_landmark(landmarks, name) is None]
    if missing:
        return False, "missing_torso_anchors:" + ",".join(missing)

    shoulder_center = _center_of_landmarks(landmarks, ("LEFT_SHOULDER", "RIGHT_SHOULDER"))
    hip_center = _center_of_landmarks(landmarks, ("LEFT_HIP", "RIGHT_HIP"))
    if shoulder_center is None or hip_center is None:
        return False, "torso_center_unavailable"

    shoulder_minus_hip_y = float(shoulder_center[1]) - float(hip_center[1])
    if shoulder_minus_hip_y <= 0.20:
        return False, f"unstable_torso_axis:shoulder_minus_hip_y={shoulder_minus_hip_y:.4f}"

    return True, "stable_torso"


def _smooth_retarget_landmarks(
    node_id: str,
    landmarks: Dict[str, Any],
    *,
    smoothing: float,
    max_delta: float,
) -> Dict[str, Any]:
    if not landmarks:
        return landmarks
    smoothing = max(0.0, min(0.95, float(smoothing)))
    max_delta = max(0.0, float(max_delta))
    if smoothing <= 0.0 and max_delta <= 0.0:
        return landmarks

    previous = _FUSION_SMOOTHING_BY_NODE.get(node_id, {})
    smoothed: Dict[str, Any] = {}
    for name, landmark in landmarks.items():
        if not isinstance(landmark, dict):
            continue
        item = dict(landmark)
        old = previous.get(str(name), {})
        for axis in ("x", "y", "z"):
            try:
                raw_value = float(landmark.get(axis))
            except Exception:
                continue
            if not math.isfinite(raw_value):
                continue
            old_value = old.get(axis)
            if old_value is None:
                item[axis] = round(raw_value, 6)
                continue
            blended = float(old_value) * smoothing + raw_value * (1.0 - smoothing)
            if max_delta > 0.0:
                delta = max(-max_delta, min(max_delta, blended - float(old_value)))
                blended = float(old_value) + delta
            item[axis] = round(blended, 6)
        smoothed[str(name)] = item

    _FUSION_SMOOTHING_BY_NODE[node_id] = {
        name: {
            axis: float(value.get(axis, 0.0))
            for axis in ("x", "y", "z")
            if isinstance(value, dict)
        }
        for name, value in smoothed.items()
        if isinstance(value, dict)
    }
    return smoothed or landmarks


def _temporal_landmark_diagnostics(
    previous_frame: Dict[str, Any] | None,
    current_landmarks: Dict[str, Any],
) -> Dict[str, Any]:
    previous_landmarks = (
        previous_frame.get("landmarks")
        if isinstance(previous_frame, dict) and isinstance(previous_frame.get("landmarks"), dict)
        else {}
    )
    if not previous_landmarks or not current_landmarks:
        return {
            "matched_landmarks": 0,
            "max_delta": None,
            "median_delta": None,
            "large_jump_count": 0,
            "large_jump_landmarks": [],
        }

    deltas: List[Tuple[str, float]] = []
    for name in sorted(set(previous_landmarks.keys()).intersection(current_landmarks.keys())):
        current_point = _point3_from_landmark(current_landmarks, str(name))
        previous_point = _point3_from_landmark(previous_landmarks, str(name))
        if current_point is None or previous_point is None:
            continue
        deltas.append((str(name), _vec_len(_vec_sub(current_point, previous_point))))

    values = [delta for _, delta in deltas]
    large = [(name, delta) for name, delta in deltas if delta > 0.35]
    return {
        "matched_landmarks": len(deltas),
        "max_delta": round(max(values), 5) if values else None,
        "median_delta": round(float(np.median(values)), 5) if values else None,
        "large_jump_count": len(large),
        "large_jump_landmarks": [
            {"name": name, "delta": round(delta, 5)}
            for name, delta in sorted(large, key=lambda item: item[1], reverse=True)[:8]
        ],
    }


def _usable_retarget_landmarks(landmarks: Dict[str, Any]) -> bool:
    if not isinstance(landmarks, dict):
        return False
    if len(landmarks) < 4:
        return False

    names = set(str(name) for name in landmarks.keys())
    torso_count = len({"LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_HIP", "RIGHT_HIP"}.intersection(names))
    upper_count = len(
        {
            "LEFT_SHOULDER",
            "RIGHT_SHOULDER",
            "LEFT_ELBOW",
            "RIGHT_ELBOW",
            "LEFT_WRIST",
            "RIGHT_WRIST",
        }.intersection(names)
    )
    lower_count = len(
        {
            "LEFT_HIP",
            "RIGHT_HIP",
            "LEFT_KNEE",
            "RIGHT_KNEE",
            "LEFT_ANKLE",
            "RIGHT_ANKLE",
        }.intersection(names)
    )
    required_count = len(REQUIRED_RETARGET_LANDMARKS.intersection(names))
    return torso_count >= 3 or upper_count >= 4 or lower_count >= 4 or required_count >= 4


def _empty_rgbd_motion(
    *,
    node_id: str,
    prompt: str,
    image_value: Any,
    depth_units: np.ndarray,
    diagnostics: Dict[str, Any],
    message: str,
) -> Dict[str, Any]:
    _FUSION_HISTORY_BY_NODE.pop(node_id, None)
    _FUSION_SMOOTHING_BY_NODE.pop(node_id, None)

    try:
        image_array = _image_array_from_value(image_value) if image_value else np.zeros(
            (int(depth_units.shape[0]), int(depth_units.shape[1]), 3),
            dtype=np.uint8,
        )
        image = _array_to_jpeg_data_uri(image_array)
    except Exception:
        image = ""

    timestamp = time.time()
    motion = {
        "type": "rgbd_pose_motion_trace",
        "source": "realsense_d435i_mediapipe_rgbd",
        "label": "stop",
        "prompt": prompt,
        "video": {
            "fps": 0,
            "frame_count": 0,
            "duration_sec": None,
        },
        "sampling": {
            "sampled_frames": 0,
            "retarget_coordinates": "body_centered_3d_from_realsense_aligned_depth",
            "diagnostics": diagnostics,
        },
        "summary": {
            "primary_skill": "stop",
            "confidence": 0.0,
            "heuristic_labels": ["stop", "no_valid_rgbd_pose"],
        },
        "frames": [],
        "invalid_current_frame": True,
    }
    return {
        "ok": False,
        "type": "rgbd_pose_fusion_result",
        "image": image,
        "pose3d": {
            "type": "rgbd_pose3d",
            "landmarks": {},
            "retarget_landmarks": {},
            "landmark_count": 0,
            "retarget_landmark_count": 0,
            "diagnostics": diagnostics,
            "timestamp": timestamp,
        },
        "skeleton": {
            "type": "rgbd_pose_skeleton",
            "landmarks": {},
            "retarget_landmarks": {},
            "features": {},
            "diagnostics": diagnostics,
            "timestamp": timestamp,
            "camera_frame": "realsense_color_optical_frame",
        },
        "motion": motion,
        "skill": "stop",
        "summary": motion["summary"],
        "diagnostics": diagnostics,
        "message": message,
    }


def exec_rgbd_pose_fusion(
    node: Dict[str, Any],
    context: Dict[str, Any],
    edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    props = _node_props(node)
    inputs = _incoming_values(node["id"], edges, context)
    prompt = _text(inputs.get("prompt") or props.get("prompt"))

    pose_payload = inputs.get("pose") or props.get("pose")
    depth_payload = inputs.get("depth") or props.get("depth")
    image_value = inputs.get("image") or props.get("image")

    if not isinstance(pose_payload, dict):
        raise ValueError("RGB-D Pose Fusion requires a pose JSON input")
    if not isinstance(depth_payload, dict):
        raise ValueError("RGB-D Pose Fusion requires a depth JSON input")

    depth_units, normalized_depth_payload = _depth_array_from_payload(depth_payload)
    min_visibility = _to_float(props.get("minPoseVisibility"), 0.35)
    radius = max(0, _to_int(props.get("depthSampleRadius"), 3))
    landmarks3d, depth_by_name = _landmarks_3d_from_depth(
        pose_payload,
        depth_units,
        normalized_depth_payload,
        radius=radius,
        min_visibility=min_visibility,
    )
    retarget_landmarks = _retarget_landmarks_from_pose_and_depth(
        pose_payload,
        landmarks3d,
        min_visibility=min_visibility,
    )
    node_id = str(node.get("id", "rgbd_pose_fusion"))
    retarget_landmarks = _smooth_retarget_landmarks(
        node_id,
        retarget_landmarks,
        smoothing=_to_float(props.get("landmarkSmoothing"), 0.0),
        max_delta=_to_float(props.get("landmarkMaxDelta"), 0.0),
    )
    diagnostics = _retarget_diagnostics(landmarks3d, retarget_landmarks, depth_by_name)
    require_stable_torso = _to_bool(props.get("requireStableTorso"), False)
    stable_torso, stable_torso_reason = _stable_retarget_torso(retarget_landmarks)
    diagnostics["stable_torso"] = stable_torso
    diagnostics["stable_torso_reason"] = stable_torso_reason
    history = _FUSION_HISTORY_BY_NODE.setdefault(node_id, [])
    temporal_diagnostics = _temporal_landmark_diagnostics(
        history[-1] if history else None,
        retarget_landmarks,
    )
    diagnostics["temporal_landmark_delta"] = temporal_diagnostics
    if int(temporal_diagnostics.get("large_jump_count") or 0) > 0:
        diagnostics.setdefault("warnings", []).append(
            f"large temporal landmark jumps: {temporal_diagnostics.get('large_jump_count')}"
        )
    hold_large_jumps = _to_bool(props.get("holdLargeJumps"), True)
    if hold_large_jumps and history and int(temporal_diagnostics.get("large_jump_count") or 0) > 0:
        previous_landmarks = history[-1].get("landmarks") if isinstance(history[-1], dict) else None
        if isinstance(previous_landmarks, dict) and _usable_retarget_landmarks(previous_landmarks):
            held_reason = f"large_temporal_jump_count={temporal_diagnostics.get('large_jump_count')}"
            retarget_landmarks = {
                str(name): dict(value) if isinstance(value, dict) else value
                for name, value in previous_landmarks.items()
            }
            diagnostics = _retarget_diagnostics(landmarks3d, retarget_landmarks, depth_by_name)
            diagnostics["temporal_landmark_delta"] = temporal_diagnostics
            diagnostics["held_previous_frame"] = True
            diagnostics["held_previous_frame_reason"] = held_reason
            diagnostics.setdefault("warnings", []).append(f"held previous RGB-D pose: {held_reason}")
            stable_torso, stable_torso_reason = _stable_retarget_torso(retarget_landmarks)
            diagnostics["stable_torso"] = stable_torso
            diagnostics["stable_torso_reason"] = stable_torso_reason
    if require_stable_torso and not stable_torso:
        diagnostics.setdefault("warnings", []).append(
            f"unstable torso coordinate frame: {stable_torso_reason}"
        )

    if not _usable_retarget_landmarks(retarget_landmarks):
        diagnostics = dict(diagnostics)
        diagnostics["invalid_current_frame"] = True
        diagnostics["invalid_reason"] = "insufficient_current_rgbd_pose_landmarks"
        return _empty_rgbd_motion(
            node_id=node_id,
            prompt=prompt,
            image_value=image_value,
            depth_units=depth_units,
            diagnostics=diagnostics,
            message=(
                "RGB-D Pose Fusion did not produce enough current-frame landmarks; "
                "cleared motion history and emitted stop."
            ),
        )

    if image_value:
        image_array = _image_array_from_value(image_value)
    else:
        image_array = np.zeros((int(depth_units.shape[0]), int(depth_units.shape[1]), 3), dtype=np.uint8)

    fused_image = _draw_pose_overlay(
        image_array,
        pose_payload.get("landmarks", {}),
        min_visibility=min_visibility,
        label=f"RGB-D fused {len(landmarks3d)}",
        depth_by_name=depth_by_name,
    )

    timestamp = time.time()
    g1_named_targets = landmarks_to_g1_named_targets(retarget_landmarks)
    g1_action = (
        g1_action_payload_from_named_targets(
            g1_named_targets,
            source="realsense_d435i_mediapipe_rgbd",
        )
        if g1_named_targets
        else {}
    )
    frame = {
        "frame_index": len(history),
        "timestamp_sec": timestamp,
        "visible_landmarks": len(retarget_landmarks),
        "landmarks": retarget_landmarks,
        "depth_landmarks": landmarks3d,
        "image_landmarks": pose_payload.get("landmarks", {}),
        "world_landmarks": pose_payload.get("world_landmarks", {}),
        "features": frame_features(retarget_landmarks) if retarget_landmarks else {},
        "g1_named_targets": dict(g1_named_targets),
        "joint_target_map": dict(g1_named_targets),
        "named_joint_targets": dict(g1_named_targets),
    }

    history.append(frame)
    max_frames = max(1, _to_int(props.get("maxMotionFrames"), 40))
    if len(history) > max_frames:
        del history[: len(history) - max_frames]

    label = _text(props.get("motionLabel") or props.get("poseLabel"))
    summary = summarize_motion(history, label)
    skill = _text(summary.get("primary_skill")) or label or "unknown"
    motion = {
        "type": "rgbd_pose_motion_trace",
        "source": "realsense_d435i_mediapipe_rgbd",
        "label": label,
        "prompt": prompt,
        "video": {
            "fps": 0,
            "frame_count": len(history),
            "width": int(image_array.shape[1]),
            "height": int(image_array.shape[0]),
            "duration_sec": None,
        },
        "sampling": {
            "sampled_frames": len(history),
            "min_visibility": min_visibility,
            "depth_sample_radius": radius,
            "retarget_coordinates": "body_centered_3d_from_realsense_aligned_depth",
            "diagnostics": diagnostics,
        },
        "summary": summary,
        "frames": list(history),
        "g1_named_targets": dict(g1_named_targets),
        "joint_target_map": dict(g1_named_targets),
    }

    skeleton = {
        "type": "rgbd_pose_skeleton",
        "landmarks": landmarks3d,
        "retarget_landmarks": retarget_landmarks,
        "features": frame.get("features", {}),
        "g1_named_targets": dict(g1_named_targets),
        "joint_target_map": dict(g1_named_targets),
        "diagnostics": diagnostics,
        "timestamp": timestamp,
        "camera_frame": "realsense_color_optical_frame",
    }

    return {
        "ok": bool(landmarks3d),
        "type": "rgbd_pose_fusion_result",
        "debug_retarget_landmark_sample": _debug_retarget_landmark_lines(diagnostics),
        "image": fused_image,
        "pose3d": {
            "type": "rgbd_pose3d",
            "landmarks": landmarks3d,
            "retarget_landmarks": retarget_landmarks,
            "landmark_count": len(landmarks3d),
            "retarget_landmark_count": len(retarget_landmarks),
            "g1_named_targets": dict(g1_named_targets),
            "joint_target_map": dict(g1_named_targets),
            "diagnostics": diagnostics,
            "timestamp": timestamp,
        },
        "skeleton": skeleton,
        "motion": motion,
        "action": g1_action,
        "g1_action": g1_action,
        "g1_named_targets": dict(g1_named_targets),
        "joint_target_map": dict(g1_named_targets),
        "skill": skill,
        "summary": summary,
        "diagnostics": diagnostics,
        "message": f"Fused {len(landmarks3d)} pose landmarks with aligned depth; G1 targets={len(g1_named_targets)}.",
    }
