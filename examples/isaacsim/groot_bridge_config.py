from __future__ import annotations

import os


GROOT_ROBOT_PRIM = "/World/GR00T_Humanoid"
GROOT_ARTICULATION_PRIM = "/World/GR00T_Humanoid/G1"
GROOT_ROOT_MOTION_PRIM = GROOT_ROBOT_PRIM


def apply_groot_bridge_env(*, camera: bool = False) -> None:
    os.environ["VLAGRAPH_OMNIVERSE_HOST"] = "127.0.0.1"
    os.environ["VLAGRAPH_BACKEND_BASE"] = "http://localhost:9000"
    os.environ["VLAGRAPH_CLIENT_ID"] = "isaacsim01"
    os.environ["VLAGRAPH_ROBOT_PRIM"] = GROOT_ROBOT_PRIM
    os.environ["VLAGRAPH_ARTICULATION_PRIM"] = GROOT_ARTICULATION_PRIM
    os.environ["VLAGRAPH_ROOT_MOTION_PRIM"] = GROOT_ROOT_MOTION_PRIM
    os.environ["VLAGRAPH_HOME_ROOT_ROTATION_DEG"] = "0,0,0"
    os.environ["VLAGRAPH_ROBOT_TYPE"] = "humanoid"
    os.environ["VLAGRAPH_CONTROLLER_MODE"] = "locomotion"

    os.environ["VLAGRAPH_APPLY_TRAJECTORY_ROOT_TRANSLATION"] = "true"
    os.environ["VLAGRAPH_LOCK_TRAJECTORY_ROOT_ROTATION"] = "false"
    os.environ["VLAGRAPH_RESTORE_ROOT_ON_STOP"] = "false"
    os.environ["VLAGRAPH_HOLD_ROOT_MOTION_POSE"] = "true"
    os.environ["VLAGRAPH_ROOT_POSE_USE_ARTICULATION_API"] = "false"

    os.environ["VLAGRAPH_ZERO_JOINT_VELOCITIES"] = "false"
    os.environ["VLAGRAPH_RESET_HUMANOID_ON_FIRST_COMMAND"] = "false"
    os.environ["VLAGRAPH_RESET_HUMANOID_EACH_TRAJECTORY"] = "false"
    os.environ["VLAGRAPH_RESET_HUMANOID_AFTER_TRAJECTORY"] = "false"

    os.environ["VLAGRAPH_TURN_SIGN"] = "-1"
    os.environ["VLAGRAPH_ROTATION_SIGN"] = "1,1,-1"
    os.environ["VLAGRAPH_ENFORCE_HUMANOID_JOINT_LIMITS"] = "true"
    os.environ["VLAGRAPH_HUMANOID_JOINT_LIMIT_SCALE"] = "0.95"
    os.environ["VLAGRAPH_HUMANOID_JOINT_MAX_DELTA_RAD"] = "0.35"

    os.environ["VLAGRAPH_FREEZE_HUMANOID_WHEN_IDLE"] = "true"
    os.environ["VLAGRAPH_HUMANOID_IDLE_TIMEOUT_SEC"] = "0.4"
    os.environ["VLAGRAPH_NEUTRALIZE_HUMANOID_WHEN_IDLE"] = "false"
    os.environ["VLAGRAPH_DISABLE_ANIMATION_FOR_ARTICULATION"] = "true"
    os.environ["VLAGRAPH_ENABLE_ANIMATION"] = "false"
    os.environ["VLAGRAPH_PLAY_TIMELINE"] = "false"
    os.environ["VLAGRAPH_PLAY_TIMELINE_ON_START"] = "false"
    os.environ["VLAGRAPH_ANIMATION_LOOP"] = "false"
    os.environ["VLAGRAPH_SKELETON_PRIM"] = ""
    os.environ["VLAGRAPH_ANIMATION_PRIM"] = ""
    os.environ["VLAGRAPH_POSE_ANIMATION_PRIM"] = f"{GROOT_ROBOT_PRIM}/VlaGraphPoseAnimation"

    os.environ["VLAGRAPH_SEND_IMAGE"] = "true" if camera else "false"
    os.environ["VLAGRAPH_IMAGE_INTERVAL_SEC"] = "0.5" if camera else "1.0"
    if camera:
        os.environ["VLAGRAPH_AUTO_ATTACH_CAMERA"] = "true"
        os.environ["VLAGRAPH_CAMERA_WIDTH"] = "640"
        os.environ["VLAGRAPH_CAMERA_HEIGHT"] = "360"
        os.environ["VLAGRAPH_CAMERA_LOCAL_POSITION"] = "0,2.55796,-4.08236"
        os.environ["VLAGRAPH_CAMERA_LOCAL_ROTATION_DEG"] = "-194.14137,1.0457,-179.11757"
        os.environ["VLAGRAPH_CAMERA_LOCAL_SCALE"] = "1,1,1"
