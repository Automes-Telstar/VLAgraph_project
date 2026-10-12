import os
import sys
import types
from pathlib import Path


script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from groot_bridge_config import apply_groot_bridge_env


bridge_path = Path(r"C:/Users/0/Desktop/vlagraph/examples/isaacsim/VlaGraphIsaacSimBridge.py")
apply_groot_bridge_env(camera=False)
os.environ["VLAGRAPH_ROBOT_PRIM"] = "/World/OMY3M_Learning/Robot"
os.environ["VLAGRAPH_ARTICULATION_PRIM"] = ""
os.environ["VLAGRAPH_ROOT_MOTION_PRIM"] = "/World/OMY3M_Learning/Robot"
os.environ["VLAGRAPH_ROBOT_TYPE"] = "articulated_arm"
os.environ["VLAGRAPH_CONTROLLER_MODE"] = "joint"

# Low-latency defaults for heavy Isaac Sim scenes.
# RGB readback/JPEG encoding is expensive, so keep camera streaming off unless
# you explicitly need remote images.
os.environ["VLAGRAPH_SEND_STATE"] = "true"
os.environ["VLAGRAPH_STATE_INTERVAL_SEC"] = "0.25"
os.environ["VLAGRAPH_TRAJECTORY_MAX_STEP_SEC"] = "0.15"
os.environ["VLAGRAPH_SEND_IMAGE"] = "false"
os.environ["VLAGRAPH_IMAGE_INTERVAL_SEC"] = "1.0"
os.environ["VLAGRAPH_AUTO_ATTACH_CAMERA"] = "false"
os.environ["VLAGRAPH_CAMERA_PRIM"] = "/World/OMY3M_Learning/Sensors/WristCamera1"
os.environ["VLAGRAPH_CAMERA_UPDATE_POSE"] = "false"
os.environ["VLAGRAPH_CAMERA_WIDTH"] = "320"
os.environ["VLAGRAPH_CAMERA_HEIGHT"] = "240"
module_name = "vlagraph_isaacsim_bridge_manual"
module = types.ModuleType(module_name)
module.__file__ = str(bridge_path)
sys.modules[module_name] = module

exec(compile(bridge_path.read_text(encoding="utf-8"), str(bridge_path), "exec"), module.__dict__)
module.startup(port=9900)
