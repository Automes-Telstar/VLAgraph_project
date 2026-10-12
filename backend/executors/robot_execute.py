from __future__ import annotations

from typing import Any, Dict

from backend.executors.vla_nodes import (
    _omniverse_execute,
    _ros_execute,
    _simulate_execute,
    _unity_execute,
)


def execute_robot_node(node: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Backward-compatible wrapper around the active robot execute implementation.

    The real graph runtime uses backend.executors.vla_nodes.exec_robot_execute,
    but some older code paths may still import this helper directly.
    """

    data = node.get("data", {}) or {}
    mode = str(data.get("mode", "simulate")).lower().strip()
    action = inputs.get("action")

    if action is None:
        return {
            "result": {
                "ok": False,
                "mode": mode,
                "message": "No action input connected.",
            }
        }

    if mode == "simulate":
        result = _simulate_execute(data, action)
    elif mode == "unity":
        result = _unity_execute(data, action)
    elif mode == "omniverse":
        result = _omniverse_execute(data, action)
    elif mode == "ros":
        result = _ros_execute(data, action)
    else:
        result = {
            "ok": False,
            "mode": mode,
            "message": f"Unsupported robot execute mode: {mode}",
        }

    return {"result": result}
