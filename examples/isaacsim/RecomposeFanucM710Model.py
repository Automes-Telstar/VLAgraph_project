"""
Delete and re-compose the FANUC M-710 model from the extension asset.

Use this when transform/physics experiments left the robot invisible or far
away in the current Isaac Sim stage.

Run in Isaac Sim Script Editor with the timeline stopped:

    exec(open(r"C:/Users/0/Desktop/vlagraph/examples/isaacsim/RecomposeFanucM710Model.py").read())
"""

from __future__ import annotations

import sys
from pathlib import Path


EXTENSION_ROOT = Path(
    r"C:/Users/0/Desktop/isaac_exts_omy3m_6dof_project/isaac_exts/fanuc.m710ic20l.motion"
)
PYTHON_ROOT = EXTENSION_ROOT / "python"
ASSET_PATH = EXTENSION_ROOT / "assets" / "m710ic_20l" / "m710ic_20l.usda"

FANUC_ROOT_PATH = (
    "/World/GraphicViewer/Device/LASD/Robot/HFS1/"
    "HFS1_R01_R03/HFS1_7Axis_LH/lnk3/FANUC_M710"
)
FANUC_MODEL_PATH = FANUC_ROOT_PATH + "/Robot"
FANUC_BASE_LINK_PATH = FANUC_MODEL_PATH + "/Geometry/world/base_link"


def _stage():
    import omni.usd

    return omni.usd.get_context().get_stage()


def _reset_parent_lnk3(stage) -> None:
    from pxr import Gf, UsdGeom

    lnk3_path = FANUC_ROOT_PATH.rsplit("/", 1)[0]
    prim = stage.GetPrimAtPath(lnk3_path)
    if not prim or not prim.IsValid():
        raise RuntimeError(f"lnk3 not found: {lnk3_path}")
    xform = UsdGeom.Xformable(prim)
    translate_op = None
    for op in xform.GetOrderedXformOps():
        if op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
            translate_op = op
            break
    if translate_op is None:
        translate_op = xform.AddTranslateOp()
    translate_op.Set(Gf.Vec3d(0.0, 0.0, 0.0))
    print(f"[FANUC Recompose] lnk3 translate reset: {lnk3_path}")


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


def _clear_runtime_velocities(stage, root_path: str) -> None:
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


def _print_check(stage) -> None:
    from pxr import UsdGeom

    for path in (FANUC_ROOT_PATH, FANUC_MODEL_PATH, FANUC_BASE_LINK_PATH):
        prim = stage.GetPrimAtPath(path)
        print(f"[FANUC Recompose] exists {path}: {bool(prim and prim.IsValid())}")
    base = stage.GetPrimAtPath(FANUC_BASE_LINK_PATH)
    if base and base.IsValid():
        matrix = UsdGeom.Xformable(base).ComputeLocalToWorldTransform(0)
        pos = matrix.ExtractTranslation()
        print(f"[FANUC Recompose] base_link world position: {float(pos[0])}, {float(pos[1])}, {float(pos[2])}")


def main() -> None:
    if str(PYTHON_ROOT) not in sys.path:
        sys.path.insert(0, str(PYTHON_ROOT))

    stage = _stage()
    if stage is None:
        raise RuntimeError("USD stage is not available")
    if not ASSET_PATH.exists():
        raise RuntimeError(f"FANUC asset not found: {ASSET_PATH}")

    try:
        import omni.timeline

        timeline = omni.timeline.get_timeline_interface()
        if timeline is not None and timeline.is_playing():
            timeline.stop()
            print("[FANUC Recompose] timeline stopped")
    except Exception:
        pass

    _reset_parent_lnk3(stage)

    if stage.GetPrimAtPath(FANUC_ROOT_PATH):
        stage.RemovePrim(FANUC_ROOT_PATH)
        print(f"[FANUC Recompose] removed old prim: {FANUC_ROOT_PATH}")

    stage.DefinePrim(FANUC_ROOT_PATH, "Xform")
    model = stage.DefinePrim(FANUC_MODEL_PATH, "Xform")
    model.GetReferences().ClearReferences()
    model.GetReferences().AddReference(str(ASSET_PATH))
    print(f"[FANUC Recompose] referenced asset: {ASSET_PATH}")

    _make_visible(stage, FANUC_ROOT_PATH)
    _clear_runtime_velocities(stage, FANUC_MODEL_PATH)
    _print_check(stage)
    print("[FANUC Recompose] done. Frame selected prim or reopen stage if the viewport is stale.")


main()
