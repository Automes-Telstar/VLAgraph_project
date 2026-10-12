from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class GraphNode(BaseModel):
    id: str
    type: str
    position: Dict[str, Any] = Field(default_factory=dict)
    data: Dict[str, Any] = Field(default_factory=dict)

class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = None
    targetHandle: Optional[str] = None
    type: Optional[str] = None
    animated: Optional[bool] = None
    style: Optional[Dict[str, Any]] = None

class GraphRunRequest(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    input: Dict[str, Any] = Field(default_factory=dict)


class GraphRuntimeOptions(BaseModel):
    persistent: Optional[bool] = None
    require_feedback: Optional[bool] = None
    continue_on_error: bool = False
    live_single_context: bool = False
    max_iterations: int = 0
    cycle_interval_sec: float = 0.75
    feedback_timeout_sec: float = 30.0
    log_limit: int = 400


class GraphRuntimeStartRequest(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    input: Dict[str, Any] = Field(default_factory=dict)
    options: GraphRuntimeOptions = Field(default_factory=GraphRuntimeOptions)


class UnityRunRequest(BaseModel):
    prompt: str = "Move RobotKyle to CheckpointA at Unity world coordinate [35.0, 0.0, -10.0] using apply_base_waypoint"
    image: str = ""
    robot_state: Dict[str, Any] = Field(
        default_factory=lambda: {
            "gripper_open": True,
            "eef_pose": [0.1, 0.2, 0.3, 0.0, 0.0, 0.0],
        }
    )
    use_unity_state: bool = False
    state_client_id: str = "default"
    model_name: str = "openvla-stub"
    decode_mode: str = "default"
    safety_enabled: bool = True
    safety_max_delta: float = 0.05
    unity_endpoint: str = "ws://host.docker.internal:9081/robot"
    unity_scene: str = "VALConnect"
    unity_object: str = "RobotKyle"
    unity_command: str = "apply_base_waypoint"
    action_format: str = ""
    waypoint_speed: Optional[float] = None
    unity_robot_type: str = "generic"
    unity_controller_mode: str = "task"
    unity_timeout_sec: float = 5.0


class InferRequest(BaseModel):
    image_url: str = ""
    instruction: str = ""
    robot_state: Dict[str, Any] = Field(default_factory=dict)
    model_name: str = "openvla-stub"


class FineTuneStartRequest(BaseModel):
    dataset_path: str = ""
    base_model: str = "openvla/openvla-7b"
    output_name: str = "openvla-exp"
    epochs: int = 1
    batch_size: int = 2
    learning_rate: float = 1e-4
    lora_enabled: bool = True


class UploadResponse(BaseModel):
    ok: bool = True
    file_name: str
    file_path: str
    content_type: str = "application/octet-stream"
    size_bytes: int = 0
