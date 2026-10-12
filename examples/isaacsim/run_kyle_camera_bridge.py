"""Launch VLA Graph Isaac Sim bridge for /World/KyleRobot with camera streaming."""

from __future__ import annotations

import os


os.environ["VLAGRAPH_BACKEND_BASE"] = "http://localhost:9000"
os.environ["VLAGRAPH_CLIENT_ID"] = "isaacsim01"
os.environ["VLAGRAPH_ROBOT_PRIM"] = "/World/KyleRobot"
os.environ["VLAGRAPH_ROBOT_TYPE"] = "humanoid"
os.environ["VLAGRAPH_CONTROLLER_MODE"] = "locomotion"

os.environ["VLAGRAPH_SEND_IMAGE"] = "true"
os.environ["VLAGRAPH_AUTO_ATTACH_CAMERA"] = "true"
os.environ["VLAGRAPH_CAMERA_WIDTH"] = "640"
os.environ["VLAGRAPH_CAMERA_HEIGHT"] = "360"
os.environ["VLAGRAPH_IMAGE_INTERVAL_SEC"] = "0.5"
os.environ["VLAGRAPH_CAMERA_LOCAL_POSITION"] = "0,2.55796,-4.08236"
os.environ["VLAGRAPH_CAMERA_LOCAL_ROTATION_DEG"] = "-194.14137,1.0457,-179.11757"
os.environ["VLAGRAPH_CAMERA_LOCAL_SCALE"] = "1,1,1"
os.environ["VLAGRAPH_PRINT_PROMPTS"] = "true"
os.environ["VLAGRAPH_TURN_SIGN"] = "-1"
os.environ["VLAGRAPH_ROTATION_SIGN"] = "1,1,-1"
os.environ["VLAGRAPH_ENFORCE_HUMANOID_JOINT_LIMITS"] = "true"
os.environ["VLAGRAPH_HUMANOID_JOINT_LIMIT_SCALE"] = "0.95"
os.environ["VLAGRAPH_HUMANOID_JOINT_MAX_DELTA_RAD"] = "0.35"
os.environ["VLAGRAPH_RESET_HUMANOID_ON_FIRST_COMMAND"] = "true"
os.environ["VLAGRAPH_RESTORE_ROOT_ON_STOP"] = "false"
os.environ["VLAGRAPH_HUMANOID_DRIVE_STIFFNESS"] = "180"
os.environ["VLAGRAPH_HUMANOID_DRIVE_DAMPING"] = "24"
os.environ["VLAGRAPH_FREEZE_HUMANOID_WHEN_IDLE"] = "true"
os.environ["VLAGRAPH_HUMANOID_IDLE_TIMEOUT_SEC"] = "0.4"
os.environ["VLAGRAPH_NEUTRALIZE_HUMANOID_WHEN_IDLE"] = "true"
os.environ["VLAGRAPH_DISABLE_ANIMATION_FOR_ARTICULATION"] = "true"
os.environ["VLAGRAPH_APPLY_TRAJECTORY_ROOT_TRANSLATION"] = "true"
os.environ["VLAGRAPH_LOCK_TRAJECTORY_ROOT_ROTATION"] = "false"

os.environ["VLAGRAPH_ENABLE_ANIMATION"] = "true"
os.environ["VLAGRAPH_PLAY_TIMELINE"] = "true"
os.environ["VLAGRAPH_PLAY_TIMELINE_ON_START"] = "false"
os.environ["VLAGRAPH_ANIMATION_LOOP"] = "true"
os.environ["VLAGRAPH_SKELETON_PRIM"] = "/World/KyleRobot/ROOT/Hips/Skeleton"
os.environ["VLAGRAPH_ANIMATION_PRIM"] = "/World/KyleRobot/Take_001"
os.environ["VLAGRAPH_POSE_ANIMATION_PRIM"] = "/World/KyleRobot/VlaGraphPoseAnimation"

exec(open(r"C:\Users\0\Desktop\vlagraph\examples\isaacsim\VlaGraphIsaacSimBridge.py").read())
