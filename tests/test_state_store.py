from __future__ import annotations

import unittest

from backend import state_store


class StateStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        with state_store._state_lock:
            state_store._state.clear()

    def test_preferred_isaacsim_bridge_state_is_not_immediately_overwritten(self) -> None:
        first = state_store.update_state(
            "isaacsim01",
            {
                "type": "robot_state",
                "client_id": "isaacsim01",
                "source": "isaacsim_bridge",
                "bridge_build": "current",
                "position": [1.0, 0.0, 0.8],
            },
        )
        second = state_store.update_state(
            "isaacsim01",
            {
                "type": "robot_state",
                "client_id": "isaacsim01",
                "source": "isaac_g1_vlagraph_bridge",
                "position": [0.0, 0.0, 0.8],
            },
        )

        self.assertIs(second, first)
        stored = state_store.get_state("isaacsim01")
        self.assertEqual(stored["state"]["source"], "isaacsim_bridge")
        self.assertEqual(stored["state"]["position"], [1.0, 0.0, 0.8])


if __name__ == "__main__":
    unittest.main()
