"""Launch VLA Graph Isaac Sim bridge for /World/GR00T_Humanoid with camera streaming."""

from __future__ import annotations

import sys
from pathlib import Path


script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from groot_bridge_config import apply_groot_bridge_env


apply_groot_bridge_env(camera=True)

exec(open(r"C:\Users\0\Desktop\vlagraph\examples\isaacsim\VlaGraphIsaacSimBridge.py").read())
