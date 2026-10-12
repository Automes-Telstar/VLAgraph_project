from __future__ import annotations

import base64
import json
import math
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

try:
    from backend.config import UPLOAD_DIR
except Exception:
    UPLOAD_DIR = str(Path.cwd() / "uploads")


DEFAULT_DATASET_DIR = Path(UPLOAD_DIR) / "isaaclab_datasets" / "omy3m"
DEFAULT_HOST_ROOT = Path(r"C:\Users\0\Desktop\vlagraph")


def _incoming_values(
    node_id: str,
    edges: List[Dict[str, Any]],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for edge in edges:
        if edge.get("target") != node_id:
            continue
        source_payload = context.get(edge.get("source"))
        if source_payload is None:
            continue
        source_handle = edge.get("sourceHandle")
        value = source_payload
        if source_handle:
            if not isinstance(source_payload, dict) or source_handle not in source_payload:
                continue
            value = source_payload[source_handle]
        key = str(edge.get("targetHandle") or source_handle or edge.get("source"))
        result[key] = value
    return result


def _props(node: Dict[str, Any]) -> Dict[str, Any]:
    value = node.get("data")
    return value if isinstance(value, dict) else {}


def _float_list(value: Any) -> List[float]:
    if isinstance(value, str):
        value = [part for part in re.split(r"[\s,;]+", value.strip()) if part]
    if not isinstance(value, (list, tuple)):
        return []
    result: List[float] = []
    for item in value:
        try:
            parsed = float(item)
        except (TypeError, ValueError):
            continue
        if math.isfinite(parsed):
            result.append(parsed)
    return result


def _text_list(value: Any) -> List[str]:
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,;\n]+", value) if part.strip()]
    if isinstance(value, (list, tuple)):
        return [str(part).strip() for part in value if str(part).strip()]
    return []


def _safe_name(value: Any, default: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip()).strip("._")
    return normalized or default


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "tolist"):
        try:
            return value.tolist()
        except Exception:
            pass
    return str(value)


def exec_omy3m_joint_action(
    node: Dict[str, Any],
    context: Dict[str, Any],
    edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    data = _props(node)
    inputs = _incoming_values(node["id"], edges, context)
    joint_names = _text_list(
        data.get("jointNames")
        or "joint1,joint2,joint3,joint4,joint5,joint6"
    )
    joint_positions = _float_list(
        inputs.get("joint_positions", data.get("jointPositions"))
    )
    if len(joint_names) != 6:
        raise ValueError(f"OMY3M requires six joint names; received {len(joint_names)}")
    if len(joint_positions) != 6:
        raise ValueError(
            f"OMY3M requires six joint positions; received {len(joint_positions)}"
        )

    limit = abs(float(data.get("jointLimitRad", math.pi)))
    clamped = [max(-limit, min(limit, value)) for value in joint_positions]
    gripper_position = float(data.get("gripperPosition", 0.0))
    duration = max(0.0, float(data.get("durationSec", 1.0)))
    prompt = str(inputs.get("prompt") or data.get("prompt") or "").strip()

    action = {
        "type": "omy3m_joint_target",
        "command": "apply_joint_targets",
        "robot_type": "articulated_arm",
        "controller_mode": "joint",
        "joint_names": joint_names,
        "joint_positions": clamped,
        "joint_target_map": dict(zip(joint_names, clamped)),
        "gripper_position": gripper_position,
        "duration_sec": duration,
        "target_embodiment": "OMY3M_6DOF",
    }
    if prompt:
        action["prompt"] = prompt
        action["instruction"] = prompt
    return {
        "action": action,
        "joint_positions": clamped,
        "joint_target_map": action["joint_target_map"],
        "ok": True,
    }


def _dataset_root(value: Any) -> Path:
    text = str(value or "").strip()
    path = Path(text) if text else DEFAULT_DATASET_DIR
    if not path.is_absolute():
        path = Path(UPLOAD_DIR) / path
    return path


def _host_path(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(Path(UPLOAD_DIR).resolve())
    except (OSError, ValueError):
        return str(path)
    host_root = Path(os.getenv("VLAGRAPH_HOST_ROOT") or DEFAULT_HOST_ROOT)
    return str(host_root / "uploads" / relative)


def _save_image(image: Any, image_dir: Path, step_id: str) -> str:
    if isinstance(image, dict):
        image = image.get("image") or image.get("data_url") or image.get("url")
    if not isinstance(image, str) or not image.strip():
        return ""
    value = image.strip()
    if not value.startswith("data:image/") or ";base64," not in value:
        return value

    header, encoded = value.split(",", 1)
    mime = header[5:].split(";", 1)[0].lower()
    extension = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(mime, ".bin")
    image_dir.mkdir(parents=True, exist_ok=True)
    output_path = image_dir / f"{step_id}{extension}"
    output_path.write_bytes(base64.b64decode(encoded, validate=True))
    return str(output_path)


def exec_omy3m_isaaclab_record(
    node: Dict[str, Any],
    context: Dict[str, Any],
    edges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    data = _props(node)
    inputs = _incoming_values(node["id"], edges, context)

    dataset_root = _dataset_root(data.get("datasetPath"))
    episode_name = _safe_name(
        data.get("episodeName"),
        time.strftime("episode_%Y%m%d_%H%M%S"),
    )
    episode_dir = dataset_root / episode_name
    image_dir = episode_dir / "images" / "wrist"
    episode_dir.mkdir(parents=True, exist_ok=True)

    step_id = f"{time.time_ns()}_{uuid.uuid4().hex[:8]}"
    image_path = _save_image(inputs.get("image"), image_dir, step_id)
    state = inputs.get("state") if isinstance(inputs.get("state"), dict) else {}
    action = inputs.get("action") if isinstance(inputs.get("action"), dict) else {}
    result = inputs.get("result") if isinstance(inputs.get("result"), dict) else {}
    instruction = str(inputs.get("prompt") or data.get("instruction") or "").strip()
    success = bool(result.get("ok", data.get("success", True)))
    require_image = bool(data.get("requireImage", True))
    save_failed = bool(data.get("saveFailed", False))

    if not success and not save_failed:
        return {
            "ok": False,
            "saved": False,
            "dataset": {
                "path": str(episode_dir / "steps.jsonl"),
                "host_path": _host_path(episode_dir / "steps.jsonl"),
                "format": "isaaclab_omy3m_jsonl_v1",
            },
            "message": "OMY3M execution failed; training step was not saved.",
            "execution_result": _json_safe(result),
        }
    if require_image and not image_path:
        return {
            "ok": False,
            "saved": False,
            "dataset": {
                "path": str(episode_dir / "steps.jsonl"),
                "host_path": _host_path(episode_dir / "steps.jsonl"),
                "format": "isaaclab_omy3m_jsonl_v1",
            },
            "message": "Wrist camera image is missing; training step was not saved.",
        }
    post_state: Dict[str, Any] = {}
    state_update = result.get("state_update")
    if isinstance(state_update, dict) and isinstance(state_update.get("state"), dict):
        post_state = state_update["state"]
    response = result.get("response")
    if not post_state and isinstance(response, dict) and isinstance(response.get("state"), dict):
        post_state = response["state"]
    if not post_state:
        for message in reversed(result.get("received_messages", [])):
            if isinstance(message, dict) and str(message.get("type", "")).lower() == "robot_state":
                post_state = message
                break

    record = {
        "schema": "vlagraph.isaaclab.omy3m.v1",
        "episode": episode_name,
        "step_id": step_id,
        "timestamp": time.time(),
        "instruction": instruction,
        "observation": {
            "state_before": _json_safe(state),
            "state_after": _json_safe(post_state),
            "wrist_camera_rgb": image_path,
        },
        "commanded_action": _json_safe(action),
        "execution_result": _json_safe(result),
        "reward": float(data.get("reward", 1.0 if success else 0.0)),
        "terminated": bool(data.get("terminated", False)),
        "success": success,
        "robot": {
            "embodiment": "OMY3M_6DOF",
            "prim_path": str(
                data.get("robotPrimPath") or "/World/OMY3M_Learning/Robot"
            ),
            "client_id": str(data.get("clientId") or "isaacsim01"),
        },
    }

    steps_path = episode_dir / "steps.jsonl"
    with steps_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(record, ensure_ascii=False) + "\n")

    metadata_path = episode_dir / "metadata.json"
    metadata = {
        "schema": record["schema"],
        "episode": episode_name,
        "embodiment": "OMY3M_6DOF",
        "joint_names": _text_list(data.get("jointNames")),
        "observation_keys": [
            "state_before.joint_positions",
            "state_before.joint_velocities",
            "state_after.joint_positions",
            "state_after.joint_velocities",
            "state_after.eef_pose",
            "wrist_camera_rgb",
        ],
        "action_keys": ["joint_positions", "gripper_position"],
        "steps_file": str(steps_path),
        "updated_at": record["timestamp"],
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "ok": True,
        "record": record,
        "dataset": {
            "path": str(steps_path),
            "host_path": _host_path(steps_path),
            "format": "isaaclab_omy3m_jsonl_v1",
            "episode_dir": str(episode_dir),
            "episode_dir_host": _host_path(episode_dir),
            "image_path": image_path,
        },
        "message": f"OMY3M Isaac Lab step saved: {steps_path}",
    }
