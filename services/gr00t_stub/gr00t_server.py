# services/gr00t_stub/gr00t_server.py

from __future__ import annotations

import re
from typing import Any, Dict

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="gr00t-stub", version="1.0.0")

_NUMBER_PATTERN = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


class InferRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    instruction: str = ""
    prompt: str = ""
    image: Any = ""
    image_url: str = ""
    state: Dict[str, Any] = Field(default_factory=dict)
    robot_state: Dict[str, Any] = Field(default_factory=dict)
    model_name: str = "nvidia/GR00T-N1.7-3B"
    embodiment_tag: str = "humanoid"
    inference_mode: str = "pytorch"
    action_horizon: int = 8
    action_format: str = ""
    unity_command: str = ""
    waypoint_speed: Any = None


def _coerce_positive_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        return default
    return parsed if parsed > 0.0 else default


def _vec3(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None
    try:
        return [float(value[0]), float(value[1]), float(value[2])]
    except Exception:
        return None


def _goal_from_state(req: InferRequest) -> list[float] | None:
    state = req.robot_state or req.state or {}
    if not isinstance(state, dict):
        return None
    return _vec3(state.get("goal_position")) or _vec3(state.get("target_position"))


def _goal_from_prompt(prompt: str) -> list[float] | None:
    text = str(prompt or "")
    xyz_pattern = re.compile(
        rf"\bx\s*[:=]\s*({_NUMBER_PATTERN})\D+"
        rf"\by\s*[:=]\s*({_NUMBER_PATTERN})\D+"
        rf"\bz\s*[:=]\s*({_NUMBER_PATTERN})",
        re.IGNORECASE,
    )
    xyz_match = xyz_pattern.search(text)
    if xyz_match:
        return [
            float(xyz_match.group(1)),
            float(xyz_match.group(2)),
            float(xyz_match.group(3)),
        ]

    bracket_pattern = re.compile(
        rf"[\[\(]\s*({_NUMBER_PATTERN})\s*,\s*({_NUMBER_PATTERN})\s*,\s*({_NUMBER_PATTERN})\s*[\]\)]"
    )
    bracket_match = bracket_pattern.search(text)
    if bracket_match:
        return [
            float(bracket_match.group(1)),
            float(bracket_match.group(2)),
            float(bracket_match.group(3)),
        ]

    return None


def _speed_from_prompt(prompt: str, default: float) -> float:
    text = str(prompt or "").lower()
    if any(word in text for word in ("slow", "slowly", "careful", "천천히", "조심")):
        return min(default, 0.5)
    if any(word in text for word in ("fast", "quick", "quickly", "빨리", "빠르게")):
        return max(default, 1.5)
    return default


def _direction_from_prompt(prompt: str) -> tuple[float, float, float, str]:
    text = prompt.lower()
    move_x = 0.0
    move_z = 0.8
    turn = 0.0
    intent = "forward"

    wants_turn = any(word in text for word in ("turn", "rotate", "회전", "돌아", "돌기"))
    wants_walk = any(word in text for word in ("walk", "move", "go", "advance", "forward", "이동", "걸어", "전진", "앞"))
    slight = any(word in text for word in ("slight", "slightly", "little", "조금", "살짝"))

    if any(word in text for word in ("left", "왼쪽", "좌측")):
        move_x = -0.35
        move_z = 0.45 if wants_walk or not wants_turn else 0.0
        turn = -0.2 if slight else -0.45
        intent = "left"
    elif any(word in text for word in ("right", "오른쪽", "우측")):
        move_x = 0.35
        move_z = 0.45 if wants_walk or not wants_turn else 0.0
        turn = 0.2 if slight else 0.45
        intent = "right"

    if any(word in text for word in ("back", "backward", "뒤", "후진", "뒤로")):
        move_x = 0.0 if not any(word in text for word in ("left", "right", "왼쪽", "오른쪽")) else move_x
        move_z = -0.45
        intent = "backward"

    if wants_turn and not wants_walk and move_z > 0.0:
        move_z = 0.0
        intent = "turn"

    if any(word in text for word in ("stop", "halt", "정지", "멈춰")):
        move_x = 0.0
        move_z = 0.0
        turn = 0.0
        intent = "stop"

    if any(word in text for word in ("checkpoint", "waypoint", "target", "목표", "체크포인트")):
        intent = "checkpoint"

    return move_x, move_z, turn, intent


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "gr00t-stub",
        "model": "nvidia/GR00T-N1.7-3B",
        "note": "Demo adapter shape for VLA Graph; replace with an Isaac-GR00T policy server for real inference.",
    }


@app.post("/infer")
def infer(req: InferRequest):
    prompt = req.instruction or req.prompt
    command = str(req.unity_command or "").strip().lower()
    action_format = str(req.action_format or "").strip().lower()
    embodiment = str(req.embodiment_tag or "humanoid").strip()
    speed = _speed_from_prompt(prompt, _coerce_positive_float(req.waypoint_speed, 1.0))
    move_x, move_z, turn, intent = _direction_from_prompt(prompt)
    prompt_goal = _goal_from_prompt(prompt)
    stop = move_x == 0.0 and move_z == 0.0 and turn == 0.0 and any(
        word in prompt.lower() for word in ("stop", "halt", "정지", "멈춰")
    )

    if command == "apply_patrol_control" or action_format in {"patrol", "patrol_control"}:
        goal = prompt_goal or _goal_from_state(req)
        action: Dict[str, Any] = {
            "type": "unity_patrol_action",
            "command": "apply_patrol_control",
            "patrol_mode": "target" if goal is not None else "direction",
            "patrol_speed": speed,
            "translation": [move_x, 0.0, move_z],
            "rotation": [0.0, turn, 0.0],
            "stop": stop,
            "terminate": False,
        }
        if goal is not None:
            action["patrol_target_position"] = goal
        else:
            action["patrol_direction"] = [move_x, 0.0, move_z]
    elif command == "apply_base_waypoint" or action_format in {"unity_waypoint", "waypoint"}:
        goal = prompt_goal or _goal_from_state(req)
        action = {
            "type": "unity_waypoint_action",
            "command": "apply_base_waypoint",
            "target_position": goal or [move_x, 0.0, move_z],
            "target_rotation": [0.0, turn, 0.0],
            "translation": [move_x, 0.0, move_z],
            "rotation": [0.0, turn, 0.0],
            "speed": speed,
            "stop": stop,
            "gripper": "noop",
            "terminate": False,
        }
    elif command == "apply_humanoid_step" or "humanoid" in embodiment.lower():
        action = {
            "type": "unity_humanoid_action",
            "command": "apply_humanoid_step",
            "move_x": move_x,
            "move_z": move_z,
            "turn_yaw": turn,
            "speed": speed,
            "stop": stop,
            "terminate": False,
        }
    else:
        action = {
            "type": "delta_action",
            "translation": [move_x * 0.05, 0.0, move_z * 0.05],
            "rotation": [0.0, turn * 0.05, 0.0],
            "gripper": "noop",
            "terminate": False,
        }

    action["prompt_intent"] = intent
    if prompt_goal is not None:
        action["prompt_goal"] = prompt_goal

    return {
        "ok": True,
        "service": "gr00t-stub",
        "model": req.model_name,
        "model_name": req.model_name,
        "embodiment_tag": embodiment,
        "inference_mode": req.inference_mode,
        "action_horizon": req.action_horizon,
        "action": action,
        "actions": [action],
        "debug": {
            "instruction": prompt,
            "prompt_intent": intent,
            "prompt_goal": prompt_goal,
            "speed": speed,
            "image_present": bool(req.image or req.image_url),
            "state_keys": sorted((req.robot_state or req.state or {}).keys()),
            "action_format": req.action_format,
            "unity_command": req.unity_command,
        },
    }
