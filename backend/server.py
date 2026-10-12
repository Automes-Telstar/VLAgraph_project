# backend/server.py
from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from typing import Any, Dict, List
import inspect
import json
import logging
import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from websocket import create_connection

from backend.config import (
    ALLOW_ORIGINS,
    MAX_UPLOAD_MB,
    ROUTE_FINETUNE,
    ROUTE_VLA,
    UPLOAD_DIR,
)
from backend.schemas import (
    FineTuneStartRequest,
    GraphRuntimeStartRequest,
    GraphRunRequest,
    InferRequest,
    UnityRunRequest,
    UploadResponse,
)
from backend.executors.registry import NODE_EXECUTORS
from backend.executors.vla_nodes import _omniverse_endpoint_candidates
from backend import state_store
from backend.runtime.runner import run_graph as run_graph_sync
from backend.runtime.session_manager import graph_runtime_manager, prepare_graph_for_execution


class _UnitySensorAccessLogFilter(logging.Filter):
    def __init__(self) -> None:
        super().__init__()
        raw_prefixes = os.getenv(
            "QUIET_ACCESS_LOG_PREFIXES",
            "/api/unity/image,/api/unity/lidar,/api/unity/state,"
            "/ws/unity/image,/ws/unity/lidar,/ws/unity/state",
        )
        self.quiet_prefixes = tuple(
            prefix.strip() for prefix in raw_prefixes.split(",") if prefix.strip()
        )

    def filter(self, record: logging.LogRecord) -> bool:
        if not self.quiet_prefixes:
            return True

        message = record.getMessage()
        if "WebSocket " in message:
            return not any(
                f"WebSocket {prefix}" in message
                for prefix in self.quiet_prefixes
            )

        method = ""
        path = ""
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3:
            method = str(args[1] or "").upper()
            path = str(args[2] or "")

        return not (
            method == "GET"
            and any(path.startswith(prefix) for prefix in self.quiet_prefixes)
        )


class _WebSocketLifecycleLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage().strip().lower()
        return message not in {"connection open", "connection closed"}


def _install_access_log_filter() -> None:
    if os.getenv("QUIET_UNITY_SENSOR_ACCESS_LOGS", "true").lower() in {"0", "false", "no", "off"}:
        return

    logger = logging.getLogger("uvicorn.access")
    if getattr(logger, "_unity_sensor_filter_installed", False):
        return

    unity_sensor_filter = _UnitySensorAccessLogFilter()
    logger.addFilter(unity_sensor_filter)
    setattr(logger, "_unity_sensor_filter_installed", True)

    if os.getenv("QUIET_WEBSOCKET_LIFECYCLE_LOGS", "true").lower() in {"0", "false", "no", "off"}:
        return

    lifecycle_filter = _WebSocketLifecycleLogFilter()
    for lifecycle_logger_name in (
        "uvicorn.error",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.protocols.websockets.wsproto_impl",
    ):
        lifecycle_logger = logging.getLogger(lifecycle_logger_name)
        if getattr(lifecycle_logger, "_websocket_lifecycle_filter_installed", False):
            continue
        lifecycle_logger.addFilter(unity_sensor_filter)
        lifecycle_logger.addFilter(lifecycle_filter)
        setattr(lifecycle_logger, "_websocket_lifecycle_filter_installed", True)


_install_access_log_filter()


app = FastAPI(title="OPENVLA Lego Graph Backend", version="0.3.0")

os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_REALSENSE_BRIDGE_PROCESS: subprocess.Popen[str] | None = None
_REALSENSE_BRIDGE_PORT = 9180


def _realsense_bridge_url(port: int = _REALSENSE_BRIDGE_PORT) -> str:
    return f"http://127.0.0.1:{port}"


def _server_running_in_container() -> bool:
    return Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()


def _realsense_bridge_base_candidates(port: int = _REALSENSE_BRIDGE_PORT) -> List[str]:
    if _server_running_in_container():
        return [
            f"http://host.docker.internal:{port}",
            f"http://127.0.0.1:{port}",
        ]
    return [
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
    ]


def _realsense_bridge_health(port: int = _REALSENSE_BRIDGE_PORT) -> Dict[str, Any]:
    errors: List[str] = []
    last_url = f"{_realsense_bridge_url(port)}/health"
    for base_url in _realsense_bridge_base_candidates(port):
        url = f"{base_url}/health"
        last_url = url
        try:
            response = httpx.get(url, timeout=1.0)
            payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            if response.is_success:
                return {
                    "ok": True,
                    "reachable": True,
                    "url": url,
                    "status_code": response.status_code,
                    "payload": payload if isinstance(payload, dict) else {},
                }
            errors.append(f"{url} -> HTTP {response.status_code}")
        except Exception as exc:
            errors.append(f"{url} -> {exc}")

    return {
        "ok": False,
        "reachable": False,
        "url": last_url,
        "error": "; ".join(errors),
    }


def _realsense_bridge_script() -> Path:
    candidates = [
        Path(__file__).resolve().parents[1] / "scripts" / "realsense_d435i_bridge.py",
        Path(__file__).resolve().parents[0] / "scripts" / "realsense_d435i_bridge.py",
        Path.cwd() / "scripts" / "realsense_d435i_bridge.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[-1]


def _managed_realsense_bridge_running() -> bool:
    return _REALSENSE_BRIDGE_PROCESS is not None and _REALSENSE_BRIDGE_PROCESS.poll() is None


def _realsense_bridge_status(port: int = _REALSENSE_BRIDGE_PORT) -> Dict[str, Any]:
    health = _realsense_bridge_health(port)
    health_url = str(health.get("url") or f"{_realsense_bridge_url(port)}/health")
    frame_url = health_url[: -len("/health")] + "/frame" if health_url.endswith("/health") else f"{_realsense_bridge_url(port)}/frame"
    return {
        **health,
        "managed": _managed_realsense_bridge_running(),
        "pid": _REALSENSE_BRIDGE_PROCESS.pid if _managed_realsense_bridge_running() else None,
        "frame_url": frame_url,
        "running_in_container": _server_running_in_container(),
    }

def _image_data_uri_from_base64(encoded: str, content_type: str) -> str:
    mime = str(content_type or "image/jpeg").split(";", 1)[0].strip() or "image/jpeg"
    return f"data:{mime};base64,{encoded.strip()}"


def _extract_unity_image_record(client_id: str, payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("invalid json payload")

    image_value = ""
    for key in ("image", "data_url", "frame", "snapshot"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            image_value = value.strip()
            break

    if not image_value:
        content_type = str(payload.get("content_type") or payload.get("mime_type") or "image/jpeg")
        for key in ("image_base64", "frame_base64", "base64", "image_b64"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                image_value = _image_data_uri_from_base64(value, content_type)
                break

    if not image_value:
        raise ValueError("image field missing")

    return {
        "client_id": str(payload.get("client_id") or client_id or "default").strip() or "default",
        "image": image_value,
        "content_type": str(payload.get("content_type") or payload.get("mime_type") or "image/jpeg"),
        "width": int(payload.get("width") or 0),
        "height": int(payload.get("height") or 0),
        "scene": str(payload.get("scene") or ""),
        "object_name": str(payload.get("object_name") or payload.get("object") or ""),
        "source": str(payload.get("source") or "unity_rawimage_ws"),
        "unity_timestamp": payload.get("timestamp"),
        "raw": payload,
    }


def _unity_image_ack(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ok": True,
        "client_id": record.get("client_id", "default"),
        "timestamp": record.get("timestamp"),
        "width": record.get("width", 0),
        "height": record.get("height", 0),
        "source": record.get("source", "unity_rawimage_ws"),
    }


def _extract_unity_lidar_record(client_id: str, payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("invalid json payload")

    lidar_type = str(payload.get("type") or "").strip().lower()
    allowed_types = {"", "lidar_frame", "laser_scan", "pointcloud", "pointcloud_xyz"}
    if lidar_type not in allowed_types:
        raise ValueError(f"unsupported lidar type: {payload.get('type')}")

    ranges = payload.get("ranges")
    points = (
        payload.get("points")
        or payload.get("pointcloud")
        or payload.get("point_cloud")
        or payload.get("xyz")
        or payload.get("points_flat")
    )
    if not isinstance(ranges, list) and not isinstance(points, list):
        raise ValueError("lidar payload requires ranges or points")

    normalized_client_id = str(payload.get("client_id") or client_id or "default").strip() or "default"
    record = dict(payload)
    record["client_id"] = normalized_client_id
    record["source"] = str(payload.get("source") or "unity_lidar_ws")
    record["frame_id"] = str(payload.get("frame_id") or payload.get("frame") or "unity_lidar")
    record["unity_timestamp"] = payload.get("timestamp")
    record["raw"] = payload

    if isinstance(ranges, list):
        record["range_count"] = int(payload.get("range_count") or len(ranges))
    elif isinstance(points, list):
        if points is payload.get("points_flat"):
            record["point_count"] = int(payload.get("point_count") or (len(points) // 3))
        else:
            record["point_count"] = int(payload.get("point_count") or len(points))

    return record


def _unity_lidar_ack(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ok": True,
        "client_id": record.get("client_id", "default"),
        "timestamp": record.get("timestamp"),
        "frame_id": record.get("frame_id", "unity_lidar"),
        "range_count": record.get("range_count", 0),
        "point_count": record.get("point_count", 0),
        "source": record.get("source", "unity_lidar_ws"),
    }


def _extract_unity_state_record(client_id: str, payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("invalid json payload")

    state_type = str(payload.get("type") or "").strip().lower()
    if state_type and state_type != "robot_state":
        raise ValueError(f"unsupported state type: {payload.get('type')}")

    candidate = dict(payload)
    candidate["client_id"] = str(payload.get("client_id") or client_id or "default").strip() or "default"
    candidate["source"] = str(payload.get("source") or "unity_state_ws")

    if not state_store._looks_like_robot_state_payload(candidate):
        raise ValueError("robot_state payload missing robot pose/state fields")

    return candidate

# ------------------------------------------------------------
# Unity state WebSocket
# ------------------------------------------------------------


@app.websocket("/ws/unity/state")
async def unity_state_ws(websocket: WebSocket, client_id: str = Query("default")):
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
                record = _extract_unity_state_record(client_id, payload)
            except ValueError as exc:
                await websocket.send_text(json.dumps({"ok": False, "error": str(exc)}))
                continue
            except Exception:
                await websocket.send_text(json.dumps({"ok": False, "error": "invalid json"}))
                continue

            stored = state_store.update_state(record.get("client_id", client_id), record)
            await websocket.send_text(json.dumps({"ok": True, "stored": stored}))
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/unity/image")
async def unity_image_ws(websocket: WebSocket, client_id: str = Query("default")):
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
                record = _extract_unity_image_record(client_id, payload)
            except ValueError as exc:
                await websocket.send_text(json.dumps({"ok": False, "error": str(exc)}))
                continue
            except Exception:
                await websocket.send_text(json.dumps({"ok": False, "error": "invalid json"}))
                continue

            stored = state_store.update_image(record.get("client_id", client_id), record)
            await websocket.send_text(json.dumps(_unity_image_ack(stored)))
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/unity/lidar")
async def unity_lidar_ws(websocket: WebSocket, client_id: str = Query("default")):
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
                record = _extract_unity_lidar_record(client_id, payload)
            except ValueError as exc:
                await websocket.send_text(json.dumps({"ok": False, "error": str(exc)}))
                continue
            except Exception:
                await websocket.send_text(json.dumps({"ok": False, "error": "invalid json"}))
                continue

            stored = state_store.update_lidar(record.get("client_id", client_id), record)
            await websocket.send_text(json.dumps(_unity_lidar_ack(stored)))
    except WebSocketDisconnect:
        pass


# ------------------------------------------------------------
# Unity state REST fetch
# ------------------------------------------------------------


@app.get("/api/unity/state")
def get_unity_state(client_id: str = "default") -> Dict[str, Any]:
    state = state_store.get_state(client_id)
    if state is None:
        return {"ok": False, "client_id": client_id, "message": "no state"}
    return {"ok": True, "requested_client_id": client_id, **state}


@app.get("/api/unity/state/clients")
def list_unity_clients() -> Dict[str, Any]:
    return {"ok": True, "clients": state_store.list_clients()}


@app.get("/api/unity/image")
def get_unity_image(client_id: str = "default") -> Dict[str, Any]:
    image = state_store.get_image(client_id)
    if image is None:
        return {"ok": False, "client_id": client_id, "message": "no image"}
    return {"ok": True, "requested_client_id": client_id, **image}


@app.get("/api/unity/image/clients")
def list_unity_image_clients() -> Dict[str, Any]:
    return {"ok": True, "clients": state_store.list_image_clients()}


@app.get("/api/unity/lidar")
def get_unity_lidar(client_id: str = "default") -> Dict[str, Any]:
    lidar = state_store.get_lidar(client_id)
    if lidar is None:
        return {"ok": False, "client_id": client_id, "message": "no lidar"}
    return {"ok": True, "requested_client_id": client_id, **lidar}


@app.get("/api/unity/lidar/clients")
def list_unity_lidar_clients() -> Dict[str, Any]:
    return {"ok": True, "clients": state_store.list_lidar_clients()}


# ------------------------------------------------------------
# Omniverse one-shot commands
# ------------------------------------------------------------
def _float_from_request(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        return default
    return parsed if parsed > 0 else default


def _parse_omniverse_message(raw_message: Any, request_id: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(raw_message)
    except Exception:
        return {
            "ok": False,
            "request_id": request_id,
            "applied": False,
            "error": f"Invalid JSON response from Omniverse: {raw_message}",
        }

    if isinstance(parsed, dict):
        return parsed

    return {
        "ok": False,
        "request_id": request_id,
        "applied": False,
        "error": f"Unexpected Omniverse response type: {type(parsed).__name__}",
    }


def _replace_endpoint_port(endpoint: str, port: int) -> str:
    try:
        parsed = urlparse(endpoint)
        if not parsed.scheme or not parsed.hostname:
            return endpoint
        host = parsed.hostname
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        netloc = f"{host}:{int(port)}"
        return urlunparse(parsed._replace(netloc=netloc))
    except Exception:
        return endpoint


def _normalize_isaac_g1_scene_endpoint(endpoint: str) -> str:
    try:
        parsed = urlparse(endpoint)
        if int(parsed.port or 0) != 9899:
            return endpoint
        path = parsed.path
        if path and path != "/" and path.endswith("/"):
            return urlunparse(parsed._replace(path=path.rstrip("/")))
    except Exception:
        pass
    return endpoint


def _isaac_g1_init_endpoints(endpoint: str) -> List[str]:
    endpoints: List[str] = []

    def add(value: str) -> None:
        if value and value not in endpoints:
            endpoints.append(value)

    for candidate in _omniverse_endpoint_candidates(endpoint):
        try:
            parsed = urlparse(candidate)
            port = int(parsed.port or 0)
        except Exception:
            port = 0

        if port == 9900:
            add(_normalize_isaac_g1_scene_endpoint(_replace_endpoint_port(candidate, 9899)))
            add(candidate)
        elif port == 9899:
            add(_normalize_isaac_g1_scene_endpoint(candidate))
            add(_replace_endpoint_port(candidate, 9900))
        else:
            add(candidate)

    return endpoints


def _send_omniverse_init_command(
    *,
    endpoint: str,
    request_payload: Dict[str, Any],
    request_id: str,
    timeout_sec: float,
    response_timeout_sec: float,
) -> Dict[str, Any]:
    ws = None
    request_sent = False
    try:
        ws = create_connection(endpoint, timeout=timeout_sec)
        ws.settimeout(response_timeout_sec)
        ws.send(json.dumps(request_payload, ensure_ascii=False))
        request_sent = True

        response_candidates = [ws.recv()]
        ws.settimeout(max(0.1, min(response_timeout_sec, 0.25)))
        while True:
            try:
                response_candidates.append(ws.recv())
            except (TimeoutError, OSError):
                break
            except Exception:
                break

        primary_response: Dict[str, Any] | None = None
        latest_state: Dict[str, Any] | None = None
        received_messages: List[Dict[str, Any]] = []

        for raw_message in response_candidates:
            parsed_message = _parse_omniverse_message(raw_message, request_id)
            received_messages.append(parsed_message)
            if str(parsed_message.get("type", "")).strip().lower() == "robot_state":
                latest_state = parsed_message
                continue
            if primary_response is None:
                primary_response = parsed_message

        response = primary_response or latest_state or {
            "ok": False,
            "request_id": request_id,
            "applied": False,
            "error": "No response received from Omniverse.",
        }

        if response.get("request_id") not in (None, request_id):
            return {
                "ok": False,
                "applied": False,
                "endpoint": endpoint,
                "request": request_payload,
                "response": response,
                "received_messages": received_messages,
                "message": "Omniverse response request_id mismatch.",
            }

        response_ok = response.get("ok")
        if response_ok is None:
            response_ok = response.get("applied")
        applied = response.get("applied")
        if applied is None:
            applied = response_ok

        message = str(
            response.get("message")
            or response.get("error")
            or ("Isaac GR00T scene initialized." if response_ok else "Isaac GR00T scene init failed.")
        )
        prim_path = str(
            response.get("prim_path")
            or response.get("primPath")
            or response.get("resolved_prim_path")
            or ""
        )

        return {
            "ok": bool(response_ok),
            "applied": bool(applied),
            "endpoint": endpoint,
            "request": request_payload,
            "response": response,
            "received_messages": received_messages,
            "message": message,
            "prim_path": prim_path,
        }
    except Exception as exc:
        return {
            "ok": False,
            "applied": False,
            "endpoint": endpoint,
            "request": request_payload,
            "message": f"{endpoint} -> {exc}",
            "request_sent": request_sent,
        }
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass


@app.post("/api/omniverse/isaac-gr00t/init")
def init_isaac_gr00t_scene(req: Dict[str, Any]) -> Dict[str, Any]:
    endpoint = str(
        req.get("omniverseEndpoint")
        or req.get("omniverse_endpoint")
        or req.get("endpoint")
        or "ws://host.docker.internal:9900/omniverse"
    ).strip()
    timeout_sec = _float_from_request(
        req.get("timeoutSec", req.get("timeout_sec", 15)),
        15.0,
    )
    response_timeout_sec = max(timeout_sec, 15.0)
    request_id = str(
        req.get("requestId")
        or req.get("request_id")
        or f"init-{uuid4().hex}"
    ).strip()
    client_id = str(req.get("clientId") or req.get("client_id") or "").strip()

    request_payload: Dict[str, Any] = {
        "type": "omniverse_command",
        "request_id": request_id,
        "command": "init",
    }
    if client_id:
        request_payload["client_id"] = client_id

    for source_key, target_key in (
        ("omniverseUrl", "url"),
        ("omniverse_url", "url"),
        ("stage", "stage"),
        ("omniverseStage", "stage"),
        ("omniverse_stage", "stage"),
        ("primPath", "prim_path"),
        ("prim_path", "prim_path"),
        ("omniversePrimPath", "prim_path"),
        ("omniverse_prim_path", "prim_path"),
    ):
        value = req.get(source_key)
        if value not in (None, "") and target_key not in request_payload:
            request_payload[target_key] = value

    init_sequence: List[Dict[str, Any]] = []
    for candidate_endpoint in _isaac_g1_init_endpoints(endpoint):
        result = _send_omniverse_init_command(
            endpoint=candidate_endpoint,
            request_payload=request_payload,
            request_id=request_id,
            timeout_sec=timeout_sec,
            response_timeout_sec=response_timeout_sec,
        )
        init_sequence.append(result)
        if result.get("ok"):
            try:
                successful_port = int(urlparse(candidate_endpoint).port or 0)
            except Exception:
                successful_port = 0
            successful_ports = {
                int(urlparse(str(item.get("endpoint") or "")).port or 0)
                for item in init_sequence
                if item.get("ok")
            }
            if successful_port not in {9899, 9900} or {9899, 9900}.issubset(successful_ports):
                break

    successful = [item for item in init_sequence if item.get("ok")]
    if successful:
        primary = successful[-1]
        return {
            **primary,
            "ok": True,
            "applied": any(bool(item.get("applied")) for item in successful),
            "endpoint": str(primary.get("endpoint") or endpoint),
            "init_sequence": init_sequence,
            "tried_endpoints": [str(item.get("endpoint") or "") for item in init_sequence],
            "message": "Unified Isaac G1 init completed: "
            + " -> ".join(
                f"{item.get('endpoint')}:{'ok' if item.get('ok') else 'failed'}"
                for item in init_sequence
            ),
        }

    attempted_text = "; ".join(str(item.get("message") or item.get("endpoint")) for item in init_sequence)
    return {
        "ok": False,
        "applied": False,
        "endpoint": endpoint,
        "tried_endpoints": [str(item.get("endpoint") or "") for item in init_sequence],
        "init_sequence": init_sequence,
        "request": request_payload,
        "message": f"Isaac GR00T init failed: {attempted_text}",
    }


# ------------------------------------------------------------
# Log helpers
# ------------------------------------------------------------
def summarize_for_log(value: Any, depth: int = 0) -> Any:
    if isinstance(value, str):
        compact = " ".join(value.split())
        if len(compact) > 140:
            return f"{compact[:137]}..."
        return compact

    if depth >= 2:
        if isinstance(value, dict):
            return "{...}"
        if isinstance(value, list):
            return "[...]"
        return value

    if isinstance(value, dict):
        items = list(value.items())
        summarized: Dict[str, Any] = {}
        for key, item in items[:6]:
            summarized[str(key)] = summarize_for_log(item, depth + 1)
        if len(items) > 6:
            summarized["..."] = f"{len(items) - 6} more fields"
        return summarized

    if isinstance(value, list):
        summarized = [summarize_for_log(item, depth + 1) for item in value[:6]]
        if len(value) > 6:
            summarized.append(f"... {len(value) - 6} more items")
        return summarized

    return value


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def build_unity_run_debug(result: Dict[str, Any]) -> Dict[str, Any]:
    context = _as_dict(result.get("context"))
    state_node = _as_dict(context.get("node-3"))
    infer_node = _as_dict(context.get("node-4"))
    decode_node = _as_dict(context.get("node-5"))
    safety_node = _as_dict(context.get("node-6"))
    execute_node = _as_dict(context.get("node-7"))

    state_snapshot = {
        "client_id": state_node.get("client_id"),
        "object_name": state_node.get("object_name"),
        "robot_type": state_node.get("robot_type"),
        "controller_mode": state_node.get("controller_mode"),
        "position": state_node.get("position"),
        "velocity": state_node.get("velocity"),
        "goal_position": state_node.get("goal_position"),
        "distance_to_goal": state_node.get("distance_to_goal"),
        "has_line_of_sight": state_node.get("has_line_of_sight"),
        "stuck": state_node.get("stuck"),
        "source": state_node.get("source"),
        "error": state_node.get("error"),
    }

    return {
        "state": state_snapshot,
        "openvla": {
            "request": infer_node.get("request"),
            "action": infer_node.get("action"),
            "error": infer_node.get("error"),
            "error_detail": infer_node.get("error_detail"),
            "route": infer_node.get("route"),
            "raw": summarize_for_log(infer_node.get("raw")),
        },
        "decoded_action": decode_node.get("decoded"),
        "safe_action": safety_node.get("safe_action"),
        "unity_execute": {
            "command": execute_node.get("command"),
            "request": execute_node.get("request"),
            "response": execute_node.get("response"),
            "received_messages": summarize_for_log(execute_node.get("received_messages")),
            "message": execute_node.get("message"),
            "state_update": summarize_for_log(execute_node.get("state_update")),
            "tried_endpoints": execute_node.get("tried_endpoints"),
        },
    }


# ------------------------------------------------------------
# Graph helpers
# ------------------------------------------------------------
def build_node_map(nodes: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {node["id"]: node for node in nodes}


def topo_sort(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[str]:
    indegree = {node["id"]: 0 for node in nodes}
    graph: Dict[str, List[str]] = {node["id"]: [] for node in nodes}

    for edge in edges:
        source = edge["source"]
        target = edge["target"]

        if source not in graph:
            raise HTTPException(status_code=400, detail=f"Unknown source node: {source}")
        if target not in indegree:
            raise HTTPException(status_code=400, detail=f"Unknown target node: {target}")

        graph[source].append(target)
        indegree[target] += 1

    queue = [node_id for node_id, degree in indegree.items() if degree == 0]
    ordered: List[str] = []

    while queue:
        current = queue.pop(0)
        ordered.append(current)

        for nxt in graph[current]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    if len(ordered) != len(nodes):
        raise HTTPException(status_code=400, detail="Cycle detected in graph")

    return ordered


async def execute_node(
    executor: Any,
    node: Dict[str, Any],
    context: Dict[str, Any],
    edges: List[Dict[str, Any]],
) -> Any:
    """
    executor 호환 처리:
    1) exec(node, context, edges)
    2) exec(node, context)
    둘 다 지원
    """
    try:
        sig = inspect.signature(executor)
        param_count = len(sig.parameters)
    except Exception:
        param_count = 3

    if param_count >= 3:
        result = executor(node, context, edges)
    else:
        result = executor(node, context)

    if inspect.isawaitable(result):
        result = await result

    return result


async def run_graph_internal(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    node_map = build_node_map(nodes)
    ordered = topo_sort(nodes, edges)

    context: Dict[str, Any] = {}
    logs: List[str] = []

    for node_id in ordered:
        node = node_map[node_id]
        node_type = node.get("type")

        executor = NODE_EXECUTORS.get(node_type)
        if executor is None:
            raise HTTPException(status_code=400, detail=f"Unknown node type: {node_type}")

        logs.append(f"[RUN] {node_type} ({node_id})")

        try:
            result = await execute_node(executor, node, context, edges)
            context[node_id] = result
            logs.append(f"[OK] {node_type} ({node_id}) -> {summarize_for_log(result)}")
        except Exception as e:
            context[node_id] = {
                "ok": False,
                "error": str(e),
            }
            logs.append(f"[ERROR] {node_type} ({node_id}) -> {str(e)}")

    return {
        "ok": True,
        "order": ordered,
        "context": context,
        "logs": logs,
    }


def build_unity_run_graph(req: UnityRunRequest) -> Dict[str, List[Dict[str, Any]]]:
    use_unity_state = bool(req.use_unity_state)
    state_client_id = str(req.state_client_id or "").strip() or "default"

    if use_unity_state:
        state_node = {
            "id": "node-3",
            "type": "unity_state",
            "position": {"x": 80, "y": 420},
            "data": {
                "label": "Robot State (Unity)",
                "clientId": state_client_id,
            },
        }
    else:
        state_node = {
            "id": "node-3",
            "type": "robot_state",
            "position": {"x": 80, "y": 420},
            "data": {
                "label": "Robot State Node",
                "robotState": req.robot_state,
            },
        }

    nodes = [
        {
            "id": "node-1",
            "type": "prompt",
            "position": {"x": 80, "y": 100},
            "data": {
                "label": "Prompt Node",
                "text": req.prompt,
            },
        },
        {
            "id": "node-2",
            "type": "image_input",
            "position": {"x": 80, "y": 260},
            "data": {
                "label": "Image Input Node",
                "imageUrl": req.image,
            },
        },
        state_node,
        {
            "id": "node-4",
            "type": "openvla_infer",
            "position": {"x": 440, "y": 250},
            "data": {
                "label": "OpenVLA Infer Node",
                "modelName": req.model_name,
                "actionFormat": req.action_format,
                "unityCommand": req.unity_command,
                "waypointSpeed": req.waypoint_speed,
            },
        },
        {
            "id": "node-5",
            "type": "action_decode",
            "position": {"x": 780, "y": 250},
            "data": {
                "label": "Action Decode Node",
                "decodeMode": req.decode_mode,
            },
        },
        {
            "id": "node-6",
            "type": "safety_clamp",
            "position": {"x": 1120, "y": 250},
            "data": {
                "label": "Safety Clamp Node",
                "enabled": req.safety_enabled,
                "maxDelta": req.safety_max_delta,
            },
        },
        {
            "id": "node-7",
            "type": "robot_execute",
            "position": {"x": 1460, "y": 250},
            "data": {
                "label": "Robot Execute Node",
                "executor": "robot-executor",
                "mode": "unity",
                "unityEndpoint": req.unity_endpoint,
                "unityScene": req.unity_scene,
                "unityObject": req.unity_object,
                "unityCommand": req.unity_command,
                "unityRobotType": req.unity_robot_type,
                "unityControllerMode": req.unity_controller_mode,
                "unityTimeoutSec": req.unity_timeout_sec,
                "unityStateClientId": state_client_id,
            },
        },
    ]

    edges = [
        {
            "id": "e1-4",
            "source": "node-1",
            "target": "node-4",
            "sourceHandle": "text",
            "targetHandle": "prompt",
        },
        {
            "id": "e2-4",
            "source": "node-2",
            "target": "node-4",
            "sourceHandle": "image",
            "targetHandle": "image",
        },
        {
            "id": "e3-4",
            "source": "node-3",
            "target": "node-4",
            "sourceHandle": "state",
            "targetHandle": "state",
        },
        {
            "id": "e4-5",
            "source": "node-4",
            "target": "node-5",
            "sourceHandle": "action",
            "targetHandle": "action",
        },
        {
            "id": "e5-6",
            "source": "node-5",
            "target": "node-6",
            "sourceHandle": "decoded",
            "targetHandle": "action",
        },
        {
            "id": "e6-7",
            "source": "node-6",
            "target": "node-7",
            "sourceHandle": "safe_action",
            "targetHandle": "action",
        },
    ]

    return {
        "nodes": nodes,
        "edges": edges,
    }


# ------------------------------------------------------------
# Health
# ------------------------------------------------------------
@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "service": "OPENVLA Lego Graph Backend",
        "route_vla": ROUTE_VLA,
        "route_finetune": ROUTE_FINETUNE,
        "node_types": list(NODE_EXECUTORS.keys()),
        "upload_dir": UPLOAD_DIR,
    }


@app.get("/api/realsense/bridge/status")
def realsense_bridge_status(port: int = Query(_REALSENSE_BRIDGE_PORT, ge=1, le=65535)) -> Dict[str, Any]:
    return _realsense_bridge_status(port)


@app.post("/api/realsense/bridge/start")
def start_realsense_bridge(payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    global _REALSENSE_BRIDGE_PROCESS

    data = payload or {}
    port = int(data.get("port") or _REALSENSE_BRIDGE_PORT)
    width = int(data.get("width") or 640)
    height = int(data.get("height") or 480)
    fps = int(data.get("fps") or 30)
    serial = str(data.get("serial") or "").strip()
    mock_when_unavailable = bool(data.get("mockWhenUnavailable", False))

    existing = _realsense_bridge_health(port)
    if existing.get("reachable"):
        return {
            **_realsense_bridge_status(port),
            "started": False,
            "message": "RealSense bridge is already reachable.",
        }

    if _managed_realsense_bridge_running():
        return {
            **_realsense_bridge_status(port),
            "started": False,
            "message": "Managed RealSense bridge process is already running.",
        }

    if _server_running_in_container():
        return {
            **_realsense_bridge_status(port),
            "started": False,
            "message": (
                "RealSense bridge is not reachable. The backend is running inside Docker, "
                "so it cannot start the Windows USB camera directly. Run this on the Windows host: "
                r"powershell -ExecutionPolicy Bypass -File scripts\start_realsense_host_bridge.ps1 -NoMockFallback"
            ),
        }

    script = _realsense_bridge_script()
    if not script.exists():
        raise HTTPException(status_code=500, detail=f"RealSense bridge script not found: {script}")

    log_dir = Path(UPLOAD_DIR).resolve().parent / "scripts"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_log = log_dir / "realsense_d435i_bridge.api.out.log"
    stderr_log = log_dir / "realsense_d435i_bridge.api.err.log"

    command = [
        sys.executable,
        str(script),
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        "--width",
        str(width),
        "--height",
        str(height),
        "--fps",
        str(fps),
        "--reconnect-interval-sec",
        "1.0",
        "--frame-cache-ttl-sec",
        "0.06",
    ]
    if serial:
        command.extend(["--serial", serial])
    if mock_when_unavailable:
        command.append("--mock-when-unavailable")

    with stdout_log.open("a", encoding="utf-8") as out, stderr_log.open("a", encoding="utf-8") as err:
        _REALSENSE_BRIDGE_PROCESS = subprocess.Popen(
            command,
            cwd=str(Path(__file__).resolve().parents[1]),
            stdout=out,
            stderr=err,
            text=True,
        )

    deadline = time.time() + 5.0
    status = _realsense_bridge_status(port)
    while time.time() < deadline:
        time.sleep(0.25)
        status = _realsense_bridge_status(port)
        if status.get("reachable"):
            break

    return {
        **status,
        "started": True,
        "stdout_log": str(stdout_log),
        "stderr_log": str(stderr_log),
        "message": "RealSense bridge start requested.",
    }


@app.post("/api/realsense/bridge/stop")
def stop_realsense_bridge() -> Dict[str, Any]:
    global _REALSENSE_BRIDGE_PROCESS

    if not _managed_realsense_bridge_running():
        return {
            **_realsense_bridge_status(),
            "stopped": False,
            "message": "No managed RealSense bridge process is running.",
        }

    process = _REALSENSE_BRIDGE_PROCESS
    assert process is not None
    process.terminate()
    try:
        process.wait(timeout=3.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3.0)
    _REALSENSE_BRIDGE_PROCESS = None

    return {
        **_realsense_bridge_status(),
        "stopped": True,
        "message": "Managed RealSense bridge process stopped.",
    }


# ------------------------------------------------------------
# Upload
# 기존 /upload/file 유지
# 추가로 프론트 편의를 위해 /api/upload도 제공
# ------------------------------------------------------------
@app.post("/upload/file", response_model=UploadResponse)
@app.post("/api/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    contents = await file.read()
    size_bytes = len(contents)

    if size_bytes > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file too large")

    ext = os.path.splitext(file.filename or "")[1]
    safe_name = f"{uuid4().hex}{ext}"
    full_path = os.path.join(UPLOAD_DIR, safe_name)

    with open(full_path, "wb") as f:
        f.write(contents)

    return UploadResponse(
        file_name=file.filename or safe_name,
        file_path=full_path,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=size_bytes,
    )


# ------------------------------------------------------------
# Proxy: OpenVLA infer
# 기존 /vla/infer 유지
# ------------------------------------------------------------
@app.post("/vla/infer")
async def proxy_infer(req: InferRequest) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{ROUTE_VLA}/infer", json=req.model_dump())
        response.raise_for_status()
        return response.json()


# ------------------------------------------------------------
# Proxy: Finetune
# 기존 /vla/finetune/start 유지
# ------------------------------------------------------------
@app.post("/vla/finetune/start")
async def proxy_finetune(req: FineTuneStartRequest) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{ROUTE_FINETUNE}/finetune/start",
            json=req.model_dump(),
        )
        response.raise_for_status()
        return response.json()


# ------------------------------------------------------------
# Graph run
# 기존 /graph/run 유지
# 추가로 /api/graph/run 제공
# ------------------------------------------------------------
@app.post("/graph/run")
@app.post("/api/graph/run")
async def run_graph(req: GraphRunRequest) -> Dict[str, Any]:
    graph = {
        "nodes": [node.model_dump() for node in req.nodes],
        "edges": [edge.model_dump() for edge in req.edges],
    }
    prepared_graph, prepare_logs = prepare_graph_for_execution(graph)
    result = await asyncio.to_thread(run_graph_sync, prepared_graph, req.input)
    if prepare_logs:
        result["graph_prepare_logs"] = prepare_logs
    return result


@app.post("/api/graph/runtime/start")
async def start_graph_runtime(req: GraphRuntimeStartRequest) -> Dict[str, Any]:
    graph = {
        "nodes": [node.model_dump() for node in req.nodes],
        "edges": [edge.model_dump() for edge in req.edges],
    }
    return await graph_runtime_manager.start_session(
        graph,
        req.input,
        req.options.model_dump(),
    )


@app.get("/api/graph/runtime/{session_id}")
async def get_graph_runtime(session_id: str) -> Dict[str, Any]:
    try:
        return graph_runtime_manager.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="graph runtime session not found")


@app.post("/api/graph/runtime/{session_id}/cancel")
async def cancel_graph_runtime(session_id: str) -> Dict[str, Any]:
    try:
        return await graph_runtime_manager.cancel_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="graph runtime session not found")


@app.post("/unity/run")
@app.post("/api/unity/run")
async def run_unity_graph(req: UnityRunRequest) -> Dict[str, Any]:
    graph = build_unity_run_graph(req)
    result = await asyncio.to_thread(run_graph_sync, graph)
    debug = build_unity_run_debug(result)
    result["request"] = req.model_dump()
    result["debug"] = debug
    print(f"[unity_run] debug={json.dumps(summarize_for_log(debug), ensure_ascii=False)}")
    return result
