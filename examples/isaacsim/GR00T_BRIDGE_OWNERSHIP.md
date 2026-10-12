# GR00T Isaac Sim Bridge Ownership

This setup intentionally uses two Isaac-side bridges.

## robotis.omy.motion

- Location: `C:/isaac_exts/robotis.omy.motion`
- Port: `9899`
- Owns the Isaac UI window named `Isaac G1 VLA Graph Bridge`.
- Owns scene creation/reset for `/World/GR00T_Humanoid`.
- Its Init button runs scene init first, then calls the VLAGRAPH 9900 reset when that bridge is loaded.

## vlagraph.bridge.autostart

- Location: `C:/isaac_exts/vlagraph.bridge.autostart`
- Starts: `C:/Users/0/Desktop/vlagraph/examples/isaacsim/StartVlaGraphBridge9900.py`
- Port: `9900`
- Owns VLA Graph command execution, scene scan, state/image publishing, and root/cache reset.
- Uses `examples/isaacsim/groot_bridge_config.py` for all GR00T defaults.

## Root Motion Rule

Move the wrapper prim:

```text
/World/GR00T_Humanoid
```

Do not use the articulation child as the root motion prim:

```text
-/World/GR00T_Humanoid/G1
```

The child is for articulation/joint control. Applying root motion there can double-count height and make the humanoid appear at a different or floating location after Init.

## Unified Init Order

Frontend `Init GR00T Scene` and Isaac UI `Init` should both produce this order:

```text
9899 scene init -> 9900 VLAGRAPH bridge reset
```

Expected 9900 state after reload:

```text
bridge_build: 2026-06-24-wrapper-root-home-v27
root_motion_prim_path: /World/GR00T_Humanoid
root_pose_use_articulation_api: false
position z: about 0.768
```
