import asyncio
import importlib.util
import sys
import time
from pathlib import Path
from types import SimpleNamespace


def _load_bridge_module():
    path = Path(__file__).resolve().parents[1] / "examples" / "isaacsim" / "VlaGraphIsaacSimBridge.py"
    spec = importlib.util.spec_from_file_location("vlagraph_isaacsim_bridge_for_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_missing_usd_stage_does_not_crash_update_or_resolution(monkeypatch):
    module = _load_bridge_module()
    bridge = module.VlaGraphIsaacSimBridge()
    monkeypatch.setattr(bridge, "_get_stage", lambda: None)

    assert bridge._valid_prim_path("/World/Robot") is False
    assert bridge._find_robot_prim_candidate() == ""
    assert bridge._resolve_robot_prim_path() == bridge.robot_prim_path

    bridge._on_update(None)
    payload = bridge._build_state_payload(time.time())

    assert payload["type"] == "robot_state"
    assert "USD stage is not available" in payload["message"]


def test_backend_websocket_connection_failures_are_rate_limited(monkeypatch):
    module = _load_bridge_module()
    bridge = module.VlaGraphIsaacSimBridge()
    bridge._backend_ws_retry_interval_sec = 30.0
    attempts = 0

    async def connect(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        raise TimeoutError("timed out during opening handshake")

    monkeypatch.setitem(sys.modules, "websockets", SimpleNamespace(connect=connect))

    async def run_check():
        first = await bridge._get_backend_websocket("state")
        second = await bridge._get_backend_websocket("state")
        return first, second

    first, second = asyncio.run(run_check())

    assert first is None
    assert second is None
    assert attempts == 1
    assert bridge._backend_ws_next_connect_at_by_kind["state"] > time.time()
