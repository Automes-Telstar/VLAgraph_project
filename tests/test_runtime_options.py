from __future__ import annotations

import unittest
import sys
import types

sys.modules.setdefault(
    "websocket",
    types.SimpleNamespace(create_connection=lambda *args, **kwargs: None),
)
from backend.runtime.session_manager import _runtime_options


class RuntimeOptionsTest(unittest.TestCase):
    def test_auto_persistent_unity_graph_defaults_to_one_iteration(self) -> None:
        graph = {
            "nodes": [
                {"id": "state", "type": "unity_state", "data": {"clientId": "isaacsim01"}},
                {
                    "id": "execute",
                    "type": "robot_execute",
                    "data": {"mode": "unity", "unityStateClientId": "isaacsim01"},
                },
            ],
            "edges": [],
        }

        options = _runtime_options(graph, {})

        self.assertTrue(options["persistent"])
        self.assertEqual(options["max_iterations"], 1)

    def test_explicit_persistent_zero_iterations_is_preserved(self) -> None:
        graph = {
            "nodes": [
                {"id": "state", "type": "unity_state", "data": {"clientId": "isaacsim01"}},
                {
                    "id": "execute",
                    "type": "robot_execute",
                    "data": {"mode": "unity", "unityStateClientId": "isaacsim01"},
                },
            ],
            "edges": [],
        }

        options = _runtime_options(graph, {"persistent": True, "max_iterations": 0})

        self.assertTrue(options["persistent"])
        self.assertEqual(options["max_iterations"], 0)


if __name__ == "__main__":
    unittest.main()
