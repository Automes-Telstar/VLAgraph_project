from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except Exception:
        return default


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except Exception:
        if hasattr(value, "detach"):
            try:
                value = value.detach().cpu().numpy()
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


def _preview(value: Any, limit: int = 4000) -> Any:
    safe = _json_safe(value)
    text = json.dumps(safe, ensure_ascii=False)
    if len(text) <= limit:
        return safe
    return {"preview": text[:limit], "truncated": True, "bytes": len(text)}


@dataclass
class IsaacLabRuntime:
    task: str
    num_envs: int = 1
    device: str = "cuda:0"
    headless: bool = False
    env: Any = None
    simulation_app: Any = None
    last_observation: Any = None
    last_reward: Any = None
    last_terminated: Any = None
    last_truncated: Any = None
    last_info: Any = None
    step_count: int = 0
    started_at: float = field(default_factory=time.time)

    def start(self) -> None:
        if self.env is not None:
            return

        try:
            from isaaclab.app import AppLauncher
        except Exception as exc:
            raise RuntimeError(
                "Isaac Lab is not importable in this Python environment. "
                "Run this bridge with Isaac Lab's python.sh/python.bat."
            ) from exc

        launcher_args = argparse.Namespace(
            headless=self.headless,
            device=self.device,
            enable_cameras=_env_bool("VLAGRAPH_ISAACLAB_ENABLE_CAMERAS", False),
        )
        self.simulation_app = AppLauncher(launcher_args).app

        import gymnasium as gym
        import isaaclab_tasks  # noqa: F401 - required for gym task registration

        kwargs: Dict[str, Any] = {}
        if self.num_envs > 0:
            kwargs["num_envs"] = self.num_envs
        self.env = gym.make(self.task, **kwargs)
        self.reset()

    def close(self) -> None:
        if self.env is not None:
            try:
                self.env.close()
            except Exception:
                pass
            self.env = None
        if self.simulation_app is not None:
            try:
                self.simulation_app.close()
            except Exception:
                pass
            self.simulation_app = None

    def reset(self) -> Dict[str, Any]:
        self.start() if self.env is None else None
        result = self.env.reset()
        if isinstance(result, tuple) and len(result) >= 2:
            observation, info = result[0], result[1]
        else:
            observation, info = result, {}
        self.last_observation = observation
        self.last_reward = None
        self.last_terminated = None
        self.last_truncated = None
        self.last_info = info
        self.step_count = 0
        return self.state_payload(message="Isaac Lab environment reset.")

    def action_from_payload(self, payload: Dict[str, Any]) -> Any:
        action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
        raw = (
            action.get("isaaclab_action")
            or action.get("isaacLabAction")
            or action.get("action")
            or action.get("joint_positions")
            or action.get("jointTargets")
            or action.get("joint_targets")
        )
        if raw is None and any(key in action for key in ("move_x", "move_z", "turn_yaw")):
            raw = [float(action.get("move_x", 0.0)), float(action.get("move_z", 0.0)), float(action.get("turn_yaw", 0.0))]
        if raw is None:
            raw = 0.0
        return self._coerce_action(raw)

    def _coerce_action(self, raw: Any) -> Any:
        space = getattr(self.env, "action_space", None)
        try:
            import numpy as np
            import torch
        except Exception:
            np = None
            torch = None

        if isinstance(raw, dict):
            raw = list(raw.values())

        shape = getattr(space, "shape", None)
        if torch is not None:
            tensor = torch.as_tensor(raw, dtype=torch.float32, device=self.device)
            if shape:
                flat = tensor.flatten()
                target_size = int(shape[-1])
                if flat.numel() == 1 and target_size > 1:
                    flat = flat.repeat(target_size)
                if flat.numel() < target_size:
                    pad = torch.zeros(target_size - flat.numel(), dtype=flat.dtype, device=flat.device)
                    flat = torch.cat([flat, pad], dim=0)
                flat = flat[:target_size]
                tensor = flat.reshape((1, target_size)).repeat(max(1, self.num_envs), 1)
            return tensor

        if np is not None:
            arr = np.asarray(raw, dtype=np.float32).reshape(-1)
            if shape:
                target_size = int(shape[-1])
                if arr.size == 1 and target_size > 1:
                    arr = np.repeat(arr, target_size)
                if arr.size < target_size:
                    arr = np.pad(arr, (0, target_size - arr.size))
                arr = arr[:target_size].reshape((1, target_size))
            return arr
        return raw

    def step(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.start() if self.env is None else None
        action = self.action_from_payload(payload)
        result = self.env.step(action)
        if isinstance(result, tuple) and len(result) >= 5:
            observation, reward, terminated, truncated, info = result[:5]
        elif isinstance(result, tuple) and len(result) >= 4:
            observation, reward, done, info = result[:4]
            terminated, truncated = done, False
        else:
            observation, reward, terminated, truncated, info = result, None, False, False, {}
        self.last_observation = observation
        self.last_reward = reward
        self.last_terminated = terminated
        self.last_truncated = truncated
        self.last_info = info
        self.step_count += 1
        return self.state_payload(
            action=action,
            message=f"Isaac Lab step applied count={self.step_count}.",
        )

    def state_payload(self, *, action: Any = None, message: str = "Isaac Lab state ready.") -> Dict[str, Any]:
        return {
            "ok": True,
            "type": "robot_state",
            "client_id": os.environ.get("VLAGRAPH_CLIENT_ID", "isaaclab01"),
            "source": "isaaclab",
            "task": self.task,
            "num_envs": self.num_envs,
            "device": self.device,
            "step_count": self.step_count,
            "uptime_sec": round(time.time() - self.started_at, 3),
            "observation": _preview(self.last_observation),
            "reward": _json_safe(self.last_reward),
            "terminated": _json_safe(self.last_terminated),
            "truncated": _json_safe(self.last_truncated),
            "info": _preview(self.last_info),
            "action": _preview(action) if action is not None else None,
            "message": message,
        }


class VlaGraphIsaacLabBridge:
    def __init__(self) -> None:
        self.host = os.environ.get("VLAGRAPH_OMNIVERSE_HOST", "0.0.0.0")
        self.port = _env_int("VLAGRAPH_OMNIVERSE_PORT", 9900)
        self.path = os.environ.get("VLAGRAPH_OMNIVERSE_PATH", "/omniverse")
        self.runtime = IsaacLabRuntime(
            task=os.environ.get("VLAGRAPH_ISAACLAB_TASK", "Isaac-Cartpole-Direct-v0"),
            num_envs=_env_int("VLAGRAPH_ISAACLAB_NUM_ENVS", 1),
            device=os.environ.get("VLAGRAPH_ISAACLAB_DEVICE", "cuda:0"),
            headless=_env_bool("VLAGRAPH_ISAACLAB_HEADLESS", False),
        )

    async def start(self) -> None:
        import websockets

        if _env_bool("VLAGRAPH_ISAACLAB_START_ENV_ON_BOOT", True):
            self.runtime.start()
        async with websockets.serve(self._handle_client, self.host, self.port):
            print(f"[VlaGraphIsaacLabBridge] listening ws://{self.host}:{self.port}{self.path}")
            print(f"[VlaGraphIsaacLabBridge] task={self.runtime.task} num_envs={self.runtime.num_envs}")
            await asyncio.Future()

    async def _handle_client(self, websocket: Any) -> None:
        async for raw in websocket:
            response = self._handle_message(raw)
            await websocket.send(json.dumps(response, ensure_ascii=False))

    def _handle_message(self, raw: str) -> Dict[str, Any]:
        request_id = ""
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError(f"expected JSON object, got {type(payload).__name__}")
            request_id = str(payload.get("request_id") or uuid.uuid4())
            command = str(payload.get("command") or "execute_policy").strip().lower()
            if command in {"reset", "reset_scene", "init", "initialize"}:
                state = self.runtime.reset()
                applied = True
            elif command in {"scan_scene", "state", "get_state", "observe"}:
                state = self.runtime.state_payload(message="Isaac Lab state scanned.")
                applied = False
            elif command in {"execute_policy", "isaaclab_step", "step", "apply_action"}:
                state = self.runtime.step(payload)
                applied = True
            else:
                return self._ack(request_id, command, False, False, message=f"Unsupported Isaac Lab command: {command}")
            return self._ack(request_id, command, True, applied, state=state, message=state.get("message"))
        except Exception as exc:
            return self._ack(request_id or str(uuid.uuid4()), "error", False, False, message=str(exc))

    def _ack(
        self,
        request_id: str,
        command: str,
        ok: bool,
        applied: bool,
        *,
        state: Dict[str, Any] | None = None,
        message: str = "",
    ) -> Dict[str, Any]:
        payload = {
            "ok": ok,
            "type": "omniverse_ack",
            "request_id": request_id,
            "applied": applied,
            "command": command,
            "source": "isaaclab",
            "message": message,
        }
        if state:
            payload.update(
                {
                    "state": state,
                    "observation": state.get("observation"),
                    "reward": state.get("reward"),
                    "terminated": state.get("terminated"),
                    "truncated": state.get("truncated"),
                    "info": state.get("info"),
                }
            )
        return payload


def startup(port: int | None = None) -> None:
    if port is not None:
        os.environ["VLAGRAPH_OMNIVERSE_PORT"] = str(port)
    bridge = VlaGraphIsaacLabBridge()
    try:
        asyncio.run(bridge.start())
    finally:
        bridge.runtime.close()


if __name__ == "__main__":
    startup()
