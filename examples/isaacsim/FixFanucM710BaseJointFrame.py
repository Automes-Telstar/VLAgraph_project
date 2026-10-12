"""
Force-reset the FANUC M-710 base_joint frame after changing Body0 to lnk3.

Run in Isaac Sim Script Editor:

    exec(open(r"C:/Users/0/Desktop/vlagraph/examples/isaacsim/FixFanucM710BaseJointFrame.py").read())
"""

from __future__ import annotations


BASE_JOINT_PATH = (
    "/World/GraphicViewer/Device/LASD/Robot/HFS1/"
    "HFS1_R01_R03/HFS1_7Axis_LH/lnk3/FANUC_M710/Robot/Physics/base_joint"
)
BODY0_PATH = (
    "/World/GraphicViewer/Device/LASD/Robot/HFS1/"
    "HFS1_R01_R03/HFS1_7Axis_LH/lnk3"
)
BODY1_PATH = (
    "/World/GraphicViewer/Device/LASD/Robot/HFS1/"
    "HFS1_R01_R03/HFS1_7Axis_LH/lnk3/FANUC_M710/Robot/Geometry/world/base_link"
)


def _stage():
    import omni.usd

    return omni.usd.get_context().get_stage()


def _set_attr(prim, name, type_name, value) -> None:
    attr = prim.GetAttribute(name)
    if attr:
        attr.Clear()
        attr.ClearAtTime(0)
    else:
        attr = prim.CreateAttribute(name, type_name, True)
    attr.Set(value)


def _targets(prim, name: str) -> list[str]:
    rel = prim.GetRelationship(name)
    if not rel:
        return []
    return [str(path) for path in rel.GetTargets()]


def main() -> None:
    from pxr import Gf, Sdf

    stage = _stage()
    if stage is None:
        raise RuntimeError("USD stage is not available")

    edit_layer = stage.GetEditTarget().GetLayer()
    prim = stage.GetPrimAtPath(BASE_JOINT_PATH)
    if not prim or not prim.IsValid():
        raise RuntimeError(f"base_joint not found: {BASE_JOINT_PATH}")

    body0 = prim.GetRelationship("physics:body0")
    body1 = prim.GetRelationship("physics:body1")
    if body0:
        body0.ClearTargets(True)
    else:
        body0 = prim.CreateRelationship("physics:body0", True)
    if body1:
        body1.ClearTargets(True)
    else:
        body1 = prim.CreateRelationship("physics:body1", True)
    body0.SetTargets([Sdf.Path(BODY0_PATH)])
    body1.SetTargets([Sdf.Path(BODY1_PATH)])

    _set_attr(prim, "physics:localPos0", Sdf.ValueTypeNames.Point3f, Gf.Vec3f(0.0, 0.0, 0.0))
    _set_attr(prim, "physics:localPos1", Sdf.ValueTypeNames.Point3f, Gf.Vec3f(0.0, 0.0, 0.0))
    _set_attr(prim, "physics:localRot0", Sdf.ValueTypeNames.Quatf, Gf.Quatf(1.0, 0.0, 0.0, 0.0))
    _set_attr(prim, "physics:localRot1", Sdf.ValueTypeNames.Quatf, Gf.Quatf(1.0, 0.0, 0.0, 0.0))

    print("[FANUC base_joint frame fix]")
    print(f"  edit_layer: {edit_layer.identifier}")
    print(f"  body0: {_targets(prim, 'physics:body0')}")
    print(f"  body1: {_targets(prim, 'physics:body1')}")
    for name in ("physics:localPos0", "physics:localRot0", "physics:localPos1", "physics:localRot1"):
        print(f"  {name}: {prim.GetAttribute(name).Get()}")
    print("  If the Property panel still shows old values, deselect/reselect base_joint or reopen the stage.")


main()
