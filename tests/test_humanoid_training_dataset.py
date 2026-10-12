import json

from backend.executors.motion_nodes import _root_translation_from_centers
from backend.motion.extractor import save_humanoid_training_dataset, summarize_motion


def _frame(timestamp: float, hip_x: float):
    landmarks = {
        "LEFT_HIP": {"x": hip_x, "y": 0.5, "z": 0.0},
        "RIGHT_HIP": {"x": hip_x + 0.1, "y": 0.5, "z": 0.0},
    }
    return {
        "timestamp_sec": timestamp,
        "retarget_landmarks": landmarks,
        "features": {
            "hip_center": [hip_x + 0.05, 0.5, 0.0],
            "stance_width": 0.1,
            "arm_state": {"left_arm_raised": False, "right_arm_raised": False},
        },
    }


def test_summary_is_humanoid_specific():
    summary = summarize_motion([_frame(0.0, 0.0), _frame(0.1, 0.1)], "")

    assert summary["embodiment"] == "humanoid"
    assert summary["meaning_ko"]
    assert "휴머노이드" in summary["learning_goal_ko"]


def test_training_dataset_saves_observation_action_pairs(tmp_path):
    destination = tmp_path / "motion.humanoid.jsonl"
    trace = {
        "prompt": "두 발로 앞으로 이동",
        "summary": {"primary_skill": "walk_like", "meaning_ko": [{"code": "walk_like"}]},
        "frames": [_frame(0.0, 0.0), _frame(0.1, 0.1), _frame(0.2, 0.2)],
    }

    metadata = save_humanoid_training_dataset(trace, str(destination))
    rows = [json.loads(line) for line in destination.read_text(encoding="utf-8").splitlines()]

    assert metadata["trainable"] is True
    assert metadata["samples"] == 2
    assert rows[0]["schema"] == "vlagraph.humanoid_imitation.v1"
    assert rows[0]["embodiment"] == "humanoid"
    assert rows[0]["observation"]["landmarks"]
    assert rows[0]["action"]["target_landmarks"]

def test_root_translation_can_mirror_image_x_axis():
    base = (0.0, 0.5, 0.0)
    target = (0.1, 0.5, 0.0)

    normal, normal_delta = _root_translation_from_centers(
        base,
        target,
        lateral_scale=1.0,
        vertical_scale=1.0,
        depth_scale=0.0,
        image_x_depth_scale=1.2,
        mirror_image_x=False,
        max_lateral=1.0,
        max_vertical=1.0,
        max_depth=1.0,
    )
    mirrored, mirrored_delta = _root_translation_from_centers(
        base,
        target,
        lateral_scale=1.0,
        vertical_scale=1.0,
        depth_scale=0.0,
        image_x_depth_scale=1.2,
        mirror_image_x=True,
        max_lateral=1.0,
        max_vertical=1.0,
        max_depth=1.0,
    )

    assert normal[0] == 0.12
    assert normal[1] == 0.1
    assert normal_delta["image_x_mirrored"] is False
    assert mirrored[0] == -0.12
    assert mirrored[1] == -0.1
    assert mirrored_delta["image_x_mirrored"] is True
