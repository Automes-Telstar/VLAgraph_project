from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from backend.executors.omy3m_nodes import (
    exec_omy3m_isaaclab_record,
    exec_omy3m_joint_action,
)


def _edge(source: str, target: str, source_handle: str, target_handle: str) -> dict:
    return {
        "source": source,
        "target": target,
        "sourceHandle": source_handle,
        "targetHandle": target_handle,
    }


class Omy3mNodesTest(unittest.TestCase):
    def test_joint_action_builds_six_axis_map_and_clamps(self) -> None:
        result = exec_omy3m_joint_action(
            {
                "id": "action",
                "data": {
                    "jointNames": "j1,j2,j3,j4,j5,j6",
                    "jointPositions": "0,1,2,3,4,-4",
                    "jointLimitRad": 3,
                    "gripperPosition": 0.25,
                },
            },
            {"prompt": {"text": "move the cube"}},
            [_edge("prompt", "action", "text", "prompt")],
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["action"]["joint_positions"], [0, 1, 2, 3, 3, -3])
        self.assertEqual(result["action"]["joint_target_map"]["j6"], -3)
        self.assertEqual(result["action"]["command"], "apply_joint_targets")
        self.assertEqual(result["action"]["instruction"], "move the cube")

    def test_record_writes_isaaclab_jsonl_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = exec_omy3m_isaaclab_record(
                {
                    "id": "record",
                    "data": {
                        "datasetPath": tmpdir,
                        "episodeName": "episode_test",
                        "jointNames": "j1,j2,j3,j4,j5,j6",
                        "requireImage": False,
                    },
                },
                {
                    "prompt": {"text": "pick object"},
                    "state": {"state": {"joint_positions": [0] * 6}},
                    "action": {"action": {"joint_positions": [0.1] * 6}},
                    "result": {"result": {"ok": True, "response": {"state": {"joint_positions": [0.1] * 6}}}},
                },
                [
                    _edge("prompt", "record", "text", "prompt"),
                    _edge("state", "record", "state", "state"),
                    _edge("action", "record", "action", "action"),
                    _edge("result", "record", "result", "result"),
                ],
            )

            steps_path = Path(result["dataset"]["path"])
            self.assertTrue(steps_path.exists())
            record = json.loads(steps_path.read_text(encoding="utf-8").strip())
            self.assertEqual(record["schema"], "vlagraph.isaaclab.omy3m.v1")
            self.assertEqual(record["instruction"], "pick object")
            self.assertEqual(
                record["observation"]["state_after"]["joint_positions"],
                [0.1] * 6,
            )
            self.assertEqual(record["commanded_action"]["joint_positions"], [0.1] * 6)


if __name__ == "__main__":
    unittest.main()
