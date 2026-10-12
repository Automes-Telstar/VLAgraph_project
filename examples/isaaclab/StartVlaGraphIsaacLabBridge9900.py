from __future__ import annotations

import os
from pathlib import Path


os.environ.setdefault("VLAGRAPH_CLIENT_ID", "isaaclab01")
os.environ.setdefault("VLAGRAPH_OMNIVERSE_HOST", "0.0.0.0")
os.environ.setdefault("VLAGRAPH_OMNIVERSE_PORT", "9900")
os.environ.setdefault("VLAGRAPH_OMNIVERSE_PATH", "/omniverse")
os.environ.setdefault("VLAGRAPH_ISAACLAB_TASK", "Isaac-Cartpole-Direct-v0")
os.environ.setdefault("VLAGRAPH_ISAACLAB_NUM_ENVS", "1")
os.environ.setdefault("VLAGRAPH_ISAACLAB_DEVICE", "cuda:0")
os.environ.setdefault("VLAGRAPH_ISAACLAB_HEADLESS", "false")


bridge_path = Path(__file__).resolve().parent / "VlaGraphIsaacLabBridge.py"
exec(compile(bridge_path.read_text(encoding="utf-8"), str(bridge_path), "exec"))
