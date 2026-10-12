"""
Patch/check FANUC M-710 + HFS E1 physics wiring inside Isaac Sim.

Run in Isaac Sim Script Editor:

    exec(open(r"C:/Users/0/Desktop/vlagraph/examples/isaacsim/PatchFanucM710E1Physics.py").read())

Set APPLY_PATCH = True below to author the USD relationships.
"""

from __future__ import annotations

import os

# 기본값을 적용 모드로 둡니다. 진단만 하고 싶으면 Script Editor 실행 전에
# os.environ["FANUC_E1_APPLY_PATCH"] = "0" 로 바꾸세요.
APPLY_PATCH = os.getenv("FANUC_E1_APPLY_PATCH", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
KEEP_CARRIAGE_KINEMATIC = os.getenv(
    "FANUC_E1_KEEP_CARRIAGE_KINEMATIC",
    "0",
).strip().lower() not in {"0", "false", "no", "off"}
DISABLE_FANUC_GRAVITY = os.getenv(
    "FANUC_E1_DISABLE_FANUC_GRAVITY",
    "1",
).strip().lower() not in {"0", "false", "no", "off"}
CARRIAGE_MASS_KG = float(os.getenv("FANUC_E1_CARRIAGE_MASS_KG", "1000.0"))
CARRIAGE_INERTIA = (
    float(os.getenv("FANUC_E1_CARRIAGE_INERTIA_X", "250.0")),
    float(os.getenv("FANUC_E1_CARRIAGE_INERTIA_Y", "250.0")),
    float(os.getenv("FANUC_E1_CARRIAGE_INERTIA_Z", "250.0")),
)

RAIL_BASE_PATH = (
    "/World/GraphicViewer/Device/LASD/Robot/HFS1/"
    "HFS1_R01_R03/HFS1_7Axis_LH/lnk2"
)
CARRIAGE_PATH = (
    "/World/GraphicViewer/Device/LASD/Robot/HFS1/"
    "HFS1_R01_R03/HFS1_7Axis_LH/lnk3"
)
E1_JOINT_PATH = (
    "/World/GraphicViewer/Device/LASD/Robot/HFS1/"
    "HFS1_R01_R03/HFS1_7Axis_LH/Physics/externalAxisJoint"
)
FANUC_MODEL_PATH = (
    "/World/GraphicViewer/Device/LASD/Robot/HFS1/"
    "HFS1_R01_R03/HFS1_7Axis_LH/lnk3/FANUC_M710/Robot"
)
FANUC_BASE_LINK_PATH = FANUC_MODEL_PATH + "/Geometry/world/base_link"
FANUC_BASE_JOINT_PATH = FANUC_MODEL_PATH + "/Physics/base_joint"


def _stage():
    import omni.usd

    return omni.usd.get_context().get_stage()


def _rel_targets(prim, rel_name: str) -> list[str]:
    rel = prim.GetRelationship(rel_name)
    if not rel:
        return []
    return [str(path) for path in rel.GetTargets()]


def _set_body_relationship(joint, body0: str, body1: str) -> None:
    from pxr import Sdf

    body0_rel = joint.CreateBody0Rel()
    body1_rel = joint.CreateBody1Rel()
    body0_rel.ClearTargets(True)
    body1_rel.ClearTargets(True)
    body0_rel.SetTargets([Sdf.Path(body0)])
    body1_rel.SetTargets([Sdf.Path(body1)])


def _reset_joint_frames(joint_prim) -> None:
    from pxr import Gf, Sdf

    values = {
        "physics:localPos0": Gf.Vec3f(0.0, 0.0, 0.0),
        "physics:localPos1": Gf.Vec3f(0.0, 0.0, 0.0),
        "physics:localRot0": Gf.Quatf(1.0, 0.0, 0.0, 0.0),
        "physics:localRot1": Gf.Quatf(1.0, 0.0, 0.0, 0.0),
    }
    for attr_name, value in values.items():
        type_name = Sdf.ValueTypeNames.Point3f if "Pos" in attr_name else Sdf.ValueTypeNames.Quatf
        attr = joint_prim.GetAttribute(attr_name)
        if not attr:
            attr = joint_prim.CreateAttribute(attr_name, type_name, True)
        attr.Set(value)


def _ensure_rigid_body(stage, path: str, *, kinematic: bool) -> None:
    from pxr import UsdPhysics

    prim = stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid():
        raise RuntimeError(f"Prim not found: {path}")
    if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
        UsdPhysics.RigidBodyAPI.Apply(prim)
    body = UsdPhysics.RigidBodyAPI.Get(stage, path)
    body.CreateKinematicEnabledAttr(bool(kinematic)).Set(bool(kinematic))
    body.CreateStartsAsleepAttr(False).Set(False)
    body.CreateVelocityAttr((0.0, 0.0, 0.0)).Set((0.0, 0.0, 0.0))
    body.CreateAngularVelocityAttr((0.0, 0.0, 0.0)).Set((0.0, 0.0, 0.0))
    _set_kinematic(prim, bool(kinematic))


def _set_disable_gravity(prim, disabled: bool) -> None:
    from pxr import Sdf

    # Some Isaac/PhysX builds do not immediately surface PhysxSchema helpers
    # in Script Editor, but the authored USD attribute is what the property UI
    # reads. Author it directly as a robust fallback.
    attr = prim.GetAttribute("physxRigidBody:disableGravity")
    if not attr:
        attr = prim.CreateAttribute("physxRigidBody:disableGravity", Sdf.ValueTypeNames.Bool, True)
    attr.Set(bool(disabled))


def _set_kinematic(prim, enabled: bool) -> None:
    from pxr import Sdf

    attr = prim.GetAttribute("physics:kinematicEnabled")
    if not attr:
        attr = prim.CreateAttribute("physics:kinematicEnabled", Sdf.ValueTypeNames.Bool, True)
    attr.Set(bool(enabled))


def _set_axis_locks(prim, *, lock_yz_translation: bool, lock_rotation: bool) -> None:
    from pxr import Sdf

    axis_settings = {
        "physxRigidBody:lockedPosAxis": (False, bool(lock_yz_translation), bool(lock_yz_translation)),
        "physxRigidBody:lockedRotAxis": (bool(lock_rotation), bool(lock_rotation), bool(lock_rotation)),
    }
    for attr_name, value in axis_settings.items():
        attr = prim.GetAttribute(attr_name)
        if not attr:
            attr = prim.CreateAttribute(attr_name, Sdf.ValueTypeNames.Bool3, True)
        attr.Set(value)


def _set_mass_properties(prim, *, mass: float, inertia: tuple[float, float, float]) -> None:
    from pxr import Gf, Sdf, UsdPhysics

    if not prim.HasAPI(UsdPhysics.MassAPI):
        UsdPhysics.MassAPI.Apply(prim)

    values = {
        "physics:mass": max(0.001, float(mass)),
        "physics:diagonalInertia": Gf.Vec3f(
            max(0.001, float(inertia[0])),
            max(0.001, float(inertia[1])),
            max(0.001, float(inertia[2])),
        ),
        "physics:centerOfMass": Gf.Vec3f(0.0, 0.0, 0.0),
    }
    for attr_name, value in values.items():
        type_name = Sdf.ValueTypeNames.Float
        if attr_name != "physics:mass":
            type_name = Sdf.ValueTypeNames.Float3
        attr = prim.GetAttribute(attr_name)
        if not attr:
            attr = prim.CreateAttribute(attr_name, type_name, True)
        attr.Set(value)


def _stabilize_fanuc_rigid_bodies(stage) -> None:
    from pxr import UsdPhysics

    root = stage.GetPrimAtPath(FANUC_MODEL_PATH)
    if not root or not root.IsValid():
        raise RuntimeError(f"FANUC model not found: {FANUC_MODEL_PATH}")
    stabilized: list[str] = []
    for prim in stage.Traverse():
        path = str(prim.GetPath())
        if path != FANUC_MODEL_PATH and not path.startswith(FANUC_MODEL_PATH.rstrip("/") + "/"):
            continue
        if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
            continue
        body = UsdPhysics.RigidBodyAPI.Get(stage, path)
        body.CreateVelocityAttr((0.0, 0.0, 0.0)).Set((0.0, 0.0, 0.0))
        body.CreateAngularVelocityAttr((0.0, 0.0, 0.0)).Set((0.0, 0.0, 0.0))
        if DISABLE_FANUC_GRAVITY:
            _set_disable_gravity(prim, True)
        if path == FANUC_BASE_LINK_PATH:
            _set_kinematic(prim, False)
        stabilized.append(path)
    print(
        "[FANUC E1 Patch] stabilized FANUC rigid bodies "
        f"count={len(stabilized)} disable_gravity={DISABLE_FANUC_GRAVITY}"
    )
    for path in stabilized:
        print(f"  stabilized: {path}")


def _ensure_prismatic_joint(stage) -> None:
    from pxr import UsdPhysics

    parent = E1_JOINT_PATH.rsplit("/", 1)[0]
    stage.DefinePrim(parent, "Scope")
    joint = UsdPhysics.PrismaticJoint.Define(stage, E1_JOINT_PATH)
    _set_body_relationship(joint, RAIL_BASE_PATH, CARRIAGE_PATH)
    _reset_joint_frames(joint.GetPrim())
    joint.CreateAxisAttr("X").Set("X")
    joint.CreateLowerLimitAttr(-10_000.0).Set(-10_000.0)
    joint.CreateUpperLimitAttr(10_000.0).Set(10_000.0)
    drive = UsdPhysics.DriveAPI.Get(joint.GetPrim(), "linear")
    if not drive:
        drive = UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "linear")
    drive.CreateTypeAttr("force").Set("force")
    drive.CreateStiffnessAttr(80_000.0).Set(80_000.0)
    drive.CreateDampingAttr(4_000.0).Set(4_000.0)
    drive.CreateTargetPositionAttr(0.0).Set(0.0)
    drive.CreateTargetVelocityAttr(0.0).Set(0.0)


def _ensure_base_fixed_to_carriage(stage) -> None:
    from pxr import UsdPhysics

    parent = FANUC_BASE_JOINT_PATH.rsplit("/", 1)[0]
    stage.DefinePrim(parent, "Scope")
    joint = UsdPhysics.FixedJoint.Define(stage, FANUC_BASE_JOINT_PATH)
    _set_body_relationship(joint, CARRIAGE_PATH, FANUC_BASE_LINK_PATH)
    _reset_joint_frames(joint.GetPrim())


def _print_joint(stage, path: str) -> None:
    prim = stage.GetPrimAtPath(path)
    print("")
    print(f"JOINT {path}")
    print(f"  exists: {bool(prim and prim.IsValid())}")
    if not prim or not prim.IsValid():
        return
    print(f"  type: {prim.GetTypeName()}")
    print(f"  body0: {_rel_targets(prim, 'physics:body0')}")
    print(f"  body1: {_rel_targets(prim, 'physics:body1')}")


def _print_body(stage, path: str) -> None:
    from pxr import UsdPhysics

    prim = stage.GetPrimAtPath(path)
    print("")
    print(f"BODY {path}")
    print(f"  exists: {bool(prim and prim.IsValid())}")
    if not prim or not prim.IsValid():
        return
    print(f"  type: {prim.GetTypeName()}")
    print(f"  rigid_body: {prim.HasAPI(UsdPhysics.RigidBodyAPI)}")
    print(f"  articulation_root: {prim.HasAPI(UsdPhysics.ArticulationRootAPI)}")


def main() -> None:
    stage = _stage()
    if stage is None:
        raise RuntimeError("USD stage is not available")

    edit_layer = stage.GetEditTarget().GetLayer()
    print(f"[FANUC E1 Patch] edit layer: {edit_layer.identifier}")
    print("[FANUC E1 Patch] Current wiring")
    for path in (RAIL_BASE_PATH, CARRIAGE_PATH, FANUC_MODEL_PATH, FANUC_BASE_LINK_PATH):
        _print_body(stage, path)
    _print_joint(stage, E1_JOINT_PATH)
    _print_joint(stage, FANUC_BASE_JOINT_PATH)

    if not APPLY_PATCH:
        print("")
        print(
            "[FANUC E1 Patch] Dry run only. "
            "Set FANUC_E1_APPLY_PATCH=1 or edit APPLY_PATCH=True, then run again."
        )
        return

    _ensure_rigid_body(stage, RAIL_BASE_PATH, kinematic=True)
    _ensure_rigid_body(stage, CARRIAGE_PATH, kinematic=KEEP_CARRIAGE_KINEMATIC)
    carriage_prim = stage.GetPrimAtPath(CARRIAGE_PATH)
    if DISABLE_FANUC_GRAVITY:
        _set_disable_gravity(carriage_prim, True)
    _set_mass_properties(carriage_prim, mass=CARRIAGE_MASS_KG, inertia=CARRIAGE_INERTIA)
    _set_axis_locks(carriage_prim, lock_yz_translation=True, lock_rotation=True)
    _ensure_prismatic_joint(stage)
    _ensure_base_fixed_to_carriage(stage)
    _stabilize_fanuc_rigid_bodies(stage)

    print("")
    print("[FANUC E1 Patch] Patched wiring")
    _print_body(stage, RAIL_BASE_PATH)
    _print_body(stage, CARRIAGE_PATH)
    _print_joint(stage, E1_JOINT_PATH)
    _print_joint(stage, FANUC_BASE_JOINT_PATH)
    print("")
    print("[FANUC E1 Patch] Re-run FANUC physics initialization and check DOF names.")
    if KEEP_CARRIAGE_KINEMATIC:
        print("[FANUC E1 Patch] lnk3 is kinematic; disable this if PhysX reports static-body joints.")
    else:
        print("[FANUC E1 Patch] lnk3 is dynamic with disableGravity=true, so PhysX joints can be created.")
    if DISABLE_FANUC_GRAVITY:
        print("[FANUC E1 Patch] FANUC rigid bodies have disableGravity=true to prevent startup drop.")


main()
