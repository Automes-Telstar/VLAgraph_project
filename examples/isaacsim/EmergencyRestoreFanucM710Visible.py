"""
Emergency restore for FANUC M-710 visibility and transforms.

Run in Isaac Sim Script Editor with the timeline stopped:

    exec(open(r"C:/Users/0/Desktop/vlagraph/examples/isaacsim/EmergencyRestoreFanucM710Visible.py").read())
"""

from __future__ import annotations


ROOTS = (
    "/World/GraphicViewer/Device/LASD/Robot/HFS1/HFS1_R01_R03/HFS1_7Axis_LH/lnk3",
    "/World/GraphicViewer/Device/LASD/Robot/HFS1/HFS1_R01_R03/HFS1_7Axis_LH/lnk3/FANUC_M710",
    "/World/GraphicViewer/Device/LASD/Robot/HFS1/HFS1_R01_R03/HFS1_7Axis_LH/lnk3/FANUC_M710/Robot",
)
FANUC_MODEL = ROOTS[-1]
FANUC_BASE_LINK = FANUC_MODEL + "/Geometry/world/base_link"
BASE_JOINT = FANUC_MODEL + "/Physics/base_joint"


def _stage():
    import omni.usd

    return omni.usd.get_context().get_stage()


def _reset_xform(stage, path: str) -> None:
    from pxr import Gf, UsdGeom

    prim = stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid():
        print(f"[FANUC Emergency Restore] missing: {path}")
        return
    xform = UsdGeom.Xformable(prim)
    translate_op = None
    orient_op = None
    scale_op = None
    other_ops = []
    for op in xform.GetOrderedXformOps():
        op_type = op.GetOpType()
        if op_type == UsdGeom.XformOp.TypeTranslate and translate_op is None:
            translate_op = op
        elif op_type == UsdGeom.XformOp.TypeOrient and orient_op is None:
            orient_op = op
        elif op_type == UsdGeom.XformOp.TypeScale and scale_op is None:
            scale_op = op
        else:
            other_ops.append(op)
    if translate_op is None:
        translate_op = xform.AddTranslateOp()
    if orient_op is None:
        orient_op = xform.AddOrientOp()
    if scale_op is None:
        scale_op = xform.AddScaleOp()
    translate_op.Set(Gf.Vec3d(0.0, 0.0, 0.0))
    orient_op.Set(Gf.Quatf(1.0, 0.0, 0.0, 0.0))
    scale_op.Set(Gf.Vec3f(1.0, 1.0, 1.0))
    xform.SetXformOpOrder([translate_op, orient_op, scale_op, *other_ops])
    print(f"[FANUC Emergency Restore] xform reset: {path}")


def _make_visible(stage, root_path: str) -> None:
    from pxr import UsdGeom

    root = stage.GetPrimAtPath(root_path)
    if not root or not root.IsValid():
        return
    prefix = root_path.rstrip("/") + "/"
    for prim in stage.Traverse():
        path = str(prim.GetPath())
        if path == root_path or path.startswith(prefix):
            imageable = UsdGeom.Imageable(prim)
            if imageable:
                imageable.MakeVisible()


def _zero_body_velocity(stage, root_path: str) -> None:
    from pxr import UsdPhysics

    root = stage.GetPrimAtPath(root_path)
    if not root or not root.IsValid():
        return
    prefix = root_path.rstrip("/") + "/"
    for prim in stage.Traverse():
        path = str(prim.GetPath())
        if path != root_path and not path.startswith(prefix):
            continue
        if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
            continue
        body = UsdPhysics.RigidBodyAPI.Get(stage, path)
        body.CreateVelocityAttr((0.0, 0.0, 0.0)).Set((0.0, 0.0, 0.0))
        body.CreateAngularVelocityAttr((0.0, 0.0, 0.0)).Set((0.0, 0.0, 0.0))
        print(f"[FANUC Emergency Restore] velocity reset: {path}")


def main() -> None:
    stage = _stage()
    if stage is None:
        raise RuntimeError("USD stage is not available")
    for path in ROOTS:
        _reset_xform(stage, path)
    _make_visible(stage, FANUC_MODEL)
    _zero_body_velocity(stage, FANUC_MODEL)
    print("[FANUC Emergency Restore] done. Reopen the stage if the viewport is still stale.")


main()
