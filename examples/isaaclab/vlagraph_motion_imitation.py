from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

import gymnasium as gym


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except Exception:
        return default
    return parsed if math.isfinite(parsed) else default


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "detach"):
        try:
            value = value.detach().cpu()
        except Exception:
            return str(value)
    if hasattr(value, "tolist"):
        try:
            return value.tolist()
        except Exception:
            return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def _first_numeric(value: Any) -> float | None:
    if hasattr(value, "detach"):
        try:
            value = value.detach().cpu()
        except Exception:
            return None
    if hasattr(value, "reshape"):
        try:
            flattened = value.reshape(-1)
            if len(flattened) > 0:
                return float(flattened[0])
        except Exception:
            pass
    if isinstance(value, (list, tuple)) and value:
        return _first_numeric(value[0])
    try:
        return float(value)
    except Exception:
        return None


class MotionTraceTarget:
    """Small adapter from VLA Graph MediaPipe traces to low-dimensional intent."""

    def __init__(self, trace_path: str | Path) -> None:
        self.path = Path(trace_path).expanduser()
        self.trace = self._load_trace(self.path)
        self.label = self._label_from_trace(self.trace)
        self.summary = self.trace.get("summary") if isinstance(self.trace.get("summary"), dict) else {}
        self.frames = self.trace.get("frames") if isinstance(self.trace.get("frames"), list) else []
        self.duration_sec = self._duration_sec()
        self.command = self._command_from_label()

    @staticmethod
    def _load_trace(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"VLA Graph motion trace not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError(f"Motion trace must be a JSON object: {path}")
        return payload

    @staticmethod
    def _label_from_trace(trace: dict[str, Any]) -> str:
        summary = trace.get("summary") if isinstance(trace.get("summary"), dict) else {}
        labels = summary.get("heuristic_labels")
        if isinstance(labels, list) and labels:
            return _text(labels[-1])
        return _text(summary.get("primary_skill") or trace.get("label") or trace.get("motionLabel") or "motion")

    def _duration_sec(self) -> float:
        video = self.trace.get("video") if isinstance(self.trace.get("video"), dict) else {}
        duration = _as_float(video.get("duration_sec") or video.get("durationSec"), 0.0)
        if duration > 0:
            return duration
        timestamps = [
            _as_float(frame.get("timestamp_sec"), 0.0)
            for frame in self.frames
            if isinstance(frame, dict)
        ]
        return max(timestamps) - min(timestamps) if len(timestamps) >= 2 else 2.0

    def _command_from_label(self) -> dict[str, float]:
        label = self.label.lower().replace("-", "_")
        labels = " ".join([label] + [str(item).lower() for item in self.summary.get("heuristic_labels", [])])
        command = {"forward": 0.0, "lateral": 0.0, "yaw": 0.0, "arm": 0.0}
        if any(token in labels for token in ("walk", "forward", "body_translation", "leg_motion")):
            command["forward"] = 1.0
        if "back" in labels:
            command["forward"] = -1.0
        if "left" in labels:
            command["yaw"] = 0.7
        if "right" in labels:
            command["yaw"] = -0.7
        if "arm" in labels or "raised" in labels:
            command["arm"] = 0.8
        return command

    def target_action_like(self, action: Any) -> Any:
        """Return a small normalized action target with the same backend type as action."""
        values = [self.command["forward"], self.command["lateral"], self.command["yaw"], self.command["arm"]]
        if hasattr(action, "detach"):
            import torch

            flat = torch.zeros_like(action).reshape(-1)
            source = torch.as_tensor(values, dtype=flat.dtype, device=flat.device)
            flat[: min(flat.numel(), source.numel())] = source[: min(flat.numel(), source.numel())]
            return flat.reshape_as(action)

        try:
            import numpy as np

            arr = np.zeros_like(action, dtype=np.float32).reshape(-1)
            src = np.asarray(values, dtype=np.float32)
            arr[: min(arr.size, src.size)] = src[: min(arr.size, src.size)]
            return arr.reshape(getattr(action, "shape", (-1,)))
        except Exception:
            return values

    def frame_at_step(self, step: int, dt: float) -> dict[str, Any]:
        if not self.frames:
            return {}
        duration = max(self.duration_sec, dt, 1.0e-6)
        t = (float(step) * dt) % duration
        best = min(
            (frame for frame in self.frames if isinstance(frame, dict)),
            key=lambda frame: abs(_as_float(frame.get("timestamp_sec"), 0.0) - t),
            default={},
        )
        return best if isinstance(best, dict) else {}


class VlaGraphMotionImitationWrapper(gym.Wrapper):
    """Adds a light MediaPipe imitation reward and optional VLA Graph telemetry."""

    def __init__(
        self,
        env: gym.Env,
        *,
        trace_path: str | Path,
        reward_weight: float = 0.05,
        action_scale: float = 1.0,
        publish_interval: int = 100,
        client_id: str = "isaaclab-motion-train",
        backend_ws: str = "",
    ) -> None:
        super().__init__(env)
        self.motion_target = MotionTraceTarget(trace_path)
        self.reward_weight = max(0.0, float(reward_weight))
        self.action_scale = max(1.0e-6, float(action_scale))
        self.publish_interval = max(0, int(publish_interval))
        self.client_id = client_id
        self.backend_ws = backend_ws
        self.step_count = 0
        self.started_at = time.time()
        self._ws = None
        print(
            "[VlaGraphMotionImitation] enabled "
            f"trace={self.motion_target.path} label={self.motion_target.label} "
            f"weight={self.reward_weight}"
        )

    def step(self, action: Any) -> Any:
        result = self.env.step(action)
        if isinstance(result, tuple) and len(result) >= 5:
            obs, reward, terminated, truncated, info = result[:5]
            rest = result[5:]
            reward, imitation = self._add_imitation_reward(reward, action)
            self.step_count += 1
            self._publish(action, reward, imitation, info)
            return (obs, reward, terminated, truncated, info, *rest)
        if isinstance(result, tuple) and len(result) >= 4:
            obs, reward, done, info = result[:4]
            rest = result[4:]
            reward, imitation = self._add_imitation_reward(reward, action)
            self.step_count += 1
            self._publish(action, reward, imitation, info)
            return (obs, reward, done, info, *rest)
        return result

    def _add_imitation_reward(self, reward: Any, action: Any) -> tuple[Any, float]:
        if self.reward_weight <= 0.0:
            return reward, 0.0
        target = self.motion_target.target_action_like(action)
        imitation_value = 0.0
        if hasattr(action, "detach"):
            import torch

            error = ((action - target) / self.action_scale).pow(2)
            while error.ndim > 1:
                error = error.mean(dim=-1)
            bonus = self.reward_weight * torch.exp(-error)
            imitation_value = float(bonus.mean().detach().cpu())
            return reward + bonus, imitation_value

        try:
            import numpy as np

            error = np.square((np.asarray(action) - np.asarray(target)) / self.action_scale)
            while error.ndim > 1:
                error = error.mean(axis=-1)
            bonus = self.reward_weight * np.exp(-error)
            imitation_value = float(np.mean(bonus))
            return reward + bonus, imitation_value
        except Exception:
            return reward, imitation_value

    def _publish(self, action: Any, reward: Any, imitation: float, info: Any) -> None:
        if self.publish_interval <= 0 or self.step_count % self.publish_interval != 0:
            return
        frame = self.motion_target.frame_at_step(
            self.step_count,
            _as_float(getattr(self.unwrapped, "step_dt", 0.0), 0.0) or 1.0 / 60.0,
        )
        payload = {
            "type": "robot_state",
            "client_id": self.client_id,
            "source": "isaaclab_motion_imitation",
            "step_count": self.step_count,
            "uptime_sec": round(time.time() - self.started_at, 3),
            "motion_label": self.motion_target.label,
            "motion_command": self.motion_target.command,
            "imitation_reward": imitation,
            "reward_preview": _first_numeric(reward),
            "action_preview": _json_safe(action),
            "motion_frame": _json_safe(frame),
            "info_preview": _json_safe(info),
        }
        if not self.backend_ws:
            if self.step_count == self.publish_interval:
                print("[VlaGraphMotionImitation] telemetry websocket disabled")
            return
        try:
            if self._ws is None:
                from websocket import create_connection

                self._ws = create_connection(self.backend_ws, timeout=1.0)
            self._ws.send(json.dumps(payload, ensure_ascii=False))
            try:
                self._ws.recv()
            except Exception:
                pass
        except Exception as exc:
            print(f"[VlaGraphMotionImitation] telemetry publish failed: {exc}")
            self._close_ws()

    def _close_ws(self) -> None:
        if self._ws is None:
            return
        try:
            self._ws.close()
        except Exception:
            pass
        self._ws = None

    def close(self) -> None:
        self._close_ws()
        return self.env.close()
