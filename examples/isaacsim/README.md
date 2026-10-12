# Isaac Sim Bridge for VLA Graph

`VlaGraphIsaacSimBridge.py` connects Isaac Sim to VLA Graph.

It provides:

- `ws://0.0.0.0:9900/omniverse` command server for `Robot Execute(mode=omniverse)`
- periodic robot state publishing to `http://localhost:9000/ws/unity/state`
- optional camera image publishing to `http://localhost:9000/ws/unity/image`
- persistent backend WebSocket publishing, so backend logs do not show open/close for every state frame

The backend endpoints are named `unity` for compatibility, but the payloads can come from Isaac Sim.

## Install Runtime Dependencies

Inside the Isaac Sim Python environment:

```bash
./python.sh -m pip install websockets pillow
```

On Windows, use the Isaac Sim `python.bat` equivalent.

## Run

Open Isaac Sim, load a stage with a robot prim, then run this from Script Editor:

```python
import os

os.environ["VLAGRAPH_BACKEND_BASE"] = "http://localhost:9000"
os.environ["VLAGRAPH_CLIENT_ID"] = "isaacsim01"
os.environ["VLAGRAPH_ROBOT_PRIM"] = "/World/KyleRobot"
os.environ["VLAGRAPH_ROBOT_TYPE"] = "humanoid"
os.environ["VLAGRAPH_CONTROLLER_MODE"] = "locomotion"

# KyleRobot 아래에 /World/KyleRobot/VlaGraphCamera 를 만들고
# 그 카메라 화면을 VLA Graph backend로 전송합니다.
os.environ["VLAGRAPH_SEND_IMAGE"] = "true"
os.environ["VLAGRAPH_AUTO_ATTACH_CAMERA"] = "true"
os.environ["VLAGRAPH_CAMERA_WIDTH"] = "640"
os.environ["VLAGRAPH_CAMERA_HEIGHT"] = "360"
os.environ["VLAGRAPH_IMAGE_INTERVAL_SEC"] = "0.25"

# 카메라 Transform. Isaac Sim Inspector의 Translate/Rotate/Scale 값과 맞춥니다.
os.environ["VLAGRAPH_CAMERA_LOCAL_POSITION"] = "0,2.55796,-4.08236"
os.environ["VLAGRAPH_CAMERA_LOCAL_ROTATION_DEG"] = "-194.14137,1.0457,-179.11757"
os.environ["VLAGRAPH_CAMERA_LOCAL_SCALE"] = "1,1,1"
os.environ["VLAGRAPH_PRINT_PROMPTS"] = "true"
os.environ["VLAGRAPH_TURN_SIGN"] = "-1"
os.environ["VLAGRAPH_ROTATION_SIGN"] = "1,1,-1"

exec(open(r"C:/Users/0/Desktop/vlagraph/examples/isaacsim/VlaGraphIsaacSimBridge.py").read())
```

If you run the script again in Script Editor, the newer version stops the
previous bridge instance first. If you still see `Errno 10048` for port `9900`,
the old server was started before this safeguard existed. Restart Isaac Sim, or
use a different port:

```python
import os

os.environ["VLAGRAPH_OMNIVERSE_PORT"] = "9900"
exec(open(r"C:/Users/0/Desktop/vlagraph/examples/isaacsim/VlaGraphIsaacSimBridge.py").read())
```

Then set VLA Graph `Robot Execute.omniverseEndpoint` to:

```text
ws://host.docker.internal:9900/omniverse
```

If the VLA Graph backend runs in Docker on the same Windows host, keep:

```text
VLAGRAPH_BACKEND_BASE=http://localhost:9000
```

In the VLA Graph frontend, set `Robot Execute` to:

```text
mode = omniverse
omniverseEndpoint = ws://host.docker.internal:9900/omniverse
omniverseStage = /World
omniversePrimPath = /World/KyleRobot
omniverseCommand = execute_policy
```

If the backend runs directly on the same machine instead of Docker, use:

```text
omniverseEndpoint = ws://localhost:9900/omniverse
```

## Graph Inputs

Use these VLA Graph nodes:

- `Robot State (Unity)` with `clientId=isaacsim01`
- `Remote Image Sensor` with `remoteImageUrl=http://localhost:9000/api/unity/image?client_id=isaacsim01` if camera publishing is enabled
- `NVIDIA GR00T Infer`
- `Robot Execute(mode=omniverse)`

An example graph is available at:

```text
examples/graphs/isaacsim_gr00t_humanoid_graph.json
```

## Environment Variables

```text
VLAGRAPH_OMNIVERSE_HOST=127.0.0.1
VLAGRAPH_OMNIVERSE_PORT=9900
VLAGRAPH_OMNIVERSE_PATH=/omniverse
VLAGRAPH_BACKEND_BASE=http://localhost:9000
VLAGRAPH_CLIENT_ID=isaacsim01
VLAGRAPH_ROBOT_PRIM=/World/KyleRobot
VLAGRAPH_ROBOT_TYPE=humanoid
VLAGRAPH_CONTROLLER_MODE=locomotion
VLAGRAPH_SEND_STATE=true
VLAGRAPH_STATE_INTERVAL_SEC=0.1
VLAGRAPH_SEND_IMAGE=true
VLAGRAPH_AUTO_ATTACH_CAMERA=true
VLAGRAPH_CAMERA_NAME=VlaGraphCamera
VLAGRAPH_CAMERA_PRIM=
VLAGRAPH_CAMERA_LOCAL_POSITION=0,2.55796,-4.08236
VLAGRAPH_CAMERA_LOCAL_ROTATION_DEG=-194.14137,1.0457,-179.11757
VLAGRAPH_CAMERA_LOCAL_SCALE=1,1,1
VLAGRAPH_CAMERA_UPDATE_POSE=true
VLAGRAPH_CAMERA_WIDTH=640
VLAGRAPH_CAMERA_HEIGHT=360
VLAGRAPH_IMAGE_INTERVAL_SEC=0.25
VLAGRAPH_PRINT_PROMPTS=true
VLAGRAPH_TRANSLATION_SCALE=1.0
VLAGRAPH_STEP_SCALE=0.25
VLAGRAPH_TURN_SCALE_DEG=15.0
VLAGRAPH_TURN_SIGN=-1
VLAGRAPH_ROTATION_SCALE_DEG=1.0
VLAGRAPH_ROTATION_SIGN=1,1,-1
VLAGRAPH_POSE_ROTATION_SIGN=1,1,1
```

When `VLAGRAPH_SEND_IMAGE=true` and no `VLAGRAPH_CAMERA_PRIM` is provided, the
bridge creates a child camera at:

```text
/World/KyleRobot/VlaGraphCamera
```

The latest frame is available to graph nodes through:

```text
http://localhost:9000/api/unity/image?client_id=isaacsim01
```

## Prompt Handling

When the VLA Graph FastAPI backend executes `Robot Execute(mode=omniverse)`,
the prompt used by `OpenVLA Infer` or `NVIDIA GR00T Infer` is included in the
WebSocket command payload:

```json
{
  "type": "omniverse_command",
  "prompt": "walk forward toward the checkpoint",
  "instruction": "walk forward toward the checkpoint",
  "action": {
    "move_z": 0.5
  }
}
```

The bridge stores that text as `last_prompt` / `last_instruction`, prints a
short preview in the Isaac Sim console, and includes it in the next
`Robot State (Unity)` payload so graph runtime loops can see the current task.

## Action Support

The bridge handles:

- `translation` / `rotation`
- `target_position` / `target_rotation`
- `move_x` / `move_z` / `turn_yaw`
- `linear_x` / `linear_z` / `angular_yaw`
- `patrol_direction` / `patrol_target_position`
- `joint_targets` / `joint_positions` through Isaac Sim articulation API when available

The transform fallback is intentionally simple. For a production robot, replace `_apply_command` with your robot controller, ROS 2 bridge, ArticulationController, or Isaac Lab policy wrapper.
