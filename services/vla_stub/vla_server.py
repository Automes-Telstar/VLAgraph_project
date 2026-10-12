# services/vla_stub/vla_server.py

from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="openvla-stub", version="1.0.0")


class InferRequest(BaseModel):
    prompt: str = ""
    image: str = ""
    state: Dict[str, Any] = Field(default_factory=dict)
    model_name: str = "openvla-stub"
    action_format: str = ""
    unity_command: str = ""
    waypoint_speed: Any = None


def _coerce_positive_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        return default
    return parsed if parsed > 0.0 else default


@app.get("/health")
def health():
    return {"ok": True, "service": "openvla-stub"}


@app.post("/infer")
def infer(req: InferRequest):
    prompt = req.prompt.lower()

    gripper = "noop"
    translation = [0.0, 0.0, 0.02]
    rotation = [0.0, 0.0, 0.0]

    if "pick" in prompt or "grasp" in prompt:
        gripper = "close"
        translation = [0.03, -0.01, 0.05]
    elif "place" in prompt:
        gripper = "open"
        translation = [0.02, 0.01, -0.02]
    elif "push" in prompt:
        gripper = "noop"
        translation = [0.05, 0.00, 0.00]

    action_format = str(req.action_format or "").strip().lower()
    unity_command = str(req.unity_command or "").strip().lower()
    if unity_command == "apply_patrol_control" or action_format in {
        "apply_patrol_control",
        "patrol",
        "patrol_control",
    }:
        speed = _coerce_positive_float(req.waypoint_speed, 1.5)
        action = {
            "type": "unity_patrol_action",
            "command": "apply_patrol_control",
            "patrol_mode": "direction",
            "patrol_direction": translation,
            "patrol_speed": speed,
            "translation": translation,
            "rotation": rotation,
            "terminate": False,
        }
        return {
            "ok": True,
            "model": req.model_name,
            "action": action,
            "debug": {
                "prompt": req.prompt,
                "image": req.image,
                "state": req.state,
                "action_format": req.action_format,
                "unity_command": req.unity_command,
            },
        }

    action = {
        "type": "delta_action",
        "translation": translation,
        "rotation": rotation,
        "gripper": gripper,
        "terminate": False,
    }

    return {
        "ok": True,
        "model": req.model_name,
        "action": action,
        "debug": {
            "prompt": req.prompt,
            "image": req.image,
            "state": req.state,
        },
    }
