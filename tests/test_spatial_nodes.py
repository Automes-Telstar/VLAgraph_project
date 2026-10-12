from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.executors.spatial_nodes import (
    exec_scene_context_reset,
    exec_spatial_context_builder,
    exec_spatial_memory_save,
    exec_spatial_rag_retrieve,
    normalize_scene_scan_response,
)


def _edge(source: str, target: str, source_handle: str, target_handle: str) -> dict:
    return {
        "source": source,
        "target": target,
        "sourceHandle": source_handle,
        "targetHandle": target_handle,
    }


class SpatialNodesTest(unittest.TestCase):
    def test_memory_save_retrieve_and_context_builder(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_path = str(Path(tmpdir) / "spatial_memory.jsonl")
            scan = {
                "scene_id": "lab_room_001",
                "robot": {"position": [0.0, 0.0, 0.0]},
                "objects": [
                    {"name": "red box", "position": [2.1, 0.4, 0.7]},
                    {"name": "blue cylinder", "position": [5.0, 1.0, 0.2]},
                ],
            }
            save_result = exec_spatial_memory_save(
                {"id": "save", "data": {"memoryPath": memory_path}},
                {
                    "scan": {"scan": scan},
                    "prompt": {"text": "red box 앞으로 이동해"},
                    "result": {"result": {"ok": True}},
                },
                [
                    _edge("scan", "save", "scan", "scan"),
                    _edge("prompt", "save", "text", "prompt"),
                    _edge("result", "save", "result", "result"),
                ],
            )

            self.assertTrue(save_result["ok"])
            self.assertTrue(Path(memory_path).exists())

            retrieve_result = exec_spatial_rag_retrieve(
                {"id": "retrieve", "data": {"memoryPath": memory_path, "topK": 3}},
                {
                    "prompt": {"text": "red box 앞으로 이동해"},
                    "scene": {"scene_id": "lab_room_001"},
                },
                [
                    _edge("prompt", "retrieve", "text", "prompt"),
                    _edge("scene", "retrieve", "scene_id", "scene_id"),
                ],
            )

            self.assertEqual(len(retrieve_result["memories"]), 1)
            self.assertIn("red box", retrieve_result["memories"][0]["text"])

            context_result = exec_spatial_context_builder(
                {"id": "context", "data": {"maxLines": 3}},
                {
                    "prompt": {"text": "red box 앞으로 이동해"},
                    "retrieve": retrieve_result,
                },
                [
                    _edge("prompt", "context", "text", "prompt"),
                    _edge("retrieve", "context", "memories", "memories"),
                ],
            )

            self.assertIn("Known spatial context:", context_result["text"])
            self.assertIn("User task:", context_result["text"])
            self.assertNotIn("Approach waypoint is", context_result["text"])
            self.assertIn("stored_approach_waypoint", context_result["text"])

    def test_scene_context_reset_detects_signature_change(self) -> None:
        context: dict = {
            "scan": {"scan": {"scene_id": "scene_a", "objects": [{"name": "box", "prim_path": "/World/Box"}]}}
        }
        first = exec_scene_context_reset(
            {"id": "reset", "data": {}},
            context,
            [_edge("scan", "reset", "scan", "scan")],
        )
        context["scan"] = {
            "scan": {"scene_id": "scene_b", "objects": [{"name": "table", "prim_path": "/World/Table"}]}
        }
        second = exec_scene_context_reset(
            {"id": "reset", "data": {}},
            context,
            [_edge("scan", "reset", "scan", "scan")],
        )

        self.assertTrue(first["ok"])
        self.assertFalse(first["reset"]["scene_changed"])
        self.assertTrue(second["reset"]["scene_changed"])

    def test_normalize_scene_scan_response_accepts_flat_bridge_response(self) -> None:
        normalized = normalize_scene_scan_response(
            {
                "ok": True,
                "scene_id": "lab_room_001",
                "robot": {"prim_path": "/World/KyleRobot"},
                "objects": [{"name": "table", "prim_path": "/World/Table"}],
            }
        )

        self.assertEqual(normalized["scene_id"], "lab_room_001")
        self.assertEqual(normalized["robot"]["prim_path"], "/World/KyleRobot")
        self.assertEqual(len(normalized["objects"]), 1)
        self.assertEqual(normalized["object_count"], 1)


if __name__ == "__main__":
    unittest.main()
