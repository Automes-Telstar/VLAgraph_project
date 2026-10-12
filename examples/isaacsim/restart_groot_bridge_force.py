r"""Force-restart the VLA Graph Isaac Sim bridge for /World/GR00T_Humanoid.

Run inside Isaac Sim Script Editor:

    exec(open(r"C:\Users\0\Desktop\vlagraph\examples\isaacsim\restart_groot_bridge_force.py").read())
"""

from __future__ import annotations

import builtins
import runpy
import socket
import sys
import time
from pathlib import Path


REGISTRY_KEY = "_VLAGRAPH_ISAACSIM_BRIDGE"
BRIDGE_RUNNER = Path(r"C:\Users\0\Desktop\vlagraph\examples\isaacsim\StartVlaGraphBridge9900.py")
CONFLICT_TOKENS = (
    "isaac_g1_vlagraph_bridge",
    "isaac g1 vla graph bridge",
    "g1_vlagraph",
)


def _port_open(host: str = "127.0.0.1", port: int = 9900, timeout: float = 0.25) -> bool:
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


def _disable_conflicting_extensions() -> None:
    try:
        import omni.kit.app

        manager = omni.kit.app.get_app().get_extension_manager()
        extensions = manager.get_extensions()
    except Exception as exc:
        print(f"[VlaGraphIsaacSimBridge] extension scan skipped: {exc}")
        return

    for extension in extensions or []:
        if not isinstance(extension, dict):
            continue
        ext_id = str(extension.get("id") or extension.get("extension_id") or "")
        display = " ".join(
            str(extension.get(key) or "")
            for key in ("id", "name", "title", "display_name", "path")
        )
        if not _looks_conflicting(display):
            continue
        try:
            manager.set_extension_enabled_immediate(ext_id, False)
            print(f"[VlaGraphIsaacSimBridge] disabled conflicting extension: {ext_id or display}")
        except Exception as exc:
            print(f"[VlaGraphIsaacSimBridge] failed disabling extension {ext_id or display}: {exc}")


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
_disable_conflicting_extensions()
time.sleep(0.5)

if _port_open():
    print(
        "[VlaGraphIsaacSimBridge] port 9900 is still in use after registry stop. "
        "A different Isaac G1 bridge is still active. Disable the 'Isaac G1 VLA Graph Bridge' extension "
        "or restart Isaac Sim, then run this script again."
    )
else:
    runpy.run_path(str(BRIDGE_RUNNER), run_name="__main__")
