# Isaac Lab Bridge for VLA Graph

This folder contains a first-pass Isaac Lab bridge that reuses VLA Graph's existing
`Robot Execute(mode=omniverse)` WebSocket protocol.

The bridge listens on:

```text
ws://0.0.0.0:9900/omniverse
```

and accepts these commands:

- `isaaclab_step`, `execute_policy`, `step`, `apply_action`
- `reset_scene`, `reset`, `init`, `initialize`
- `scan_scene`, `state`, `get_state`, `observe`

## Run

Run it with Isaac Lab's Python environment, not the VLA Graph backend Python.

Linux:

```bash
cd /path/to/IsaacLab
./isaaclab.sh -p C:/Users/0/Desktop/vlagraph/examples/isaaclab/StartVlaGraphIsaacLabBridge9900.py
```

Windows paths depend on your Isaac Lab install. Use the same Python entry point
you normally use for Isaac Lab scripts, then pass:

```text
C:/Users/0/Desktop/vlagraph/examples/isaaclab/StartVlaGraphIsaacLabBridge9900.py
```

If `websockets` is missing in the Isaac Lab Python environment:

```bash
./isaaclab.sh -p -m pip install websockets
```

## Configure

Set environment variables before running the script:

```text
VLAGRAPH_CLIENT_ID=isaaclab01
VLAGRAPH_OMNIVERSE_HOST=0.0.0.0
VLAGRAPH_OMNIVERSE_PORT=9900
VLAGRAPH_ISAACLAB_TASK=Isaac-Cartpole-Direct-v0
VLAGRAPH_ISAACLAB_NUM_ENVS=1
VLAGRAPH_ISAACLAB_DEVICE=cuda:0
VLAGRAPH_ISAACLAB_HEADLESS=false
VLAGRAPH_ISAACLAB_START_ENV_ON_BOOT=true
VLAGRAPH_ISAACLAB_ENABLE_CAMERAS=false
```

In VLA Graph, set the `Robot Execute` node:

```text
mode=omniverse
omniverseEndpoint=ws://host.docker.internal:9900/omniverse
omniverseCommand=isaaclab_step
omniverseWaitForResponse=true
```

If the backend is not running in Docker, use:

```text
omniverseEndpoint=ws://localhost:9900/omniverse
```

## Action Payloads

The bridge first looks for one of these fields in `action`:

```text
isaaclab_action
isaacLabAction
action
joint_positions
jointTargets
joint_targets
```

If none is present, it maps simple locomotion-style actions:

```json
{
  "move_x": 0.0,
  "move_z": 0.25,
  "turn_yaw": 0.0
}
```

The value is padded or trimmed to the Isaac Lab env action space width and sent
to `env.step(action)`.

## Notes

This is intentionally a small adapter. For a production task, specialize
`action_from_payload()` for your Isaac Lab task's action schema and add a richer
observation mapper for cameras, robot root pose, joints, rewards, and task info.
