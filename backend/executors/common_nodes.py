# backend/executors/common_nodes.py

from __future__ import annotations

from typing import Any, Dict, List


def _incoming_values(
    node_id: str,
    edges: List[Dict[str, Any]],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    for edge in edges:
        if edge["target"] != node_id:
            continue

        source_id = edge["source"]
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


def exec_prompt(
    node: Dict[str, Any],
    context: Dict[str, Any],
    edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    data = node.get("data", {})
    return {
        "text": data.get("text", ""),
        "label": data.get("label", "Prompt Node"),
    }


def exec_image_input(
    node: Dict[str, Any],
    context: Dict[str, Any],
    edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    data = node.get("data", {})
    return {
        "image": data.get("imageUrl", ""),
        "label": data.get("label", "Image Input Node"),
    }


def exec_robot_state(
    node: Dict[str, Any],
    context: Dict[str, Any],
    edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    data = node.get("data", {})
    return {
        "state": data.get("robotState", {}),
        "label": data.get("label", "Robot State Node"),
    }


def _normalize_vec(values: Any, size: int) -> List[float]:
    if isinstance(values, dict):
        ordered_keys = ["x", "y", "z", "roll", "pitch", "yaw", "w"]
        result: List[float] = []
        for key in ordered_keys:
            if key not in values:
                continue
            try:
                result.append(float(values.get(key, 0.0)))
            except (TypeError, ValueError):
                result.append(0.0)
            if len(result) >= size:
                return result[:size]

    if isinstance(values, (list, tuple)):
        result = []
        for item in list(values)[:size]:
            try:
                result.append(float(item))
            except (TypeError, ValueError):
                result.append(0.0)
        return result

    return []


def _normalize_gripper_open(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"open", "opened", "true", "1"}:
            return True
        if normalized in {"close", "closed", "false", "0"}:
            return False

    return None


def _normalize_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
    return None


def _normalize_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_unity_robot_state(
    raw_state: Any,
    *,
    client_id: str,
    stored_timestamp: Any,
) -> Dict[str, Any]:
    if not isinstance(raw_state, dict):
        return {
            "unity_client_id": client_id,
            "source": "unity_websocket",
            "stored_timestamp": stored_timestamp,
            "raw": raw_state,
        }

    normalized = dict(raw_state)

    position = _normalize_vec(
        raw_state.get("position")
        or raw_state.get("translation")
        or raw_state.get("eef_position"),
        3,
    )
    rotation = _normalize_vec(
        raw_state.get("rotation")
        or raw_state.get("euler")
        or raw_state.get("eef_rotation"),
        3,
    )
    velocity = _normalize_vec(
        raw_state.get("velocity")
        or raw_state.get("linear_velocity"),
        3,
    )
    eef_pose = _normalize_vec(raw_state.get("eef_pose"), 6)
    goal_position = _normalize_vec(
        raw_state.get("goal_position")
        or raw_state.get("goalPosition"),
        3,
    )

    if len(eef_pose) < 6 and position and rotation:
        eef_pose = (position + rotation)[:6]

    gripper_open = _normalize_gripper_open(
        raw_state.get("gripper_open", raw_state.get("gripper"))
    )
    has_line_of_sight = _normalize_bool(raw_state.get("has_line_of_sight"))
    stuck = _normalize_bool(raw_state.get("stuck"))
    distance_to_goal = _normalize_float(raw_state.get("distance_to_goal"))

    if position:
        normalized["position"] = position
    if rotation:
        normalized["rotation"] = rotation
    if velocity:
        normalized["velocity"] = velocity
    if eef_pose:
        normalized["eef_pose"] = eef_pose
    if goal_position:
        normalized["goal_position"] = goal_position
    if gripper_open is not None:
        normalized["gripper_open"] = gripper_open
    if has_line_of_sight is not None:
        normalized["has_line_of_sight"] = has_line_of_sight
    if stuck is not None:
        normalized["stuck"] = stuck
    if distance_to_goal is not None:
        normalized["distance_to_goal"] = distance_to_goal

    normalized["unity_client_id"] = client_id
    normalized["source"] = str(raw_state.get("source") or "unity_websocket")
    normalized["state_transport"] = "unity_websocket"
    normalized["stored_timestamp"] = stored_timestamp
    return normalized


def exec_unity_state(
    node: Dict[str, Any],
    context: Dict[str, Any],
    edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Fetch latest Unity-published state from the backend in-memory store.
    """
    from backend import state_store

    data = node.get("data", {}) or {}
    client_id = str(data.get("clientId", "default")).strip() or "default"

    record = state_store.get_state(client_id)
    if record is None:
        return {
            "ok": False,
            "client_id": client_id,
            "message": "No Unity state received yet.",
            "state": {},
            "raw_state": {},
        }

    raw_state = record.get("state")
    timestamp = record.get("timestamp")
    actual_client_id = str(record.get("client_id", client_id)).strip() or client_id
    normalized_state = _normalize_unity_robot_state(
        raw_state,
        client_id=actual_client_id,
        stored_timestamp=timestamp,
    )

    return {
        "ok": True,
        "client_id": actual_client_id,
        "requested_client_id": client_id,
        "state": normalized_state,
        "timestamp": timestamp,
        "raw_state": raw_state,
        "raw": record,
    }


def exec_print(
    node: Dict[str, Any],
    context: Dict[str, Any],
    edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    inputs = _incoming_values(node["id"], edges, context)
    payload = inputs.get("input", inputs)

    return {
        "printed": payload,
        "ok": True,
    }


def exec_dataset_upload(
    node: Dict[str, Any],
    context: Dict[str, Any],
    edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    data = node.get("data", {})
    return {
        "dataset": {
            "path": data.get("datasetPath", ""),
            "format": data.get("datasetFormat", "jsonl"),
        }
    }


def exec_dataset_preview(
    node: Dict[str, Any],
    context: Dict[str, Any],
    edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    data = node.get("data", {})
    inputs = _incoming_values(node["id"], edges, context)
    dataset = inputs.get("dataset", {})

    return {
        "preview": {
            "dataset": dataset,
            "maxRows": data.get("maxRows", 3),
        }
    }
