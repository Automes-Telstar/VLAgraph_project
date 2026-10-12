# -*- coding: utf-8 -*-
"""MediaPipe/RGB-D landmark retargeting helpers for the Isaac Sim Unitree G1.

This is the small, backend-side integration of the standalone
C:/mediapipe_omniverse_humanoid_ext mapping work. VLA Graph owns camera,
MediaPipe, and RGB-D processing; robotis.omy.motion owns the Isaac Sim G1
scene and articulation. The contract between them is a G1 action payload.
"""
from __future__ import annotations

import math
import os
from typing import Any, Mapping

from backend.executors.g1_action_schema import (
    G1_ACTIVE_23DOF_JOINTS,
    G1_JOINT_GROUPS,
    G1_WAIST_3DOF_JOINTS,
    g1_full_joint_order,
    g1_schema_payload,
)

Vec3 = tuple[float, float, float]


MEDIAPIPE_G1_NEUTRAL_TARGETS: dict[str, float] = {
    "torso_joint": 0.0,
    "waist_yaw_joint": 0.0,
    "waist_roll_joint": 0.0,
    "waist_pitch_joint": 0.0,
    "left_hip_pitch_joint": -0.08,
    "left_hip_roll_joint": 0.0,
    "left_hip_yaw_joint": 0.0,
    "left_knee_joint": 0.22,
    "left_ankle_pitch_joint": -0.12,
    "left_ankle_roll_joint": 0.0,
    "right_hip_pitch_joint": -0.08,
    "right_hip_roll_joint": 0.0,
    "right_hip_yaw_joint": 0.0,
    "right_knee_joint": 0.22,
    "right_ankle_pitch_joint": -0.12,
    "right_ankle_roll_joint": 0.0,
    "left_shoulder_pitch_joint": 0.0,
    "left_shoulder_roll_joint": 0.18,
    "left_shoulder_yaw_joint": 0.0,
    "left_elbow_pitch_joint": 0.35,
    "left_elbow_roll_joint": 0.0,
    "right_shoulder_pitch_joint": 0.0,
    "right_shoulder_roll_joint": -0.18,
    "right_shoulder_yaw_joint": 0.0,
    "right_elbow_pitch_joint": 0.35,
    "right_elbow_roll_joint": 0.0,
}


def landmarks_to_g1_named_targets(
    landmarks: Mapping[str, Any],
    *,
    include_neutral: bool = True,
) -> dict[str, float]:
    """Convert MediaPipe-style landmark dicts into G1 named joint targets."""
    joints = _named_humanoid_joints(landmarks)
    if not joints:
        return {}

    targets = dict(MEDIAPIPE_G1_NEUTRAL_TARGETS) if include_neutral else {}
    _apply_arm_targets(targets, joints, "left", side=1.0)
    _apply_arm_targets(targets, joints, "right", side=-1.0)
    _apply_leg_targets(targets, joints, "left", side=1.0)
    _apply_leg_targets(targets, joints, "right", side=-1.0)
    waist = _waist_rotation(joints)
    if waist is not None:
        yaw, roll, pitch = waist
        targets["waist_yaw_joint"] = yaw
        targets["waist_roll_joint"] = roll
        targets["waist_pitch_joint"] = pitch
        # Retain the legacy 23-DoF compatibility field as yaw only.
        targets["torso_joint"] = yaw
    return {name: _clamp_joint(name, value) for name, value in targets.items()}


def g1_action_payload_from_named_targets(
    targets: Mapping[str, float],
    *,
    source: str = "mediapipe_landmarks",
) -> dict[str, Any]:
    """Build a robotis.omy.motion-compatible action payload."""
    motion_joint_order = list(g1_full_joint_order())
    for joint in G1_WAIST_3DOF_JOINTS:
        if joint not in motion_joint_order:
            motion_joint_order.append(joint)
    full_targets = {
        joint: round(float(targets.get(joint, MEDIAPIPE_G1_NEUTRAL_TARGETS.get(joint, 0.0))), 6)
        for joint in motion_joint_order
    }
    joint_groups = {
        group_name: [full_targets[joint] for joint in joints]
        for group_name, joints in G1_JOINT_GROUPS.items()
    }
    return {
        "type": "gr00t_action",
        "embodiment_tag": "REAL_G1",
        "joint_schema": g1_schema_payload(),
        "joint_names": list(motion_joint_order),
        "joint_order": list(motion_joint_order),
        "joint_order_source": "g1_schema_named",
        "joint_targets": [full_targets[joint] for joint in motion_joint_order],
        "joint_positions": [full_targets[joint] for joint in motion_joint_order],
        "active_23dof_joint_order": list(G1_ACTIVE_23DOF_JOINTS),
        "active_23dof_joint_targets": [full_targets[joint] for joint in G1_ACTIVE_23DOF_JOINTS],
        "joint_target_map": dict(full_targets),
        "named_joint_targets": dict(full_targets),
        "g1_named_targets": dict(full_targets),
        "joint_groups": joint_groups,
        "retarget_source": source,
        "retarget_mode": "joint_targets",
        **joint_groups,
    }


def g1_action_payload_from_landmarks(
    landmarks: Mapping[str, Any],
    *,
    source: str = "mediapipe_landmarks",
) -> dict[str, Any]:
    targets = landmarks_to_g1_named_targets(landmarks)
    return g1_action_payload_from_named_targets(targets, source=source) if targets else {}


def _named_humanoid_joints(landmarks: Mapping[str, Any]) -> dict[str, Vec3]:
    source: dict[str, Vec3] = {}
    for raw_name, raw_value in landmarks.items():
        point = _point3(raw_value)
        if point is None:
            continue
        name = _canonical_landmark_name(raw_name)
        if name:
            source[name] = point

    joints: dict[str, Vec3] = {}
    for name in (
        "head",
        "left_shoulder",
        "right_shoulder",
        "left_elbow",
        "right_elbow",
        "left_wrist",
        "right_wrist",
        "left_hip",
        "right_hip",
        "left_knee",
        "right_knee",
        "left_ankle",
        "right_ankle",
        "left_toe",
        "right_toe",
    ):
        if name in source:
            joints[name] = source[name]

    if "left_hip" in joints and "right_hip" in joints:
        joints["pelvis"] = _midpoint(joints["left_hip"], joints["right_hip"])
    if "left_shoulder" in joints and "right_shoulder" in joints:
        joints["chest"] = _midpoint(joints["left_shoulder"], joints["right_shoulder"])
    if "pelvis" in joints and "chest" in joints:
        joints["spine"] = _midpoint(joints["pelvis"], joints["chest"])
    if "head" in joints and "chest" in joints:
        joints["neck"] = _midpoint(joints["chest"], joints["head"])
    return joints


def _canonical_landmark_name(name: Any) -> str:
    key = str(name or "").strip().lower().replace("-", "_").replace(" ", "_")
    if key.isdigit():
        return _mediapipe_index_name(int(key))
    if key.startswith("mediapipe_pose_landmark_"):
        suffix = key.rsplit("_", 1)[-1]
        if suffix.isdigit():
            return _mediapipe_index_name(int(suffix))
    if key.startswith("pose_landmark_"):
        suffix = key.rsplit("_", 1)[-1]
        if suffix.isdigit():
            return _mediapipe_index_name(int(suffix))
    aliases = {
        "nose": "head",
        "left_foot_index": "left_toe",
        "right_foot_index": "right_toe",
        "left_foot": "left_toe",
        "right_foot": "right_toe",
    }
    return aliases.get(key, key)


def _mediapipe_index_name(index: int) -> str:
    return {
        0: "head",
        11: "left_shoulder",
        12: "right_shoulder",
        13: "left_elbow",
        14: "right_elbow",
        15: "left_wrist",
        16: "right_wrist",
        23: "left_hip",
        24: "right_hip",
        25: "left_knee",
        26: "right_knee",
        27: "left_ankle",
        28: "right_ankle",
        31: "left_toe",
        32: "right_toe",
    }.get(int(index), "")


def _point3(value: Any) -> Vec3 | None:
    if isinstance(value, Mapping):
        try:
            point = (float(value["x"]), float(value["y"]), float(value["z"]))
        except Exception:
            return None
    elif isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            point = (float(value[0]), float(value[1]), float(value[2]))
        except Exception:
            return None
    else:
        return None
    return point if all(math.isfinite(item) for item in point) else None


def _apply_arm_targets(targets: dict[str, float], joints: Mapping[str, Vec3], side_name: str, *, side: float) -> None:
    shoulder = joints.get(f"{side_name}_shoulder")
    elbow = joints.get(f"{side_name}_elbow")
    wrist = joints.get(f"{side_name}_wrist")
    if shoulder is None or elbow is None:
        return
    upper = _body_vector(joints, shoulder, elbow)
    if upper is None:
        upper = _norm(_sub(elbow, shoulder))
        upper_right, upper_up, upper_forward = upper
    else:
        upper_right, upper_up, upper_forward = upper

    lateral = abs(upper_right)
    vertical = max(0.08, abs(upper_up))
    forward = upper_forward * _env_sign("RGBD_RETARGET_UPPER_FORWARD_SIGN", -1.0)
    targets[f"{side_name}_shoulder_pitch_joint"] = -0.08 - 0.80 * math.atan2(forward, vertical)
    targets[f"{side_name}_shoulder_roll_joint"] = side * (0.18 + 0.85 * math.atan2(lateral, vertical))
    targets[f"{side_name}_shoulder_yaw_joint"] = 0.35 * math.atan2(forward, max(0.10, lateral))
    if wrist is not None:
        targets[f"{side_name}_elbow_pitch_joint"] = 0.10 + 0.80 * _bend_angle(shoulder, elbow, wrist, minimum=0.0)


def _apply_leg_targets(targets: dict[str, float], joints: Mapping[str, Vec3], side_name: str, *, side: float) -> None:
    hip = joints.get(f"{side_name}_hip")
    knee = joints.get(f"{side_name}_knee")
    ankle = joints.get(f"{side_name}_ankle")
    toe = joints.get(f"{side_name}_toe")
    if hip is None or knee is None:
        return
    pelvis_axes = _pelvis_axes(joints)
    thigh = _vector_in_axes(_sub(knee, hip), pelvis_axes) if pelvis_axes is not None else None
    if thigh is None:
        thigh = _norm(_sub(knee, hip))
        thigh_right, thigh_up, thigh_forward = thigh
    else:
        thigh_right, thigh_up, thigh_forward = thigh

    targets[f"{side_name}_hip_pitch_joint"] = -0.08 + 0.42 * math.atan2(thigh_forward, max(0.08, abs(thigh_up)))
    outward_lateral = max(0.0, -side * thigh_right)
    targets[f"{side_name}_hip_roll_joint"] = side * 0.22 * math.atan2(outward_lateral, max(0.08, abs(thigh_up)))
    if ankle is not None:
        knee_bend = 0.10 + 0.70 * _bend_angle(hip, knee, ankle, minimum=0.0)
        targets[f"{side_name}_knee_joint"] = knee_bend
        targets[f"{side_name}_ankle_pitch_joint"] = -0.10 - 0.25 * knee_bend
    if ankle is not None and toe is not None and _length(_sub(toe, ankle)) > 1.0e-6:
        foot = _vector_in_axes(_sub(toe, ankle), pelvis_axes) if pelvis_axes is not None else None
        foot = foot or _norm(_sub(toe, ankle))
        targets[f"{side_name}_ankle_roll_joint"] = side * math.asin(_clamp(foot[0], -1.0, 1.0)) * 0.18


def _waist_rotation(joints: Mapping[str, Vec3]) -> tuple[float, float, float] | None:
    left_shoulder = joints.get("left_shoulder")
    right_shoulder = joints.get("right_shoulder")
    left_hip = joints.get("left_hip")
    right_hip = joints.get("right_hip")
    pelvis_axes = _pelvis_axes(joints)
    if left_shoulder is None or right_shoulder is None or left_hip is None or right_hip is None or pelvis_axes is None:
        return None
    shoulder_axis = _norm(_sub(right_shoulder, left_shoulder))
    hip_axis = _norm(_sub(right_hip, left_hip))
    right_axis, up_axis, forward_axis = pelvis_axes
    pelvis = joints.get("pelvis")
    chest = joints.get("chest")
    if pelvis is None or chest is None:
        return None
    spine = _norm(_sub(chest, pelvis))
    twist = math.atan2(_dot(_cross(hip_axis, shoulder_axis), up_axis), _dot(hip_axis, shoulder_axis))
    roll = math.atan2(_dot(spine, right_axis), max(1.0e-5, _dot(spine, up_axis)))
    pitch_sign = _env_sign("VLAGRAPH_MOTION_WAIST_PITCH_SIGN", 1.0)
    pitch = -math.atan2(_dot(spine, forward_axis), max(1.0e-5, _dot(spine, up_axis))) * pitch_sign
    return (
        _clamp(0.35 * twist, -0.25, 0.25),
        _clamp(roll, -0.35, 0.35),
        _clamp(pitch, -0.55, 0.55),
    )


def _bend_angle(a: Vec3, b: Vec3, c: Vec3, *, minimum: float = 0.0) -> float:
    ba = _norm(_sub(a, b))
    bc = _norm(_sub(c, b))
    dot = _clamp(ba[0] * bc[0] + ba[1] * bc[1] + ba[2] * bc[2], -1.0, 1.0)
    return max(minimum, math.pi - math.acos(dot))


def _clamp_joint(name: str, value: float) -> float:
    limits = {
        "torso_joint": (-0.8, 0.8),
        "waist_yaw_joint": (-0.25, 0.25),
        "waist_roll_joint": (-0.35, 0.35),
        "waist_pitch_joint": (-0.55, 0.55),
        "left_shoulder_pitch_joint": (-2.35, 1.25),
        "right_shoulder_pitch_joint": (-2.35, 1.25),
        "left_shoulder_roll_joint": (-1.55, 2.20),
        "right_shoulder_roll_joint": (-2.20, 1.55),
        "left_shoulder_yaw_joint": (-2.45, 2.45),
        "right_shoulder_yaw_joint": (-2.45, 2.45),
        "left_elbow_pitch_joint": (0.0, 1.8),
        "right_elbow_pitch_joint": (0.0, 1.8),
        "left_elbow_roll_joint": (-0.9, 0.9),
        "right_elbow_roll_joint": (-0.9, 0.9),
        "left_hip_pitch_joint": (-1.25, 1.0),
        "right_hip_pitch_joint": (-1.25, 1.0),
        "left_hip_roll_joint": (-0.9, 0.9),
        "right_hip_roll_joint": (-0.9, 0.9),
        "left_hip_yaw_joint": (-0.7, 0.7),
        "right_hip_yaw_joint": (-0.7, 0.7),
        "left_knee_joint": (0.0, 1.75),
        "right_knee_joint": (0.0, 1.75),
        "left_ankle_pitch_joint": (-1.0, 0.7),
        "right_ankle_pitch_joint": (-1.0, 0.7),
        "left_ankle_roll_joint": (-0.6, 0.6),
        "right_ankle_roll_joint": (-0.6, 0.6),
    }
    lower, upper = limits.get(name, (-1.6, 1.6))
    return _clamp(value, lower, upper)


def _midpoint(a: Vec3, b: Vec3) -> Vec3:
    return ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, (a[2] + b[2]) * 0.5)


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _body_axes(joints: Mapping[str, Vec3]) -> tuple[Vec3, Vec3, Vec3] | None:
    left_shoulder = joints.get("left_shoulder")
    right_shoulder = joints.get("right_shoulder")
    pelvis = joints.get("pelvis")
    chest = joints.get("chest")
    if left_shoulder is None or right_shoulder is None or pelvis is None or chest is None:
        return None

    right_axis = _norm(_sub(right_shoulder, left_shoulder))
    up_axis = _norm(_sub(chest, pelvis))
    if _length(right_axis) < 1.0e-6 or _length(up_axis) < 1.0e-6:
        return None

    forward_axis = _norm(_cross(right_axis, up_axis))
    if _length(forward_axis) < 1.0e-6:
        return None
    forward_sign = _env_sign("RGBD_RETARGET_FORWARD_SIGN", 1.0)
    forward_axis = (forward_axis[0] * forward_sign, forward_axis[1] * forward_sign, forward_axis[2] * forward_sign)
    up_axis = _norm(_cross(forward_axis, right_axis))
    return right_axis, up_axis, forward_axis


def _pelvis_axes(joints: Mapping[str, Vec3]) -> tuple[Vec3, Vec3, Vec3] | None:
    left_hip = joints.get("left_hip")
    right_hip = joints.get("right_hip")
    if left_hip is None or right_hip is None:
        return None
    right_axis = _norm(_sub(right_hip, left_hip))
    pelvis = joints.get("pelvis")
    chest = joints.get("chest")
    # MediaPipe Pose world landmarks are commonly Y-down even when upstream
    # metadata calls the body-centred frame Y-up. Detect the actual sign from
    # the torso instead of trusting that label.
    up_sign = -1.0 if pelvis is not None and chest is not None and chest[1] < pelvis[1] else 1.0
    world_up = (0.0, up_sign, 0.0)
    up_axis = _norm(
        (
            world_up[0] - right_axis[0] * _dot(world_up, right_axis),
            world_up[1] - right_axis[1] * _dot(world_up, right_axis),
            world_up[2] - right_axis[2] * _dot(world_up, right_axis),
        )
    )
    forward_axis = _norm(_cross(right_axis, up_axis))
    if _length(up_axis) < 1.0e-6 or _length(forward_axis) < 1.0e-6:
        return None
    forward_sign = _env_sign("RGBD_RETARGET_FORWARD_SIGN", 1.0)
    forward_axis = tuple(value * forward_sign for value in forward_axis)
    up_axis = _norm(_cross(forward_axis, right_axis))
    return right_axis, up_axis, forward_axis


def _body_vector(joints: Mapping[str, Vec3], start: Vec3, end: Vec3) -> Vec3 | None:
    axes = _body_axes(joints)
    if axes is None:
        return None
    return _vector_in_axes(_sub(end, start), axes)


def _vector_in_axes(
    value: Vec3,
    axes: tuple[Vec3, Vec3, Vec3] | None,
) -> Vec3 | None:
    if axes is None:
        return None
    vector = _norm(value)
    right_axis, up_axis, forward_axis = axes
    return (_dot(vector, right_axis), _dot(vector, up_axis), _dot(vector, forward_axis))


def _env_sign(name: str, default: float = 1.0) -> float:
    try:
        value = float(os.getenv(name, str(default)) or default)
    except ValueError:
        value = default
    return -1.0 if value < 0.0 else 1.0


def _length(value: Vec3) -> float:
    return math.sqrt(value[0] * value[0] + value[1] * value[1] + value[2] * value[2])


def _norm(value: Vec3) -> Vec3:
    length = _length(value)
    if length < 1.0e-8:
        return (0.0, 0.0, 0.0)
    return (value[0] / length, value[1] / length, value[2] / length)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(float(lower), min(float(upper), float(value)))
