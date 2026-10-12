"""
Restore the FANUC M-710 physics wiring to the stable six-axis configuration.

Run in Isaac Sim Script Editor:

    exec(open(r"C:/Users/0/Desktop/vlagraph/examples/isaacsim/RestoreFanucM710StablePhysics.py").read())
"""

from __future__ import annotations


FANUC_MODEL_PATH = (
    "/World/GraphicViewer/Device/LASD/Robot/HFS1/"
    "HFS1_R01_R03/HFS1_7Axis_LH/lnk3/FANUC_M710/Robot"
)
FANUC_BASE_LINK_PATH = FANUC_MODEL_PATH + "/Geometry/world/base_link"
FANUC_BASE_JOINT_PATH = FANUC_MODEL_PATH + "/Physics/base_joint"
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


def _stage():
    import omni.usd

    return omni.usd.get_context().get_stage()


def _set_targets(joint_prim, body0: str, body1: str) -> None:
    from pxr import Sdf

    body0_rel = joint_prim.GetRelationship("physics:body0") or joint_prim.CreateRelationship(
        "physics:body0",
        True,
    )
    body1_rel = joint_prim.GetRelationship("physics:body1") or joint_prim.CreateRelationship(
        "physics:body1",
        True,
    )
    body0_rel.ClearTargets(True)
    body1_rel.ClearTargets(True)
    body0_rel.SetTargets([Sdf.Path(body0)])
    body1_rel.SetTargets([Sdf.Path(body1)])


def _set_attr(prim, name, type_name, value) -> None:
    attr = prim.GetAttribute(name)
    if attr:
        attr.Clear()
    else:
        attr = prim.CreateAttribute(name, type_name, True)
    attr.Set(value)


def _reset_joint_frame(joint_prim) -> None:
    from pxr import Gf, Sdf

    _set_attr(joint_prim, "physics:localPos0", Sdf.ValueTypeNames.Point3f, Gf.Vec3f(0.0, 0.0, 0.0))
    _set_attr(joint_prim, "physics:localPos1", Sdf.ValueTypeNames.Point3f, Gf.Vec3f(0.0, 0.0, 0.0))
    _set_attr(joint_prim, "physics:localRot0", Sdf.ValueTypeNames.Quatf, Gf.Quatf(1.0, 0.0, 0.0, 0.0))
    _set_attr(joint_prim, "physics:localRot1", Sdf.ValueTypeNames.Quatf, Gf.Quatf(1.0, 0.0, 0.0, 0.0))


def _remove_rigid_body_apis(prim) -> None:
    try:
        from pxr import PhysxSchema, UsdPhysics
    except Exception:
        PhysxSchema = None
        UsdPhysics = None

    if UsdPhysics is not None:
        with __import__("contextlib").suppress(Exception):
            prim.RemoveAPI(UsdPhysics.RigidBodyAPI)
        with __import__("contextlib").suppress(Exception):
            prim.RemoveAPI(UsdPhysics.MassAPI)
    if PhysxSchema is not None:
        with __import__("contextlib").suppress(Exception):
            prim.RemoveAPI(PhysxSchema.PhysxRigidBodyAPI)


def _targets(prim, name: str) -> list[str]:
    rel = prim.GetRelationship(name)
    if not rel:
        return []
    return [str(path) for path in rel.GetTargets()]


def main() -> None:
    from pxr import Sdf

    stage = _stage()
    if stage is None:
        raise RuntimeError("USD stage is not available")

    print("[FANUC Restore] restoring stable six-axis base wiring")

    base_joint = stage.GetPrimAtPath(FANUC_BASE_JOINT_PATH)
    if not base_joint or not base_joint.IsValid():
        raise RuntimeError(f"base_joint not found: {FANUC_BASE_JOINT_PATH}")

    _set_targets(base_joint, FANUC_MODEL_PATH, FANUC_BASE_LINK_PATH)
    _reset_joint_frame(base_joint)

    e1_joint = stage.GetPrimAtPath(E1_JOINT_PATH)
    if e1_joint and e1_joint.IsValid():
        _set_attr(e1_joint, "physics:jointEnabled", Sdf.ValueTypeNames.Bool, False)
        print(f"[FANUC Restore] disabled experimental E1 joint: {E1_JOINT_PATH}")

    for path in (RAIL_BASE_PATH, CARRIAGE_PATH):
        prim = stage.GetPrimAtPath(path)
        if prim and prim.IsValid():
            _remove_rigid_body_apis(prim)
            print(f"[FANUC Restore] removed rigid body APIs from: {path}")

    print(f"[FANUC Restore] base_joint body0: {_targets(base_joint, 'physics:body0')}")
    print(f"[FANUC Restore] base_joint body1: {_targets(base_joint, 'physics:body1')}")
    for name in ("physics:localPos0", "physics:localRot0", "physics:localPos1", "physics:localRot1"):
        print(f"[FANUC Restore] {name}: {base_joint.GetAttribute(name).Get()}")
    print("[FANUC Restore] Stop timeline, save/reopen the stage, then Start Physics & Initialize.")


main()
