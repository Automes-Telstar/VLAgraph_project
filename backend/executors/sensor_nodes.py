from __future__ import annotations

import base64
import json
import math
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple

import requests


def _pick_first(inputs: Dict[str, Any], *keys: str):
    if not isinstance(inputs, dict):
        return None

    for key in keys:
        if key in inputs and inputs[key] not in (None, ""):
            return inputs[key]
    return None


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
            if not isinstance(source_payload, dict):
                continue
            if source_handle not in source_payload:
                continue
            value = source_payload[source_handle]

        key = target_handle or source_handle or source_id
        result[key] = value

    return result


def _node_props(node: Dict[str, Any]) -> Dict[str, Any]:
    data = (node or {}).get("data") or {}
    if not isinstance(data, dict):
        return {}

    props = data.get("props")
    if isinstance(props, dict) and props:
        merged = dict(props)
        for key, value in data.items():
            if key != "props" and key not in merged:
                merged[key] = value
        return merged

    return data


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_headers(value: Any) -> Dict[str, str]:
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items() if v is not None}

    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items() if v is not None}
        except json.JSONDecodeError:
            return {}

    return {}


def _to_json_body(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value

    if isinstance(value, str) and value.strip():
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {"raw": value}

    return None


def _request_remote(
    *,
    url: str,
    method: str,
    headers: Dict[str, str],
    json_body: Any,
    timeout_sec: float,
    stream: bool = False,
) -> requests.Response:
    request_kwargs: Dict[str, Any] = {
        "method": method.upper() or "GET",
        "url": url,
        "headers": headers or None,
        "timeout": timeout_sec,
        "stream": stream,
    }

    if method.upper() != "GET" and json_body is not None:
        request_kwargs["json"] = json_body

    response = requests.request(**request_kwargs)
    response.raise_for_status()
    return response


def _extract_jpeg_frame_from_mjpeg_stream(response: requests.Response) -> bytes:
    buffer = bytearray()

    for chunk in response.iter_content(chunk_size=4096):
        if not chunk:
            continue

        buffer.extend(chunk)
        start = buffer.find(b"\xff\xd8")
        end = buffer.find(b"\xff\xd9", start + 2 if start >= 0 else 0)

        if start >= 0 and end >= 0:
            return bytes(buffer[start : end + 2])

        if len(buffer) > 8 * 1024 * 1024:
            raise ValueError("MJPEG stream exceeded 8MB before a full JPEG frame was found")

    raise ValueError("MJPEG stream ended before a full JPEG frame was found")


def _extract_jpeg_frame_from_rtsp(
    *,
    url: str,
    timeout_sec: float,
    ffmpeg_path: str,
    rtsp_transport: str,
) -> bytes:
    binary = shutil.which(ffmpeg_path) if ffmpeg_path else shutil.which("ffmpeg")
    if not binary:
        raise ValueError(
            "RTSP capture requires ffmpeg to be installed and available on PATH"
        )

    transport = rtsp_transport.strip().lower() or "tcp"
    if transport not in {"tcp", "udp"}:
        transport = "tcp"

    # ffmpeg timeout-related values use microseconds for network I/O options.
    network_timeout_us = max(int(timeout_sec * 1_000_000), 1_000_000)
    command = [
        binary,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-rtsp_transport",
        transport,
        "-rw_timeout",
        str(network_timeout_us),
        "-i",
        url,
        "-frames:v",
        "1",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "pipe:1",
    ]

    try:
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=max(timeout_sec + 2.0, 5.0),
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"RTSP frame capture timed out after {timeout_sec:.1f}s") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="ignore").strip()
        raise ValueError(f"RTSP frame capture failed: {stderr or 'unknown ffmpeg error'}") from exc

    if not result.stdout:
        raise ValueError("RTSP frame capture returned no image bytes")

    return result.stdout


def _data_uri_from_bytes(raw: bytes, content_type: str | None) -> str:
    mime = (content_type or "image/jpeg").split(";")[0].strip() or "image/jpeg"
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _extract_image_from_json(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""

    for key in ("image", "image_url", "data_url", "frame", "snapshot"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for key in ("image_base64", "frame_base64", "base64"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            if value.startswith("data:") or value.startswith("base64:"):
                return value

            content_type = str(
                payload.get("content_type")
                or payload.get("mime_type")
                or "image/jpeg"
            )
            return f"data:{content_type};base64,{value.strip()}"

    return ""


def _is_image_payload_not_ready(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False

    if payload.get("ok") is False:
        return True

    message = str(payload.get("message") or payload.get("error") or "").strip().lower()
    return message in {"no image", "image field missing", "image not ready", "not ready"}


def _resolve_remote_image_url(remote_image_value: Any) -> Optional[str]:
    if remote_image_value is None:
        return None

    if isinstance(remote_image_value, str):
        stripped = remote_image_value.strip()
        return stripped or None

    if isinstance(remote_image_value, dict):
        for key in ("remoteImageUrl", "remote_image_url", "image_url", "url", "imageUrl", "frame_url", "snapshot_url"):
            value = remote_image_value.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return None


def _resolve_remote_lidar_url(remote_lidar_value: Any) -> Optional[str]:
    if remote_lidar_value is None:
        return None

    if isinstance(remote_lidar_value, str):
        stripped = remote_lidar_value.strip()
        return stripped or None

    if isinstance(remote_lidar_value, dict):
        for key in ("remoteLidarUrl", "remote_lidar_url", "lidar_url", "url", "lidarUrl", "scan_url"):
            value = remote_lidar_value.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return None


def _fetch_remote_image(
    *,
    url: str,
    method: str,
    headers: Dict[str, str],
    json_body: Any,
    timeout_sec: float,
    transport: str,
    ffmpeg_path: str,
    rtsp_transport: str,
) -> Tuple[str, Dict[str, Any]]:
    transport_name = transport.strip().lower() or "snapshot"

    if transport_name == "rtsp":
        frame = _extract_jpeg_frame_from_rtsp(
            url=url,
            timeout_sec=timeout_sec,
            ffmpeg_path=ffmpeg_path,
            rtsp_transport=rtsp_transport,
        )
        return _data_uri_from_bytes(frame, "image/jpeg"), {
            "url": url,
            "method": "RTSP",
            "response_type": "rtsp",
            "content_type": "image/jpeg",
            "size_bytes": len(frame),
            "transport": "rtsp",
            "rtsp_transport": rtsp_transport.strip().lower() or "tcp",
            "ffmpeg_path": ffmpeg_path or "ffmpeg",
        }

    if transport_name == "mjpeg":
        response = _request_remote(
            url=url,
            method=method,
            headers=headers,
            json_body=json_body,
            timeout_sec=timeout_sec,
            stream=True,
        )
        try:
            frame = _extract_jpeg_frame_from_mjpeg_stream(response)
        finally:
            response.close()

        return _data_uri_from_bytes(frame, "image/jpeg"), {
            "url": url,
            "method": method.upper(),
            "response_type": "mjpeg",
            "content_type": "image/jpeg",
            "size_bytes": len(frame),
            "transport": "mjpeg",
        }

    response = _request_remote(
        url=url,
        method=method,
        headers=headers,
        json_body=json_body,
        timeout_sec=timeout_sec,
    )
    content_type = response.headers.get("content-type", "")

    if "json" in content_type:
        payload = response.json()
        image_value = _extract_image_from_json(payload)
        if not image_value:
            return "", {
                "url": url,
                "method": method.upper(),
                "response_type": "json",
                "content_type": content_type,
                "transport": "snapshot",
                "ready": False,
                "error": str(
                    payload.get("message")
                    or payload.get("error")
                    or (
                        "Remote image is not ready"
                        if _is_image_payload_not_ready(payload)
                        else "Remote image endpoint returned JSON without an image field"
                    )
                ),
                "raw": payload,
            }

        return image_value, {
            "url": url,
            "method": method.upper(),
            "response_type": "json",
            "content_type": content_type,
            "transport": "snapshot",
            "ready": True,
        }

    return _data_uri_from_bytes(response.content, content_type), {
        "url": url,
        "method": method.upper(),
        "response_type": "binary",
        "content_type": content_type or "application/octet-stream",
        "size_bytes": len(response.content),
        "transport": "snapshot",
    }


def _fetch_remote_lidar(
    *,
    url: str,
    method: str,
    headers: Dict[str, str],
    json_body: Any,
    timeout_sec: float,
) -> Tuple[Any, Dict[str, Any]]:
    response = _request_remote(
        url=url,
        method=method,
        headers=headers,
        json_body=json_body,
        timeout_sec=timeout_sec,
    )
    content_type = response.headers.get("content-type", "")

    if "json" in content_type:
        return response.json(), {
            "url": url,
            "method": method.upper(),
            "response_type": "json",
            "content_type": content_type,
        }

    raw_text = response.text.strip()
    if raw_text:
        try:
            parsed = json.loads(raw_text)
            return parsed, {
                "url": url,
                "method": method.upper(),
                "response_type": "text-json",
                "content_type": content_type or "text/plain",
            }
        except json.JSONDecodeError:
            pass

    return {
        "raw_text": raw_text,
        "content_type": content_type or "text/plain",
        "size_bytes": len(response.content),
    }, {
        "url": url,
        "method": method.upper(),
        "response_type": "text",
        "content_type": content_type or "text/plain",
        "size_bytes": len(response.content),
    }


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0
    return True


def _to_point_xyz(point: Any) -> list[float] | None:
    if isinstance(point, dict):
        if "position" in point:
            nested = _to_point_xyz(point.get("position"))
            if nested is not None:
                return nested

        if "x" not in point or "y" not in point:
            for key in ("xyz", "point"):
                nested = _to_point_xyz(point.get(key))
                if nested is not None:
                    return nested
            return None
        try:
            x = float(point.get("x", 0.0))
            y = float(point.get("y", 0.0))
            z = float(point.get("z", 0.0))
        except (TypeError, ValueError):
            return None
        return [x, y, z]

    if isinstance(point, (list, tuple)) and len(point) >= 2:
        try:
            x = float(point[0])
            y = float(point[1])
            z = float(point[2]) if len(point) >= 3 else 0.0
        except (TypeError, ValueError):
            return None
        return [x, y, z]

    return None


def _points_from_flat(values: Any) -> list[list[float]]:
    if not isinstance(values, list):
        return []

    normalized_points: list[list[float]] = []
    for index in range(0, len(values) - 2, 3):
        try:
            x = float(values[index])
            y = float(values[index + 1])
            z = float(values[index + 2])
        except (TypeError, ValueError):
            continue
        normalized_points.append([x, y, z])

    return normalized_points


def _summarize_points(points: list[list[float]], obstacle_distance: float) -> Dict[str, Any]:
    if not points:
        return {
            "nearest_distance": None,
            "nearest_point": None,
            "centroid": None,
            "bounds": None,
            "obstacle_count": 0,
        }

    min_distance = float("inf")
    max_distance = 0.0
    nearest_point: list[float] | None = None
    obstacle_count = 0
    sums = [0.0, 0.0, 0.0]
    mins = [float("inf"), float("inf"), float("inf")]
    maxs = [float("-inf"), float("-inf"), float("-inf")]

    for point in points:
        x, y, z = point[:3]
        distance = math.sqrt(x * x + y * y + z * z)
        if distance < min_distance:
            min_distance = distance
            nearest_point = point
        max_distance = max(max_distance, distance)
        if distance <= obstacle_distance:
            obstacle_count += 1

        for axis, value in enumerate((x, y, z)):
            sums[axis] += value
            mins[axis] = min(mins[axis], value)
            maxs[axis] = max(maxs[axis], value)

    count = float(len(points))
    return {
        "nearest_distance": min_distance,
        "nearest_point": nearest_point,
        "max_distance": max_distance,
        "centroid": [sums[0] / count, sums[1] / count, sums[2] / count],
        "bounds": {
            "min": mins,
            "max": maxs,
        },
        "obstacle_count": obstacle_count,
        "obstacle_distance": obstacle_distance,
    }


def _normalize_pointcloud(points: Any, obstacle_distance: float = 1.0) -> Dict[str, Any]:
    if not isinstance(points, list):
        raise ValueError("LiDAR pointcloud payload must be a list")

    normalized_points: list[list[float]] = []
    for point in points:
        xyz = _to_point_xyz(point)
        if xyz is not None:
            normalized_points.append(xyz)

    return {
        "format": "pointcloud_xyz",
        "point_count": len(normalized_points),
        "points": normalized_points,
        "summary": _summarize_points(normalized_points, obstacle_distance),
    }


def _normalize_laser_scan(payload: Dict[str, Any], obstacle_distance: float = 1.0) -> Dict[str, Any]:
    ranges = payload.get("ranges")
    if not isinstance(ranges, list):
        raise ValueError("laser_scan payload requires a ranges list")

    angle_min = _to_float(payload.get("angle_min"), 0.0)
    angle_increment = payload.get("angle_increment")
    if angle_increment is None:
        angle_max = _to_float(payload.get("angle_max"), angle_min)
        if len(ranges) > 1:
            angle_increment = (angle_max - angle_min) / float(len(ranges) - 1)
        else:
            angle_increment = 0.0

    increment = _to_float(angle_increment, 0.0)
    range_min = _to_float(payload.get("range_min"), 0.0)
    range_max = _to_float(payload.get("range_max"), float("inf"))

    points: list[list[float]] = []
    valid_ranges: list[float] = []
    nearest_range: float | None = None
    nearest_angle: float | None = None
    nearest_point: list[float] | None = None
    invalid_count = 0
    obstacle_count = 0
    sectors = {
        "front": {"min_range": None, "count": 0},
        "left": {"min_range": None, "count": 0},
        "right": {"min_range": None, "count": 0},
        "rear": {"min_range": None, "count": 0},
    }

    for index, raw_range in enumerate(ranges):
        try:
            distance = float(raw_range)
        except (TypeError, ValueError):
            invalid_count += 1
            continue

        if math.isnan(distance) or math.isinf(distance):
            invalid_count += 1
            continue
        if distance < range_min or distance > range_max:
            invalid_count += 1
            continue

        angle = angle_min + increment * index
        point = [
            distance * math.cos(angle),
            distance * math.sin(angle),
            0.0,
        ]
        points.append(point)
        valid_ranges.append(distance)

        if nearest_range is None or distance < nearest_range:
            nearest_range = distance
            nearest_angle = angle
            nearest_point = point

        if distance <= obstacle_distance:
            obstacle_count += 1

        abs_angle = abs(math.atan2(math.sin(angle), math.cos(angle)))
        if abs_angle <= math.radians(30.0):
            sector_name = "front"
        elif abs_angle >= math.radians(150.0):
            sector_name = "rear"
        elif angle > 0:
            sector_name = "left"
        else:
            sector_name = "right"

        sector = sectors[sector_name]
        sector["count"] += 1
        current_min = sector["min_range"]
        sector["min_range"] = distance if current_min is None else min(current_min, distance)

    mean_range = sum(valid_ranges) / len(valid_ranges) if valid_ranges else None

    return {
        "format": "laser_scan",
        "point_count": len(points),
        "points": points,
        "scan": {
            "angle_min": angle_min,
            "angle_increment": increment,
            "range_min": range_min,
            "range_max": range_max,
            "sample_count": len(ranges),
        },
        "summary": {
            "valid_count": len(valid_ranges),
            "invalid_count": invalid_count,
            "nearest_range": nearest_range,
            "nearest_angle": nearest_angle,
            "nearest_point": nearest_point,
            "mean_range": mean_range,
            "obstacle_count": obstacle_count,
            "obstacle_distance": obstacle_distance,
            "sectors": sectors,
        },
    }


def _extract_frame_id(payload: Dict[str, Any]) -> str:
    header = payload.get("header")
    if isinstance(header, dict):
        frame_id = str(header.get("frame_id") or "").strip()
        if frame_id:
            return frame_id
    return str(payload.get("frame_id", "") or "")


def _extract_lidar_timestamp(payload: Dict[str, Any]) -> Any:
    header = payload.get("header")
    if isinstance(header, dict) and header.get("stamp") is not None:
        return header.get("stamp")
    return payload.get("timestamp") or payload.get("stamp") or payload.get("unity_timestamp")


def _unwrap_lidar_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload

    for key in ("lidar", "scan"):
        value = payload.get(key)
        if isinstance(value, (dict, list)):
            merged = value
            if isinstance(value, dict):
                merged = dict(value)
                for meta_key in ("frame_id", "timestamp", "stamp", "unity_timestamp", "client_id", "source"):
                    if meta_key not in merged and meta_key in payload:
                        merged[meta_key] = payload.get(meta_key)
            return merged

    raw = payload.get("raw")
    if isinstance(raw, dict) and ("ranges" in raw or "points" in raw or "points_flat" in raw):
        merged = dict(raw)
        for meta_key in ("frame_id", "timestamp", "stamp", "unity_timestamp", "client_id", "source"):
            if meta_key not in merged and meta_key in payload:
                merged[meta_key] = payload.get(meta_key)
        return merged

    return payload


def _normalize_lidar(payload: Any, lidar_format: str, obstacle_distance: float = 1.0) -> Dict[str, Any]:
    format_name = lidar_format.strip().lower() or "auto"
    payload = _unwrap_lidar_payload(payload)

    if isinstance(payload, dict):
        if payload.get("ok") is False and "ranges" not in payload and "points" not in payload:
            return {
                "format": "error",
                "point_count": 0,
                "error": str(payload.get("message") or payload.get("error") or "LiDAR payload not ready"),
                "raw": payload,
            }

        if format_name in {"laser_scan", "scan"} or "ranges" in payload:
            normalized = _normalize_laser_scan(payload, obstacle_distance)
            normalized["frame_id"] = _extract_frame_id(payload)
            normalized["timestamp"] = _extract_lidar_timestamp(payload)
            normalized["source"] = str(payload.get("source") or "")
            normalized["origin"] = payload.get("origin")
            normalized["rotation"] = payload.get("rotation")
            return normalized

        if "points_flat" in payload:
            normalized = _normalize_pointcloud(
                _points_from_flat(payload.get("points_flat")),
                obstacle_distance,
            )
            normalized["format"] = "pointcloud_xyz_flat"
            normalized["frame_id"] = _extract_frame_id(payload)
            normalized["timestamp"] = _extract_lidar_timestamp(payload)
            normalized["source"] = str(payload.get("source") or "")
            return normalized

        for key in ("points", "pointcloud", "point_cloud", "xyz"):
            if key in payload:
                normalized = _normalize_pointcloud(payload[key], obstacle_distance)
                normalized["frame_id"] = _extract_frame_id(payload)
                normalized["timestamp"] = _extract_lidar_timestamp(payload)
                normalized["source"] = str(payload.get("source") or "")
                return normalized

        return {
            "format": "raw_json",
            "point_count": 0,
            "frame_id": _extract_frame_id(payload),
            "timestamp": _extract_lidar_timestamp(payload),
            "raw": payload,
        }

    if isinstance(payload, list):
        normalized = _normalize_pointcloud(payload, obstacle_distance)
        normalized["frame_id"] = ""
        normalized["timestamp"] = None
        return normalized

    return {
        "format": "raw",
        "point_count": 0,
        "raw": payload,
    }


def _lidar_ready(value: Any) -> bool:
    if not isinstance(value, dict):
        return _has_value(value)

    if value.get("format") == "error" or value.get("ok") is False:
        return False

    if int(value.get("point_count", 0) or 0) > 0:
        return True

    if value.get("format") in {"raw_json", "raw"}:
        raw = value.get("raw")
        return _has_value(raw) and not (isinstance(raw, dict) and raw.get("ok") is False)

    return _has_value(value)


def exec_sensor_input(
    node: Dict[str, Any],
    context: Dict[str, Any],
    edges: list[Dict[str, Any]],
) -> Dict[str, Any]:
    props = _node_props(node)

    node_type = str(node.get("type", "") or "").strip()
    source_mode = {
        "sensor_camera": "camera",
        "sensor_remote_image": "remote_image",
        "sensor_remote_lidar": "remote_lidar",
        "sensor_fused": "fused",
    }.get(node_type, str(props.get("sourceMode", "camera")).strip().lower() or "camera")
    remote_method = str(props.get("remoteMethod", "GET")).strip().upper() or "GET"
    remote_headers = _to_headers(props.get("remoteHeaders"))
    remote_body = _to_json_body(props.get("remoteBody"))
    timeout_sec = _to_float(props.get("requestTimeoutSec"), 10.0)
    remote_image_transport = str(props.get("remoteImageTransport", "snapshot")).strip().lower() or "snapshot"
    rtsp_transport = str(props.get("rtspTransport", "tcp")).strip().lower() or "tcp"
    ffmpeg_path = str(props.get("ffmpegPath", "ffmpeg")).strip() or "ffmpeg"
    lidar_format = str(props.get("lidarFormat", "auto")).strip().lower() or "auto"
    lidar_obstacle_distance = max(0.0, _to_float(props.get("lidarObstacleDistance"), 1.0))

    captured_frame = str(props.get("capturedFrame", "") or "").strip()
    last_captured_at = str(props.get("lastCapturedAt", "") or "").strip()

    image_output = ""
    lidar_output: Any = {}
    raw_lidar_output: Any = None
    image_meta: Dict[str, Any] = {}
    lidar_meta: Dict[str, Any] = {}

    inputs = _incoming_values(node["id"], edges, context)
    remote_image_url = _resolve_remote_image_url(
        _pick_first(
            inputs,
            "remoteImageUrl",
            "remote_image_url",
            "image_url",
            "url",
            "imageUrl",
        )
    )
    if not remote_image_url:
        remote_image_url = str(props.get("remoteImageUrl", "") or "").strip()
    remote_lidar_url = _resolve_remote_lidar_url(
        _pick_first(
            inputs,
            "remoteLidarUrl",
            "remote_lidar_url",
            "lidar_url",
            "url",
            "lidarUrl",
        )
    )
    if not remote_lidar_url:
        remote_lidar_url = str(props.get("remoteLidarUrl", "") or "").strip()
    lidar_sample = props.get("lidarSample", {})

    if source_mode == "camera":
        if not captured_frame:
            raise ValueError("camera mode requires a capturedFrame from the browser camera")

        image_output = captured_frame
        image_meta = {
            "source": "camera",
            "captured_at": last_captured_at,
        }

    elif source_mode == "remote_image":
        if not remote_image_url:
            raise ValueError("remote_image mode requires remoteImageUrl")

        image_output, image_meta = _fetch_remote_image(
            url=remote_image_url,
            method=remote_method,
            headers=remote_headers,
            json_body=remote_body,
            timeout_sec=timeout_sec,
            transport=remote_image_transport,
            ffmpeg_path=ffmpeg_path,
            rtsp_transport=rtsp_transport,
        )
        image_meta["source"] = "remote_image"

    elif source_mode == "remote_lidar":
        if remote_lidar_url:
            lidar_payload, lidar_meta = _fetch_remote_lidar(
                url=remote_lidar_url,
                method=remote_method,
                headers=remote_headers,
                json_body=remote_body,
                timeout_sec=timeout_sec,
            )
            raw_lidar_output = lidar_payload
            lidar_output = _normalize_lidar(lidar_payload, lidar_format, lidar_obstacle_distance)
        else:
            if not _has_value(lidar_sample):
                raise ValueError("remote_lidar mode requires remoteLidarUrl or lidarSample")
            raw_lidar_output = lidar_sample
            lidar_output = _normalize_lidar(lidar_sample, lidar_format, lidar_obstacle_distance)
            lidar_meta = {"source": "inline_sample"}

        lidar_meta["source"] = lidar_meta.get("source", "remote_lidar")

    elif source_mode == "fused":
        if captured_frame:
            image_output = captured_frame
            image_meta = {
                "source": "camera",
                "captured_at": last_captured_at,
            }
        elif remote_image_url:
            image_output, image_meta = _fetch_remote_image(
                url=remote_image_url,
                method=remote_method,
                headers=remote_headers,
                json_body=remote_body,
                timeout_sec=timeout_sec,
                transport=remote_image_transport,
                ffmpeg_path=ffmpeg_path,
                rtsp_transport=rtsp_transport,
            )
            image_meta["source"] = "remote_image"

        if remote_lidar_url:
            lidar_payload, lidar_meta = _fetch_remote_lidar(
                url=remote_lidar_url,
                method=remote_method,
                headers=remote_headers,
                json_body=remote_body,
                timeout_sec=timeout_sec,
            )
            raw_lidar_output = lidar_payload
            lidar_output = _normalize_lidar(lidar_payload, lidar_format, lidar_obstacle_distance)
            lidar_meta["source"] = "remote_lidar"
        elif _has_value(lidar_sample):
            raw_lidar_output = lidar_sample
            lidar_output = _normalize_lidar(lidar_sample, lidar_format, lidar_obstacle_distance)
            lidar_meta = {"source": "inline_sample"}

        if not image_output and not _lidar_ready(lidar_output):
            raise ValueError(
                "fused mode requires a capturedFrame or remoteImageUrl, and/or remoteLidarUrl"
            )

    else:
        raise ValueError(f"Unsupported sensor sourceMode: {source_mode}")

    sensor_packet = {
        "source_mode": source_mode,
        "available": {
            "image": bool(image_output),
            "lidar": _lidar_ready(lidar_output),
        },
        "camera": {
            "device_id": str(props.get("cameraDeviceId", "") or ""),
            "facing_mode": str(props.get("cameraFacingMode", "environment") or "environment"),
            "capture_width": _to_int(props.get("captureWidth"), 1280),
            "capture_height": _to_int(props.get("captureHeight"), 720),
            "last_captured_at": last_captured_at,
        },
        "remote": {
            "image_url": remote_image_url,
            "lidar_url": remote_lidar_url,
            "method": remote_method,
            "image_transport": remote_image_transport,
            "rtsp_transport": rtsp_transport,
            "ffmpeg_path": ffmpeg_path,
            "lidar_format": lidar_format,
            "lidar_obstacle_distance": lidar_obstacle_distance,
            "headers_present": bool(remote_headers),
            "body_present": remote_body is not None,
            "timeout_sec": timeout_sec,
        },
        "meta": {
            "image": image_meta,
            "lidar": lidar_meta,
        },
        "summary": {
            "image_ready": bool(image_output),
            "lidar_ready": _lidar_ready(lidar_output),
            "lidar_point_count": (
                int(lidar_output.get("point_count", 0))
                if isinstance(lidar_output, dict)
                else 0
            ),
            "lidar_nearest_range": (
                ((lidar_output.get("summary") or {}).get("nearest_range")
                 or (lidar_output.get("summary") or {}).get("nearest_distance"))
                if isinstance(lidar_output, dict)
                else None
            ),
        },
    }

    return {
        "image": image_output,
        "lidar": lidar_output,
        "raw_lidar": raw_lidar_output,
        "sensor": sensor_packet,
    }
