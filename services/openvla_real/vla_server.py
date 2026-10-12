# services/openvla_real/vla_server.py
from __future__ import annotations

import base64
import io
import json
import logging
import math
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from urllib.request import urlopen

import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field
from transformers import AutoModelForVision2Seq, AutoProcessor

logger = logging.getLogger("openvla_real")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


MODEL_NAME = os.getenv("OPENVLA_MODEL_NAME", "openvla/openvla-7b")
DEVICE = os.getenv("DEVICE", "cuda:0" if torch.cuda.is_available() else "cpu")
DTYPE_NAME = os.getenv("DTYPE", "bfloat16" if DEVICE.startswith("cuda") else "float32")
ATTN_IMPLEMENTATION = os.getenv(
    "ATTN_IMPLEMENTATION",
    "flash_attention_2" if DEVICE.startswith("cuda") else "",
)
DEFAULT_UNNORM_KEY = os.getenv("OPENVLA_UNNORM_KEY", "bridge_orig")
PRELOAD_MODEL = env_bool("PRELOAD_MODEL", False)
AUTO_WARMUP = env_bool("AUTO_WARMUP", False)
GRIPPER_OPEN_THRESHOLD = float(os.getenv("GRIPPER_OPEN_THRESHOLD", "0.1"))
GRIPPER_CLOSE_THRESHOLD = float(os.getenv("GRIPPER_CLOSE_THRESHOLD", "-0.1"))
IMAGE_DOWNLOAD_TIMEOUT_SEC = float(os.getenv("IMAGE_DOWNLOAD_TIMEOUT_SEC", "10"))
DEFAULT_ACTION_FORMAT = os.getenv("OPENVLA_ACTION_FORMAT", "delta_action").strip().lower() or "delta_action"
DEFAULT_WAYPOINT_SPEED = env_float("OPENVLA_WAYPOINT_SPEED", 1.5)

SYSTEM_PROMPT = (
    "A chat between a curious user and an artificial intelligence assistant. "
    "The assistant gives helpful, detailed, and polite answers to the user's questions."
)

app = FastAPI(title="OPENVLA Real Server", version="1.1.0")


class InferRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    image_url: str = ""
    instruction: str = ""
    robot_state: Dict[str, Any] = Field(default_factory=dict)
    model_name: str = MODEL_NAME

    # Backward-compatible fields
    image: Any = ""
    prompt: str = ""
    state: Dict[str, Any] = Field(default_factory=dict)
    unnorm_key: Optional[str] = None
    action_format: Optional[str] = None
    unity_command: Optional[str] = None
    waypoint_speed: Optional[float] = None


def _resolve_dtype(name: str) -> torch.dtype:
    normalized = name.strip().lower()
    if normalized in {"bf16", "bfloat16"}:
        return torch.bfloat16
    if normalized in {"fp16", "float16", "half"}:
        return torch.float16
    return torch.float32


def _format_vec_text(values: Any, *, dims: int = 3) -> str:
    if not isinstance(values, (list, tuple)) or len(values) < dims:
        return ""
    try:
        clipped = [float(v) for v in list(values)[:dims]]
    except Exception:
        return ""
    return "(" + ", ".join(f"{value:.2f}" for value in clipped) + ")"


def _format_lidar_state_text(robot_state: Dict[str, Any]) -> str:
    lidar_summary = robot_state.get("lidar_summary")
    if isinstance(lidar_summary, str) and lidar_summary.strip():
        return lidar_summary.strip()

    lidar = robot_state.get("lidar")
    if not isinstance(lidar, dict):
        return ""

    parts: List[str] = []
    nearest = lidar.get("nearest_range")
    if isinstance(nearest, (int, float)):
        parts.append(f"nearest_obstacle={float(nearest):.2f}m")
    obstacle_count = lidar.get("obstacle_count")
    if isinstance(obstacle_count, int):
        parts.append(f"near_obstacle_rays={obstacle_count}")
    point_count = lidar.get("point_count")
    if isinstance(point_count, int):
        parts.append(f"lidar_points={point_count}")

    sectors = lidar.get("sectors")
    if isinstance(sectors, dict):
        sector_parts: List[str] = []
        for name in ("front", "left", "right", "rear"):
            sector = sectors.get(name)
            if not isinstance(sector, dict):
                continue
            min_range = sector.get("min_range")
            if isinstance(min_range, (int, float)):
                sector_parts.append(f"{name}={float(min_range):.2f}m")
        if sector_parts:
            parts.append("sector_min_ranges(" + ", ".join(sector_parts) + ")")

    return ", ".join(parts)


def _summarize_robot_state(robot_state: Dict[str, Any]) -> str:
    if not isinstance(robot_state, dict) or not robot_state:
        return ""

    parts: List[str] = []
    robot_type = str(robot_state.get("robot_type") or "").strip()
    controller_mode = str(robot_state.get("controller_mode") or "").strip()
    object_name = str(robot_state.get("object_name") or "").strip()
    position_text = _format_vec_text(robot_state.get("position"))
    rotation_text = _format_vec_text(robot_state.get("rotation"))
    velocity_text = _format_vec_text(robot_state.get("velocity"))
    goal_text = _format_vec_text(robot_state.get("goal_position"))
    distance_to_goal = robot_state.get("distance_to_goal")
    has_line_of_sight = robot_state.get("has_line_of_sight")
    stuck = robot_state.get("stuck")

    if robot_type:
        parts.append(f"robot_type={robot_type}")
    if controller_mode:
        parts.append(f"controller_mode={controller_mode}")
    if object_name:
        parts.append(f"object={object_name}")
    if position_text:
        parts.append(f"position={position_text}")
    if rotation_text:
        parts.append(f"rotation={rotation_text}")
    if velocity_text:
        parts.append(f"velocity={velocity_text}")
    if goal_text:
        parts.append(f"goal_position={goal_text}")
    if isinstance(distance_to_goal, (int, float)) and float(distance_to_goal) >= 0.0:
        parts.append(f"distance_to_goal={float(distance_to_goal):.2f}")
    if has_line_of_sight is not None:
        parts.append(f"has_line_of_sight={bool(has_line_of_sight)}")
    if stuck is not None:
        parts.append(f"stuck={bool(stuck)}")
    if "gripper_open" in robot_state:
        parts.append(f"gripper_open={bool(robot_state.get('gripper_open'))}")
    lidar_text = _format_lidar_state_text(robot_state)
    if lidar_text:
        parts.append(lidar_text)

    return ", ".join(parts[:16])


def _build_prompt(
    instruction: str,
    model_name: str,
    robot_state: Optional[Dict[str, Any]] = None,
) -> str:
    text = instruction.strip()
    if not text:
        raise HTTPException(status_code=400, detail="instruction or prompt is required")

    state_summary = _summarize_robot_state(robot_state or {})
    task_text = (
        "The image is the humanoid's forward-facing camera view. "
        "Infer the next safe movement toward the target described by the instruction."
    )
    if state_summary:
        task_text += f" Current humanoid state: {state_summary}."
    task_text += f" Instruction: {text}"

    # 일부 OpenVLA 계열 구현체는 v01 prompt 스타일을 사용
    if "v01" in model_name.lower():
        return f"{SYSTEM_PROMPT} USER: What action should the robot take next? {task_text} ASSISTANT:"
    return f"In: What action should the robot take next? {task_text}\nOut:"


def _open_image_from_bytes(raw: bytes) -> Image.Image:
    try:
        with Image.open(io.BytesIO(raw)) as image:
            return ImageOps.exif_transpose(image).convert("RGB")
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Could not decode image bytes") from exc


def _array_to_pil(array_like: Any) -> Image.Image:
    array = np.asarray(array_like)

    if array.ndim != 3:
        raise HTTPException(status_code=400, detail="Array image must have shape [H, W, C]")

    if array.shape[2] not in {1, 3, 4}:
        raise HTTPException(
            status_code=400,
            detail="Array image channel count must be 1, 3, or 4",
        )

    if array.dtype != np.uint8:
        # 0~1 float or arbitrary numeric -> uint8로 보정
        if np.issubdtype(array.dtype, np.floating):
            array = np.clip(array, 0.0, 1.0) * 255.0
        array = np.clip(array, 0, 255).astype(np.uint8)

    if array.shape[2] == 1:
        array = np.repeat(array, 3, axis=2)
    elif array.shape[2] == 4:
        array = array[:, :, :3]

    return Image.fromarray(array).convert("RGB")


def _load_image(image_input: Any) -> Image.Image:
    if isinstance(image_input, list):
        return _array_to_pil(image_input)

    if isinstance(image_input, np.ndarray):
        return _array_to_pil(image_input)

    if not isinstance(image_input, str):
        raise HTTPException(
            status_code=400,
            detail="image must be a string path/URL/data-uri/base64 or RGB array",
        )

    image_ref = image_input.strip()
    if not image_ref:
        raise HTTPException(status_code=400, detail="image_url or image is required")

    if image_ref.startswith("data:"):
        try:
            _, encoded = image_ref.split(",", 1)
            return _open_image_from_bytes(base64.b64decode(encoded))
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid data URI image payload") from exc

    if image_ref.startswith("base64:"):
        try:
            return _open_image_from_bytes(base64.b64decode(image_ref[len("base64:"):]))
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid base64 image payload") from exc

    parsed = urlparse(image_ref)
    if parsed.scheme in {"http", "https"}:
        try:
            with urlopen(image_ref, timeout=IMAGE_DOWNLOAD_TIMEOUT_SEC) as response:
                return _open_image_from_bytes(response.read())
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not download image: {exc}") from exc

    if parsed.scheme == "file":
        image_path = Path(parsed.path)
    else:
        image_path = Path(image_ref).expanduser()

    if not image_path.exists():
        raise HTTPException(status_code=400, detail=f"Image not found: {image_ref}")

    try:
        with Image.open(image_path) as image:
            return ImageOps.exif_transpose(image).convert("RGB")
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail=f"Unsupported image file: {image_ref}") from exc


def _move_inputs_to_device(
    inputs: Dict[str, Any],
    device: torch.device,
    dtype: torch.dtype,
) -> Dict[str, Any]:
    moved: Dict[str, Any] = {}
    for key, value in inputs.items():
        if torch.is_tensor(value):
            if torch.is_floating_point(value):
                moved[key] = value.to(device=device, dtype=dtype)
            else:
                moved[key] = value.to(device=device)
        else:
            moved[key] = value
    return moved


def _action_to_list(action: Any) -> List[float]:
    if isinstance(action, torch.Tensor):
        values = action.detach().float().cpu().reshape(-1).tolist()
    elif isinstance(action, np.ndarray):
        values = action.astype(np.float32).reshape(-1).tolist()
    elif isinstance(action, (list, tuple)):
        values = np.asarray(action, dtype=np.float32).reshape(-1).tolist()
    else:
        raise HTTPException(status_code=500, detail=f"Unsupported action type: {type(action)!r}")

    return [float(v) for v in values]


def _decode_gripper(gripper_value: float) -> str:
    if gripper_value >= GRIPPER_OPEN_THRESHOLD:
        return "open"
    if gripper_value <= GRIPPER_CLOSE_THRESHOLD:
        return "close"
    return "noop"


def _normalize_vec3(values: Any) -> Optional[List[float]]:
    if not isinstance(values, (list, tuple)) or len(values) < 3:
        return None

    output: List[float] = []
    for value in list(values)[:3]:
        try:
            output.append(float(value))
        except Exception:
            return None
    return output


def _extract_state_vec3(robot_state: Dict[str, Any], key: str) -> Optional[List[float]]:
    if not isinstance(robot_state, dict):
        return None

    direct = _normalize_vec3(robot_state.get(key))
    if direct is not None:
        return direct

    if key == "position":
        pose = _normalize_vec3(robot_state.get("eef_pose"))
        if pose is not None:
            return pose

    if key == "rotation":
        pose = robot_state.get("eef_pose")
        if isinstance(pose, (list, tuple)) and len(pose) >= 6:
            return _normalize_vec3(list(pose)[3:6])

    return None


def _coerce_positive_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        return default
    return parsed if parsed > 0.0 else default


def _rotate_local_delta_by_yaw(local_delta: List[float], yaw_deg: float) -> List[float]:
    yaw_rad = math.radians(yaw_deg)
    cos_yaw = math.cos(yaw_rad)
    sin_yaw = math.sin(yaw_rad)
    return [
        (local_delta[0] * cos_yaw) + (local_delta[2] * sin_yaw),
        local_delta[1],
        (-local_delta[0] * sin_yaw) + (local_delta[2] * cos_yaw),
    ]


def _resolve_action_format(req: InferRequest) -> str:
    requested_command = str(req.unity_command or "").strip().lower()
    requested_format = str(req.action_format or "").strip().lower()
    if requested_format:
        return requested_format
    if requested_command == "apply_patrol_control":
        return "patrol_control"
    if requested_command == "apply_base_waypoint":
        return "unity_waypoint"
    return DEFAULT_ACTION_FORMAT


def _format_action_payload(
    action_payload: Dict[str, Any],
    robot_state: Dict[str, Any],
    req: InferRequest,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    action_format = _resolve_action_format(req)
    if action_format in {"patrol", "patrol_control", "apply_patrol_control"}:
        translation = _normalize_vec3(action_payload.get("translation")) or [0.0, 0.0, 1.0]
        rotation_delta = _normalize_vec3(action_payload.get("rotation")) or [0.0, 0.0, 0.0]
        goal_position = _extract_state_vec3(robot_state, "goal_position")
        waypoint_speed = _coerce_positive_float(req.waypoint_speed, DEFAULT_WAYPOINT_SPEED)
        patrol_action: Dict[str, Any] = {
            "type": "unity_patrol_action",
            "command": "apply_patrol_control",
            "patrol_mode": "target" if goal_position is not None else "direction",
            "patrol_speed": waypoint_speed,
            "stop": bool(action_payload.get("terminate", False)),
            "translation": translation,
            "rotation": rotation_delta,
        }
        if goal_position is not None:
            patrol_action["patrol_target_position"] = goal_position
        else:
            patrol_action["patrol_direction"] = translation
        return patrol_action, {
            "action_format": action_format,
            "action_format_fallback": "",
            "goal_position_used": goal_position is not None,
            "robot_state_used": goal_position is not None,
            "warning": "",
        }

    if action_format not in {"unity_waypoint", "apply_base_waypoint", "waypoint"}:
        return action_payload, {
            "action_format": action_format,
            "action_format_fallback": "",
            "goal_position_used": False,
            "robot_state_used": False,
            "warning": "",
        }

    current_position = _extract_state_vec3(robot_state, "position")
    current_rotation = _extract_state_vec3(robot_state, "rotation") or [0.0, 0.0, 0.0]
    goal_position = _extract_state_vec3(robot_state, "goal_position")
    if current_position is None:
        fallback_action = dict(action_payload)
        fallback_action["command"] = "apply_action"
        warning = "robot_state.position missing; falling back to apply_action delta payload"
        return fallback_action, {
            "action_format": action_format,
            "action_format_fallback": "delta_action",
            "goal_position_used": False,
            "robot_state_used": False,
            "warning": warning,
        }

    translation = _normalize_vec3(action_payload.get("translation")) or [0.0, 0.0, 0.0]
    rotation_delta = _normalize_vec3(action_payload.get("rotation")) or [0.0, 0.0, 0.0]
    world_delta = _rotate_local_delta_by_yaw(translation, current_rotation[1])
    waypoint_speed = _coerce_positive_float(req.waypoint_speed, DEFAULT_WAYPOINT_SPEED)
    target_position = (
        goal_position
        if goal_position is not None
        else [
            current_position[0] + world_delta[0],
            current_position[1],
            current_position[2] + world_delta[2],
        ]
    )

    return {
        "type": "unity_waypoint_action",
        "command": "apply_base_waypoint",
        "target_position": target_position,
        "target_rotation": [
            current_rotation[0] + rotation_delta[0],
            current_rotation[1] + rotation_delta[1],
            current_rotation[2] + rotation_delta[2],
        ],
        "speed": waypoint_speed,
        "stop": bool(action_payload.get("terminate", False)),
        "gripper": action_payload.get("gripper", "noop"),
        "translation": translation,
        "rotation": rotation_delta,
    }, {
        "action_format": action_format,
        "action_format_fallback": "",
        "goal_position_used": goal_position is not None,
        "robot_state_used": True,
        "warning": "",
    }


def _action_to_payload(action_values: List[float]) -> Dict[str, Any]:
    padded = list(action_values[:7])
    while len(padded) < 7:
        padded.append(0.0)

    gripper_value = float(padded[6])
    return {
        "type": "delta_action",
        "translation": [float(v) for v in padded[:3]],
        "rotation": [float(v) for v in padded[3:6]],
        "gripper": _decode_gripper(gripper_value),
        "gripper_value": gripper_value,
        "terminate": False,
    }


class OpenVLAService:
    def __init__(
        self,
        model_name: str,
        device_name: str,
        dtype_name: str,
        attn_implementation: str,
        default_unnorm_key: Optional[str],
    ) -> None:
        self.model_name = model_name
        self.device_name = device_name
        self.device = torch.device(device_name)
        self.dtype_name = dtype_name
        self.dtype = _resolve_dtype(dtype_name)
        self.attn_implementation = attn_implementation.strip()
        self.default_unnorm_key = default_unnorm_key

        self.processor: Any = None
        self.model: Any = None
        self.loaded_attn_implementation = "unloaded"
        self.load_error: Optional[str] = None
        self._lock = threading.Lock()
        self._warmup_in_progress = False
        self._warmup_started = False

    @property
    def loaded(self) -> bool:
        return self.processor is not None and self.model is not None

    @property
    def warming_up(self) -> bool:
        return self._warmup_in_progress

    def start_background_warmup(self) -> bool:
        with self._lock:
            if self.loaded or self._warmup_in_progress:
                return False
            self._warmup_in_progress = True

        def _runner() -> None:
            try:
                logger.info("Starting OpenVLA background warm-up for model=%s", self.model_name)
                self.ensure_loaded()
            except Exception:
                logger.exception("OpenVLA background warm-up failed")
            finally:
                with self._lock:
                    self._warmup_in_progress = False
                    self._warmup_started = True

        thread = threading.Thread(
            target=_runner,
            name="openvla-real-warmup",
            daemon=True,
        )
        thread.start()
        return True

    def _candidate_attn_implementations(self) -> List[Optional[str]]:
        candidates: List[Optional[str]] = []
        if self.attn_implementation:
            candidates.append(self.attn_implementation)

        if self.device.type == "cuda":
            candidates.extend(["flash_attention_2", "sdpa", None])
        else:
            candidates.append(None)

        deduped: List[Optional[str]] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = candidate or "__default__"
            if key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)
        return deduped

    def _attach_local_norm_stats(self) -> None:
        model_path = Path(self.model_name)
        stats_path = model_path / "dataset_statistics.json"
        if not model_path.is_dir() or not stats_path.exists():
            return

        with open(stats_path, "r", encoding="utf-8") as handle:
            self.model.norm_stats = json.load(handle)

    def ensure_loaded(self) -> None:
        if self.loaded:
            return

        with self._lock:
            if self.loaded:
                return

            errors: List[str] = []

            try:
                processor = AutoProcessor.from_pretrained(
                    self.model_name,
                    trust_remote_code=True,
                )
            except Exception as exc:
                self.load_error = f"processor load failed: {exc}"
                raise RuntimeError(
                    f"Failed to load OpenVLA processor {self.model_name}: {exc}"
                ) from exc

            for candidate in self._candidate_attn_implementations():
                kwargs: Dict[str, Any] = {
                    "torch_dtype": self.dtype,
                    "low_cpu_mem_usage": True,
                    "trust_remote_code": True,
                }
                if candidate:
                    kwargs["attn_implementation"] = candidate

                try:
                    model = AutoModelForVision2Seq.from_pretrained(self.model_name, **kwargs)
                    model = model.to(self.device)
                    model.eval()

                    self.processor = processor
                    self.model = model
                    self.loaded_attn_implementation = candidate or "default"
                    self.load_error = None
                    self._attach_local_norm_stats()

                    logger.info(
                        "Loaded OpenVLA model=%s device=%s dtype=%s attn=%s",
                        self.model_name,
                        self.device,
                        self.dtype_name,
                        self.loaded_attn_implementation,
                    )
                    return
                except Exception as exc:
                    errors.append(f"{candidate or 'default'}: {exc}")

            self.load_error = "; ".join(errors)
            raise RuntimeError(f"Failed to load OpenVLA model {self.model_name}: {self.load_error}")

    def health(self) -> Dict[str, Any]:
        if PRELOAD_MODEL:
            note = "Loads during startup because PRELOAD_MODEL=true."
        elif AUTO_WARMUP:
            note = "Starts background warm-up after startup because AUTO_WARMUP=true."
        else:
            note = "Loads lazily on first request unless PRELOAD_MODEL=true or AUTO_WARMUP=true."

        return {
            "ok": True,
            "service": "openvla_real",
            "model_name": self.model_name,
            "device": str(self.device),
            "dtype": self.dtype_name,
            "attn_implementation": self.loaded_attn_implementation,
            "default_unnorm_key": self.default_unnorm_key,
            "loaded": self.loaded,
            "warming_up": self.warming_up,
            "warmup_started": self._warmup_started,
            "load_error": self.load_error,
            "note": note,
        }

    def predict(self, req: InferRequest) -> Dict[str, Any]:
        instruction = str(req.instruction or req.prompt or "").strip()
        if not instruction:
            raise HTTPException(status_code=400, detail="instruction or prompt is required")

        image_input = req.image_url if req.image_url else req.image
        image = _load_image(image_input)

        robot_state = req.robot_state or req.state or {}
        unnorm_key = req.unnorm_key if req.unnorm_key is not None else self.default_unnorm_key
        if unnorm_key == "":
            unnorm_key = None

        self.ensure_loaded()

        prompt = _build_prompt(instruction, self.model_name, robot_state)

        try:
            # 중요: return_tensors="pt"를 명시해 실제 모델 입력을 안정적으로 텐서화
            model_inputs = self.processor(
                images=image,
                text=prompt,
                return_tensors="pt",
            )
        except TypeError:
            # 일부 remote code 구현체 호환 fallback
            try:
                model_inputs = self.processor(
                    prompt,
                    image,
                    return_tensors="pt",
                )
            except Exception as exc:
                logger.exception("OpenVLA processor encoding failed")
                raise HTTPException(status_code=500, detail=f"Processor encoding failed: {exc}") from exc
        except Exception as exc:
            logger.exception("OpenVLA processor encoding failed")
            raise HTTPException(status_code=500, detail=f"Processor encoding failed: {exc}") from exc

        model_inputs = _move_inputs_to_device(model_inputs, self.device, self.dtype)

        try:
            with torch.inference_mode():
                action = self.model.predict_action(
                    **model_inputs,
                    unnorm_key=unnorm_key,
                    do_sample=False,
                )
        except Exception as exc:
            logger.exception("OpenVLA inference failed")
            raise HTTPException(status_code=500, detail=f"OpenVLA inference failed: {exc}") from exc

        raw_action = _action_to_list(action)
        action_payload = _action_to_payload(raw_action)
        formatted_action, action_meta = _format_action_payload(action_payload, robot_state, req)

        requested_model_name = str(req.model_name or "").strip() or self.model_name
        model_name_mismatch = requested_model_name != self.model_name

        return {
            "ok": True,
            "service": "openvla_real",
            "model": self.model_name,
            "model_name": self.model_name,
            "requested_model_name": requested_model_name,
            "instruction": instruction,
            "prompt_text": prompt,
            "image_url": req.image_url if isinstance(req.image_url, str) else "",
            "robot_state": robot_state,
            "unnorm_key": unnorm_key,
            "action": formatted_action,
            "raw_action": raw_action,
            "meta": {
                "source": "openvla_real",
                "device": str(self.device),
                "dtype": self.dtype_name,
                "attn_implementation": self.loaded_attn_implementation,
                "robot_state_used": action_meta["robot_state_used"],
                "prompt_state_used": bool(_summarize_robot_state(robot_state)),
                "action_format": action_meta["action_format"],
                "action_format_fallback": action_meta["action_format_fallback"],
                "goal_position_used": action_meta["goal_position_used"],
                "model_name_mismatch": model_name_mismatch,
                "warning": (
                    "request.model_name is not used for hot-swapping in this server instance"
                    if model_name_mismatch
                    else ""
                ),
                "action_warning": action_meta["warning"],
            },
        }


service = OpenVLAService(
    model_name=MODEL_NAME,
    device_name=DEVICE,
    dtype_name=DTYPE_NAME,
    attn_implementation=ATTN_IMPLEMENTATION,
    default_unnorm_key=DEFAULT_UNNORM_KEY,
)


@app.on_event("startup")
def preload_model() -> None:
    if PRELOAD_MODEL:
        try:
            service.ensure_loaded()
        except Exception:
            logger.exception("Model preload failed")
        return

    if AUTO_WARMUP:
        service.start_background_warmup()


@app.get("/health")
def health() -> Dict[str, Any]:
    return service.health()


@app.post("/infer")
def infer(req: InferRequest) -> Dict[str, Any]:
    return service.predict(req)


@app.post("/act")
def act(req: InferRequest) -> Dict[str, Any]:
    result = service.predict(req)
    return {
        "ok": True,
        "service": "openvla_real",
        "model": result["model"],
        "unnorm_key": result["unnorm_key"],
        "action": result["raw_action"],
        "meta": result["meta"],
    }

