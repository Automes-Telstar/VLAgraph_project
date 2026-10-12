"""
Reset E1/FANUC Xform offsets after externalAxisJoint experiments.

Run in Isaac Sim Script Editor:

    exec(open(r"C:/Users/0/Desktop/vlagraph/examples/isaacsim/ResetFanucM710E1Offsets.py").read())
"""

from __future__ import annotations


PATHS = (
    "/World/GraphicViewer/Device/LASD/Robot/HFS1/HFS1_R01_R03/HFS1_7Axis_LH/lnk3",
    "/World/GraphicViewer/Device/LASD/Robot/HFS1/HFS1_R01_R03/HFS1_7Axis_LH/lnk3/FANUC_M710",
    "/World/GraphicViewer/Device/LASD/Robot/HFS1/HFS1_R01_R03/HFS1_7Axis_LH/lnk3/FANUC_M710/Robot",
)


def _stage():
    import omni.usd

    return omni.usd.get_context().get_stage()


def main() -> None:
    from pxr import Gf, UsdGeom

    stage = _stage()
    if stage is None:
        raise RuntimeError("USD stage is not available")

    for path in PATHS:
        prim = stage.GetPrimAtPath(path)
        if not prim or not prim.IsValid():
            print(f"[FANUC E1 Reset] missing: {path}")
            continue
        xform = UsdGeom.Xformable(prim)
        translate_op = None
        for op in xform.GetOrderedXformOps():
            if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
                translate_op = op
                break
        if translate_op is None:
            translate_op = xform.AddTranslateOp()
        translate_op.Set(Gf.Vec3d(0.0, 0.0, 0.0))
        print(f"[FANUC E1 Reset] translate reset: {path}")


main()
