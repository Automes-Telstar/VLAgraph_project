# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any


G1_SCHEMA_NAME = "unitree_g1_gr00t_v1"
G1_WAIST_3DOF_JOINTS: tuple[str, ...] = (
    "waist_yaw_joint",
    "waist_roll_joint",
    "waist_pitch_joint",
)

G1_JOINT_GROUPS: dict[str, tuple[str, ...]] = {
    "waist": ("torso_joint",),
    "left_leg": (
        "left_hip_pitch_joint",
        "left_hip_roll_joint",
        "left_hip_yaw_joint",
        "left_knee_joint",
        "left_ankle_pitch_joint",
        "left_ankle_roll_joint",
    ),
    "right_leg": (
        "right_hip_pitch_joint",
        "right_hip_roll_joint",
        "right_hip_yaw_joint",
        "right_knee_joint",
        "right_ankle_pitch_joint",
        "right_ankle_roll_joint",
    ),
    "left_arm": (
        "left_shoulder_pitch_joint",
        "left_shoulder_roll_joint",
        "left_shoulder_yaw_joint",
        "left_elbow_pitch_joint",
        "left_elbow_roll_joint",
    ),
    "right_arm": (
        "right_shoulder_pitch_joint",
        "right_shoulder_roll_joint",
        "right_shoulder_yaw_joint",
        "right_elbow_pitch_joint",
        "right_elbow_roll_joint",
    ),
    "left_hand": (
        "left_zero_joint",
        "left_one_joint",
        "left_two_joint",
        "left_three_joint",
        "left_four_joint",
        "left_five_joint",
        "left_six_joint",
    ),
    "right_hand": (
        "right_zero_joint",
        "right_one_joint",
        "right_two_joint",
        "right_three_joint",
        "right_four_joint",
        "right_five_joint",
        "right_six_joint",
    ),
}

G1_GROUP_ORDER: tuple[str, ...] = (
    "waist",
    "left_leg",
    "right_leg",
    "left_arm",
    "right_arm",
    "left_hand",
    "right_hand",
)

G1_ACTIVE_23DOF_JOINTS: tuple[str, ...] = (
    "left_hip_pitch_joint",
    "left_hip_roll_joint",
    "left_hip_yaw_joint",
    "left_knee_joint",
    "left_ankle_pitch_joint",
    "left_ankle_roll_joint",
    "right_hip_pitch_joint",
    "right_hip_roll_joint",
    "right_hip_yaw_joint",
    "right_knee_joint",
    "right_ankle_pitch_joint",
    "right_ankle_roll_joint",
    "torso_joint",
    "left_shoulder_pitch_joint",
    "left_shoulder_roll_joint",
    "left_shoulder_yaw_joint",
    "left_elbow_pitch_joint",
    "left_elbow_roll_joint",
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_pitch_joint",
    "right_elbow_roll_joint",
)

G1_UNITREE_29DOF_JOINTS: tuple[str, ...] = (
    "left_hip_pitch_joint",
    "left_hip_roll_joint",
    "left_hip_yaw_joint",
    "left_knee_joint",
    "left_ankle_pitch_joint",
    "left_ankle_roll_joint",
    "right_hip_pitch_joint",
    "right_hip_roll_joint",
    "right_hip_yaw_joint",
    "right_knee_joint",
    "right_ankle_pitch_joint",
    "right_ankle_roll_joint",
    "waist_yaw_joint",
    "waist_roll_joint",
    "waist_pitch_joint",
    "left_shoulder_pitch_joint",
    "left_shoulder_roll_joint",
    "left_shoulder_yaw_joint",
    "left_elbow_joint",
    "left_wrist_roll_joint",
    "left_wrist_pitch_joint",
    "left_wrist_yaw_joint",
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
    "right_wrist_yaw_joint",
)

G1_POLICY_GROUPS: tuple[str, ...] = (
    "left_arm",
    "right_arm",
    "left_hand",
    "right_hand",
    "waist",
    "left_leg",
    "right_leg",
)

G1_NAVIGATION_KEYS: dict[str, tuple[str, ...]] = {
    "navigate_command": ("forward", "lateral", "yaw"),
    "base_height_command": ("height",),
}

G1_GROUP_ALIASES: dict[str, tuple[str, ...]] = {
    "waist": ("torso", "trunk"),
    "left_leg": ("l_leg",),
    "right_leg": ("r_leg",),
    "left_arm": ("l_arm",),
    "right_arm": ("r_arm",),
    "left_hand": ("l_hand", "left_gripper"),
    "right_hand": ("r_hand", "right_gripper"),
}

G1_JOINT_ALIASES: dict[str, tuple[str, ...]] = {
    "torso_joint": ("waist_joint", "waist_yaw_joint", "torso"),
    "waist_yaw_joint": ("torso_joint", "waist_joint", "torso"),
    "waist_roll_joint": ("torso_roll_joint", "pelvis_roll_joint"),
    "waist_pitch_joint": ("torso_pitch_joint", "pelvis_pitch_joint"),
    "left_elbow_pitch_joint": ("left_elbow_joint",),
    "right_elbow_pitch_joint": ("right_elbow_joint",),
    "left_elbow_roll_joint": ("left_wrist_roll_joint", "left_palm_joint"),
    "right_elbow_roll_joint": ("right_wrist_roll_joint", "right_palm_joint"),
}


def g1_group_dimensions() -> dict[str, int]:
    dims = {name: len(joints) for name, joints in G1_JOINT_GROUPS.items()}
    dims.update({name: len(values) for name, values in G1_NAVIGATION_KEYS.items()})
    return dims


def g1_full_joint_order() -> tuple[str, ...]:
    joints: list[str] = []
    for group_name in G1_GROUP_ORDER:
        joints.extend(G1_JOINT_GROUPS[group_name])
    return tuple(joints)


def g1_schema_payload() -> dict[str, Any]:
    return {
        "name": G1_SCHEMA_NAME,
        "groups": {name: list(joints) for name, joints in G1_JOINT_GROUPS.items()},
        "group_order": list(G1_GROUP_ORDER),
        "policy_groups": list(G1_POLICY_GROUPS),
        "navigation": {name: list(fields) for name, fields in G1_NAVIGATION_KEYS.items()},
        "group_dimensions": g1_group_dimensions(),
        "full_joint_order": list(g1_full_joint_order()),
        "active_23dof_joint_order": list(G1_ACTIVE_23DOF_JOINTS),
        "unitree_29dof_joint_order": list(G1_UNITREE_29DOF_JOINTS),
        "waist_3dof_joint_order": list(G1_WAIST_3DOF_JOINTS),
    }


def g1_canonical_group_name(name: str) -> str:
    key = str(name or "").strip()
    if key.startswith("action."):
        key = key.split(".", 1)[1]
    key = key.replace("-", "_")
    if key in G1_JOINT_GROUPS or key in G1_NAVIGATION_KEYS:
        return key
    for group_name, aliases in G1_GROUP_ALIASES.items():
        if key in aliases:
            return group_name
    return ""


def g1_action_key_aliases(name: str) -> tuple[str, ...]:
    canonical = g1_canonical_group_name(name) or str(name or "").strip()
    aliases = [canonical, f"action.{canonical}"]
    for alias in G1_GROUP_ALIASES.get(canonical, ()):
        aliases.append(alias)
        aliases.append(f"action.{alias}")
    return tuple(dict.fromkeys(alias for alias in aliases if alias))


def g1_joint_name_candidates(name: str) -> tuple[str, ...]:
    canonical = str(name or "").strip()
    candidates = [canonical]
    if canonical.endswith("_joint"):
        candidates.append(canonical[:-6])
    elif canonical:
        candidates.append(canonical + "_joint")
    for alias in G1_JOINT_ALIASES.get(canonical, ()):
        candidates.append(alias)
        if alias.endswith("_joint"):
            candidates.append(alias[:-6])
        else:
            candidates.append(alias + "_joint")
    return tuple(dict.fromkeys(candidate for candidate in candidates if candidate))


def g1_joint_order_from_payload(action: dict[str, Any], vector_length: int = 0) -> tuple[str, ...]:
    if not isinstance(action, dict):
        return ()

    for key in ("joint_names", "jointNames", "joints", "joint_order", "jointOrder"):
        value = action.get(key)
        if isinstance(value, (list, tuple)) and value:
            return tuple(str(name) for name in value)

    schema = action.get("joint_schema") or action.get("jointSchema") or action.get("schema")
    if isinstance(schema, dict):
        for key in ("joint_order", "jointOrder", "full_joint_order", "fullJointOrder"):
            value = schema.get(key)
            if isinstance(value, (list, tuple)) and value:
                return tuple(str(name) for name in value)
        for key in ("unitree_29dof_joint_order", "unitree29DofJointOrder", "active_23dof_joint_order"):
            value = schema.get(key)
            if isinstance(value, (list, tuple)) and value and (vector_length <= 0 or len(value) == vector_length):
                return tuple(str(name) for name in value)

    source = str(action.get("joint_order_source") or action.get("jointOrderSource") or "").lower()
    if vector_length == len(G1_UNITREE_29DOF_JOINTS) or "29" in source or "unitree" in source:
        return G1_UNITREE_29DOF_JOINTS
    if vector_length == len(G1_ACTIVE_23DOF_JOINTS) or "23" in source:
        return G1_ACTIVE_23DOF_JOINTS
    if vector_length == len(g1_full_joint_order()):
        return g1_full_joint_order()
    return ()


def g1_read_action_value(action: dict[str, Any], key: str) -> Any:
    if not isinstance(action, dict):
        return None

    for alias in g1_action_key_aliases(key):
        if alias in action:
            return action.get(alias)

    nested = action.get("action")
    if isinstance(nested, dict):
        for alias in g1_action_key_aliases(key):
            nested_key = alias.split(".", 1)[1] if alias.startswith("action.") else alias
            if nested_key in nested:
                return nested.get(nested_key)

    groups = action.get("joint_groups") or action.get("groups")
    if isinstance(groups, dict):
        canonical = g1_canonical_group_name(key)
        if canonical and canonical in groups:
            return groups.get(canonical)

    return None


def g1_as_float_list(value: Any) -> list[float]:
    if value is None:
        return []
    if isinstance(value, dict):
        return []
    if isinstance(value, (str, bytes)):
        return []
    if not isinstance(value, (list, tuple)):
        try:
            return [float(value)]
        except Exception:
            return []

    result: list[float] = []

    def add(item: Any) -> None:
        if isinstance(item, (list, tuple)):
            for nested in item:
                add(nested)
            return
        try:
            result.append(float(item))
        except Exception:
            result.append(0.0)

    add(value)
    return result


def g1_fit_vector(values: Any, key: str, *, fill: float = 0.0) -> list[float]:
    vector = g1_as_float_list(values)
    canonical = g1_canonical_group_name(key) or str(key or "").strip()
    expected = g1_group_dimensions().get(canonical, 0)
    if expected <= 0:
        return vector
    if len(vector) > expected:
        return vector[:expected]
    while len(vector) < expected:
        vector.append(float(fill))
    return vector


def g1_split_full_joint_values(values: Any) -> dict[str, list[float]]:
    vector = g1_as_float_list(values)
    if not vector:
        return {}
    result: dict[str, list[float]] = {}
    offset = 0
    for group_name in G1_GROUP_ORDER:
        size = len(G1_JOINT_GROUPS[group_name])
        group_values = vector[offset : offset + size]
        offset += size
        if group_values:
            result[group_name] = g1_fit_vector(group_values, group_name)
    return result


def g1_split_named_joint_values(values: Any) -> dict[str, list[float]]:
    if not isinstance(values, dict):
        return {}

    result: dict[str, list[float]] = {}
    for group_name, joints in G1_JOINT_GROUPS.items():
        group_values: list[float] = []
        found = False
        for joint_name in joints:
            value = None
            for candidate in g1_joint_name_candidates(joint_name):
                if candidate in values:
                    value = values.get(candidate)
                    found = True
                    break
            try:
                group_values.append(float(value) if value is not None else 0.0)
            except Exception:
                group_values.append(0.0)
        if found:
            result[group_name] = group_values
    return result


def g1_normalize_action_payload(action: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(action, dict):
        return action

    normalized = dict(action)
    for group_name in G1_POLICY_GROUPS:
        value = g1_read_action_value(normalized, group_name)
        if value is not None:
            normalized[group_name] = value

    for key in G1_NAVIGATION_KEYS:
        value = g1_read_action_value(normalized, key)
        if value is not None:
            normalized[key] = value

    joint_values = (
        normalized.get("joint_targets")
        or normalized.get("joint_positions")
        or normalized.get("jointPositions")
        or normalized.get("positions")
    )
    named_joint_values: dict[str, Any] = {}
    for key in (
        "joint_target_map",
        "jointTargetMap",
        "named_joint_targets",
        "namedJointTargets",
        "g1_named_targets",
        "g1NamedTargets",
    ):
        value = normalized.get(key)
        if isinstance(value, dict):
            named_joint_values.update(value)

    if isinstance(joint_values, dict):
        named_joint_values.update(joint_values)
    elif joint_values is not None:
        vector = g1_as_float_list(joint_values)
        joint_names = g1_joint_order_from_payload(normalized, len(vector))
        if joint_names and vector:
            for name, value in zip(joint_names, vector):
                named_joint_values[str(name)] = value
        else:
            for group_name, values in g1_split_full_joint_values(joint_values).items():
                normalized.setdefault(group_name, values)

    if named_joint_values:
        normalized.setdefault("joint_target_map", dict(named_joint_values))
        normalized.setdefault("named_joint_targets", dict(named_joint_values))
        for group_name, values in g1_split_named_joint_values(named_joint_values).items():
            normalized.setdefault(group_name, values)
    elif joint_values is not None and not isinstance(joint_values, dict):
        for group_name, values in g1_split_full_joint_values(joint_values).items():
            normalized.setdefault(group_name, values)

    normalized.setdefault("joint_schema", g1_schema_payload())
    normalized.setdefault("embodiment_tag", "REAL_G1")
    return normalized


def g1_looks_like_action(action: Any) -> bool:
    if not isinstance(action, dict):
        return False
    keys = set(G1_POLICY_GROUPS) | set(G1_NAVIGATION_KEYS) | {
        "joint_schema",
        "joint_targets",
        "jointTargets",
        "joint_positions",
        "jointPositions",
        "joint_groups",
        "jointGroups",
        "joint_target_map",
        "jointTargetMap",
        "named_joint_targets",
        "namedJointTargets",
        "g1_named_targets",
        "g1NamedTargets",
        "left_wrist_eef_9d",
        "right_wrist_eef_9d",
        "action.left_wrist_eef_9d",
        "action.right_wrist_eef_9d",
    }
    keys.update(f"action.{key}" for key in G1_POLICY_GROUPS)
    keys.update(f"action.{key}" for key in G1_NAVIGATION_KEYS)
    return any(key in action for key in keys)
