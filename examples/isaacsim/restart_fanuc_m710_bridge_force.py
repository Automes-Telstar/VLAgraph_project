r"""Force-restart the VLA Graph Isaac Sim bridge for FANUC M-710 on port 9910.

Run inside Isaac Sim Script Editor:

    exec(open(r"C:\Users\0\Desktop\vlagraph\examples\isaacsim\restart_fanuc_m710_bridge_force.py").read())
"""

from __future__ import annotations

import builtins
import runpy
import socket
import sys
import time
from pathlib import Path


REGISTRY_KEY = "_VLAGRAPH_ISAACSIM_BRIDGE"
BRIDGE_RUNNER = Path(r"C:\Users\0\Desktop\vlagraph\examples\isaacsim\StartFanucM710Bridge9910.py")
PORT = 9910
CONFLICT_TOKENS = (
    "fanuc",
    "m710",
    "m_710",
    "vlagraph_fanuc",
    "vlagraph_isaacsim_bridge",
)


def _port_open(host: str = "127.0.0.1", port: int = PORT, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _looks_conflicting(name: str) -> bool:
    lower = str(name or "").replace("-", "_").lower()
    return any(token in lower for token in CONFLICT_TOKENS)


def _call_stop(obj: object, label: str) -> bool:
    stopped = False
    for method_name in ("shutdown", "stop", "close"):
        method = getattr(obj, method_name, None)
        if callable(method):
            try:
                method()
                print(f"[VlaGraphIsaacSimBridge] stopped {label}.{method_name}()")
                stopped = True
            except Exception as exc:
                print(f"[VlaGraphIsaacSimBridge] failed stopping {label}.{method_name}(): {exc}")
    return stopped


def _stop_conflicting_python_objects() -> None:
    for name in dir(builtins):
        if not _looks_conflicting(name):
            continue
        obj = getattr(builtins, name, None)
        if obj is not None and _call_stop(obj, f"builtins.{name}"):
            try:
                delattr(builtins, name)
            except Exception:
                pass

    for module_name, module in list(sys.modules.items()):
        if not module or not _looks_conflicting(module_name):
            continue
        _call_stop(module, module_name)
        bridge = getattr(module, "_BRIDGE", None)
        if bridge is not None:
            _call_stop(bridge, f"{module_name}._BRIDGE")


old_bridge = getattr(builtins, REGISTRY_KEY, None)
if old_bridge is not None:
    try:
        old_bridge.stop()
        print("[VlaGraphIsaacSimBridge] stopped bridge from builtins registry")
        time.sleep(0.5)
    except Exception as exc:
        print(f"[VlaGraphIsaacSimBridge] registry bridge stop failed: {exc}")
    finally:
        if hasattr(builtins, REGISTRY_KEY):
            delattr(builtins, REGISTRY_KEY)

_stop_conflicting_python_objects()
time.sleep(0.5)

if _port_open():
    print(
        f"[VlaGraphIsaacSimBridge] port {PORT} is still in use after registry stop. "
        "An older FANUC bridge is still active outside the script registry. "
        "Restart Isaac Sim, then run this script again."
    )
else:
    runpy.run_path(str(BRIDGE_RUNNER), run_name="__main__")
