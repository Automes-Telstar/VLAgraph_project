import os
import sys
import types
from pathlib import Path


script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

bridge_path = script_dir / "VlaGraphIsaacSimBridge.py"
fanuc_e1_axis_prim = (
    "/World/GraphicViewer/Device/LASD/Robot/HFS1/"
    "HFS1_R01_R03/HFS1_7Axis_LH/lnk3"
)

os.environ["VLAGRAPH_BACKEND_BASE"] = "http://localhost:9000"
os.environ["VLAGRAPH_CLIENT_ID"] = "fanuc_m710ic20l_01"
os.environ["VLAGRAPH_OMNIVERSE_PORT"] = "9910"

# Joint targets are applied to the FANUC articulation under Robot.
os.environ["VLAGRAPH_ROBOT_PRIM"] = "/World/GraphicViewer/Device/LASD/Robot/HFS1/HFS1_R01_R03/HFS1_7Axis_LH/lnk3/FANUC_M710/Robot"
os.environ["VLAGRAPH_ARTICULATION_PRIM"] = "/World/GraphicViewer/Device/LASD/Robot/HFS1/HFS1_R01_R03/HFS1_7Axis_LH/lnk3/FANUC_M710/Robot"

# Temporary stable mode: keep the FANUC 6-axis articulation fixed.
# E1 is represented by the FANUC extension as a virtual/visual axis only.
os.environ["VLAGRAPH_ROOT_MOTION_PRIM"] = ""
os.environ["VLAGRAPH_APPLY_TRAJECTORY_ROOT_TRANSLATION"] = "false"

os.environ["VLAGRAPH_ROBOT_TYPE"] = "articulated_arm"
os.environ["VLAGRAPH_CONTROLLER_MODE"] = "joint_position"
os.environ["VLAGRAPH_SEND_STATE"] = "true"
os.environ["VLAGRAPH_STATE_INTERVAL_SEC"] = "0.25"
os.environ["VLAGRAPH_TRAJECTORY_MAX_STEP_SEC"] = "0.15"
os.environ["VLAGRAPH_SEND_IMAGE"] = "false"
os.environ["VLAGRAPH_IMAGE_INTERVAL_SEC"] = "1.0"
os.environ["VLAGRAPH_AUTO_ATTACH_CAMERA"] = "false"
os.environ["VLAGRAPH_PRINT_PROMPTS"] = "true"
os.environ["FANUC_EXTERNAL_AXIS_MOVES_ROBOT_ROOT"] = "0"
os.environ["FANUC_EXTERNAL_AXIS_MOTION_PRIM"] = fanuc_e1_axis_prim
os.environ["FANUC_ANIMATION_MAX_STEP_SEC"] = "0.15"

module_name = "vlagraph_fanuc_m710_bridge_manual"
module = sys.modules.get(module_name)
if module is None:
    module = types.ModuleType(module_name)
    sys.modules[module_name] = module
module.__file__ = str(bridge_path)

exec(compile(bridge_path.read_text(encoding="utf-8"), str(bridge_path), "exec"), module.__dict__)
module.startup(port=9910)
