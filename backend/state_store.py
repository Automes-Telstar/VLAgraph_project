"""Thread-safe in-memory store for latest Unity robot state and image per client."""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional


_state_lock = threading.Lock()
_state: Dict[str, Dict[str, Any]] = {}

_image_lock = threading.Lock()
_image: Dict[str, Dict[str, Any]] = {}

_lidar_lock = threading.Lock()
_lidar: Dict[str, Dict[str, Any]] = {}

_AUTO_CLIENT_IDS = {"", "default", "auto"}
_STATE_SOURCE_PRIORITY = {
    "isaacsim_bridge": 100,
    "unity_websocket": 50,
    "unity_state_ws": 50,
    "isaac_g1_vlagraph_bridge": 10,
}


def _normalize_client_id(client_id: str) -> str:
    return str(client_id or "").strip() or "default"


def _looks_like_robot_state_payload(state: Any) -> bool:
    if not isinstance(state, dict):
        return False

    state_type = str(state.get("type") or "").strip().lower()
    if state_type and state_type != "robot_state":
        return False

    vector_keys = ("position", "rotation", "eef_pose", "joint_positions")
    if any(isinstance(state.get(key), list) and len(state.get(key)) > 0 for key in vector_keys):
        return True

    text_keys = ("scene", "object_name", "robot_type", "controller_mode", "source")
    if any(str(state.get(key) or "").strip() for key in text_keys):
        return True

    return "gripper_open" in state


def _state_source_priority(state: Any) -> int:
    if not isinstance(state, dict):
        return 0
    return _STATE_SOURCE_PRIORITY.get(str(state.get("source") or "").strip().lower(), 25)


def update_state(client_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """Save the latest state for a Unity client and return the stored record."""
    normalized_client_id = _normalize_client_id(client_id)

    record = {
        "client_id": normalized_client_id,
        "state": state,
        "timestamp": time.time(),
    }

    with _state_lock:
        existing = _state.get(normalized_client_id)
        if existing is not None:
            existing_state = existing.get("state")
            if (
                _state_source_priority(existing_state) > _state_source_priority(state)
                and time.time() - float(existing.get("timestamp", 0.0) or 0.0) < 5.0
            ):
                return existing
        _state[normalized_client_id] = record

    return record


def get_state(client_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the most recent valid Unity robot state for a client, if any."""
    normalized_client_id = _normalize_client_id(client_id)

    with _state_lock:
        record = _state.get(normalized_client_id)
        if record is not None:
            if _looks_like_robot_state_payload(record.get("state")):
                return record
            return None

        if normalized_client_id.lower() in _AUTO_CLIENT_IDS and len(_state) == 1:
            fallback = next(iter(_state.values()))
            if _looks_like_robot_state_payload(fallback.get("state")):
                return fallback

        return None


def list_clients() -> Dict[str, float]:
    """Return a lightweight view of connected clients and timestamps."""

    with _state_lock:
        return {cid: rec.get("timestamp", 0.0) for cid, rec in _state.items()}


def update_image(client_id: str, image_record: Dict[str, Any]) -> Dict[str, Any]:
    """Save the latest image payload for a Unity client and return the stored record."""
    normalized_client_id = _normalize_client_id(client_id)

    record = {
        "client_id": normalized_client_id,
        **(image_record if isinstance(image_record, dict) else {"raw": image_record}),
        "timestamp": time.time(),
    }

    with _image_lock:
        _image[normalized_client_id] = record

    return record


def get_image(client_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the most recent image payload for a Unity client, if any."""
    normalized_client_id = _normalize_client_id(client_id)

    with _image_lock:
        record = _image.get(normalized_client_id)
        if record is not None:
            return record

        if normalized_client_id.lower() in _AUTO_CLIENT_IDS and len(_image) == 1:
            return next(iter(_image.values()))

        return None


def list_image_clients() -> Dict[str, float]:
    """Return a lightweight view of connected image clients and timestamps."""

    with _image_lock:
        return {cid: rec.get("timestamp", 0.0) for cid, rec in _image.items()}


def update_lidar(client_id: str, lidar_record: Dict[str, Any]) -> Dict[str, Any]:
    """Save the latest LiDAR payload for a Unity client and return the stored record."""
    normalized_client_id = _normalize_client_id(client_id)

    record = {
        "client_id": normalized_client_id,
        **(lidar_record if isinstance(lidar_record, dict) else {"raw": lidar_record}),
        "timestamp": time.time(),
    }

    with _lidar_lock:
        _lidar[normalized_client_id] = record

    return record


def get_lidar(client_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the most recent LiDAR payload for a client, if any."""
    normalized_client_id = _normalize_client_id(client_id)

    with _lidar_lock:
        record = _lidar.get(normalized_client_id)
        if record is not None:
            return record

        if normalized_client_id.lower() in _AUTO_CLIENT_IDS and len(_lidar) == 1:
            return next(iter(_lidar.values()))

        return None


def list_lidar_clients() -> Dict[str, float]:
    """Return a lightweight view of connected LiDAR clients and timestamps."""

    with _lidar_lock:
        return {cid: rec.get("timestamp", 0.0) for cid, rec in _lidar.items()}
