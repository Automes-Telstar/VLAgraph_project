import math
import numpy as np

from backend.executors.fanuc_nodes import (
    M710_JOINT_AXES,
    M710_JOINT_LIMITS,
    M710_JOINT_ORIGINS,
    M710_TOOL_OFFSET,
    M710_ZERO_TCP_POSITION,
    _m710_fk,
    _number,
    _solve_m710_ik,
    _omy3m_fk,
    _solve_omy3m_ik,
    exec_fanuc_ls_parse,
    exec_fanuc_m710_prepare,
    exec_fanuc_omy3m_retarget,
    exec_fanuc_omy3m_isaaclab_export,
)


SAMPLE_LS = """/PROG  SAMPLE
/MN
   0:  UFRAME_NUM=1 ;
   0:  UTOOL_NUM=1 ;
   1:J P[1] 25% FINE ;
   2:L P[2] 100mm/sec CNT50 ;
/POS
P[1]{
   GP1:
   UF : 1, UT : 1,
   J1= 10.000 deg, J2= -20.000 deg, J3= 30.000 deg,
   J4= 40.000 deg, J5= 50.000 deg, J6= 60.000 deg
};
P[2]{
   GP1:
   UF : 1, UT : 1, CONFIG : 'N U T, 0, 0, 0',
   X = 100.000 mm, Y = 200.000 mm, Z = 300.000 mm,
   W = 0.000 deg, P = 90.000 deg, R = 180.000 deg
};
/END
"""


JOINT_ONLY_LS = """/PROG  JOINTONLY
/MN
   1:J P[1] 25% FINE ;
   2:J P[2] 50% CNT50 ;
   3:J P[3] 75% FINE ;
/POS
P[1]{
   GP1:
   UF : 0, UT : 1,
   J1= 0.000 deg, J2= 0.000 deg, J3= 0.000 deg,
   J4= 0.000 deg, J5= 0.000 deg, J6= 0.000 deg
};
P[2]{
   GP1:
   UF : 0, UT : 1,
   J1= 10.000 deg, J2= -20.000 deg, J3= 30.000 deg,
   J4= -40.000 deg, J5= 50.000 deg, J6= -60.000 deg
};
P[3]{
   GP1:
   UF : 0, UT : 1,
   J1= -15.000 deg, J2= 25.000 deg, J3= -35.000 deg,
   J4= 45.000 deg, J5= -55.000 deg, J6= 65.000 deg
};
/END
"""


CARTESIAN_L_LS = """/PROG  CARTL
/MN
   0:  UFRAME_NUM=4 ;
   0:  UTOOL_NUM=1 ;
   1:L P[1] 500mm/sec FINE ;
   2:L P[2] 500mm/sec CNT50 ;
/POS
P[1]{
   GP1:
   UF : 4, UT : 1, CONFIG : 'N U T, 0, 0, 0',
   X = 2050.000 mm, Y = 0.000 mm, Z = 1905.000 mm,
   W = 0.000 deg, P = 0.000 deg, R = 0.000 deg
};
P[2]{
   GP1:
   UF : 4, UT : 1, CONFIG : 'N U T, 0, 0, 0',
   X = 2000.000 mm, Y = 0.000 mm, Z = 1905.000 mm,
   W = 0.000 deg, P = 0.000 deg, R = 0.000 deg
};
/END
"""
CARTESIAN_Y_LS = """/PROG  CARTY
/MN
   1:L P[1] 500mm/sec FINE ;
   2:L P[2] 500mm/sec CNT50 ;
/POS
P[1]{
   GP1:
   UF : 1, UT : 1, CONFIG : 'N U T, 0, 0, 0',
   X = 100.000 mm, Y = 200.000 mm, Z = 300.000 mm,
   W = 0.000 deg, P = 0.000 deg, R = 0.000 deg
};
P[2]{
   GP1:
   UF : 1, UT : 1, CONFIG : 'N U T, 0, 0, 0',
   X = 100.000 mm, Y = 300.000 mm, Z = 300.000 mm,
   W = 0.000 deg, P = 0.000 deg, R = 0.000 deg
};
/END
"""

CARTESIAN_E1_LS = """/PROG  CARTE1
/MN
   1:L P[1] 500mm/sec FINE ;
   2:L P[2] 500mm/sec CNT50 ;
/POS
P[1]{
   GP1:
   UF : 1, UT : 1, CONFIG : 'N U T, 0, 0, 0',
   X = 100.000 mm, Y = 200.000 mm, Z = 300.000 mm,
   W = 0.000 deg, P = 0.000 deg, R = 0.000 deg,
   E1=  1091.395  mm
};
P[2]{
   GP1:
   UF : 1, UT : 1, CONFIG : 'N U T, 0, 0, 0',
   X = 100.000 mm, Y = 200.000 mm, Z = 300.000 mm,
   W = 0.000 deg, P = 0.000 deg, R = 0.000 deg,
   E1=  1191.395  mm
};
/END
"""

INITIAL_JOINT_LS = """/PROG  INITM710
/MN
/POS
P[1]{
   GP1:
   UF : 0, UT : 1,
   J1= 1.000 deg, J2= -2.000 deg, J3= 3.000 deg,
   J4= -4.000 deg, J5= 5.000 deg, J6= -6.000 deg,
   E1=  1000.000  mm
};
/END
"""

TOOLDATA_LS = """CONTROLLER_VERSION,V8
RRS_VERSION,v8.3_R30iB_GM_global4
ROBOT_NAME,m710ic_20l_HFS1_R01
UT,1,0,0.002,335,0,0,0,basic_nozzle
UT,6,-60.004,227.093,264.93,138.865,-88.894,131.569
UT,7,0.256,-10.737,404.126,0,0,0
UT,10,0,0.001,0,0,0,0
UF,1,1875.096,6978.495,-836.532,0.209,-0.107,-90.2,carbody_measure
UF,2,1719.513,2286.916,546.665,0.211,-0.057,-90.159,m2jx_trunk
UF,3,860.859,3333.983,453.349,0.202,-0.059,-90.163,m2jx_door
UF,4,1713.525,2306.945,558.623,0.211,-0.057,-90.159,m2jx_trunk_spray_automes_fixed
UF,5,865.788,3336.248,446.357,0.199,-0.269,-87.264,m2jx_door_spray_automes_new
UF,10,0,0,0,0,0,0
POSE,HOME,0,0,0,0,0,0
POSE,start,89.998,-38.108,16.46,0,-106.461,0.003
$PLMR_GRP[1].$WMR_ENB, FALSE
$PLMR_GRP[1].$ANGLE, 0
"""


def test_parse_fanuc_ls_preserves_external_axes(tmp_path):
    source = tmp_path / "cartesian_e1.LS"
    source.write_text(CARTESIAN_E1_LS, encoding="utf-8")
    parsed = exec_fanuc_ls_parse(
        {"id": "parse", "data": {}},
        {"upload": {"dataset": {"path": str(source)}}},
        [{"source": "upload", "sourceHandle": "dataset", "target": "parse", "targetHandle": "dataset"}],
    )

    first = parsed["program"]["positions"][0]
    assert first["kind"] == "cartesian"
    assert first["external_axes_mm"] == {"E1": 1091.395}
    assert first["external_axis_names"] == ["E1"]


def test_prepare_fanuc_m710_applies_e1_external_axis_to_cartesian_target(tmp_path, monkeypatch):
    source = tmp_path / "cartesian_e1.LS"
    source.write_text(CARTESIAN_E1_LS, encoding="utf-8")
    parsed = exec_fanuc_ls_parse(
        {"id": "parse", "data": {}},
        {"upload": {"dataset": {"path": str(source)}}},
        [{"source": "upload", "sourceHandle": "dataset", "target": "parse", "targetHandle": "dataset"}],
    )

    captured_targets = []

    def fake_solve(target_position, target_rotation, seed, **kwargs):
        captured_targets.append(np.asarray(target_position, dtype=float).tolist())
        return {
            "ok": True,
            "joint_positions": seed,
            "position_error_m": 0.0,
            "orientation_error_rad": 0.0,
            "configuration_branch_preserved": True,
            "max_joint_delta_rad": 0.0,
        }

    monkeypatch.setattr("backend.executors.fanuc_nodes._solve_m710_ik", fake_solve)
    prepared = exec_fanuc_m710_prepare(
        {
            "id": "prepare",
            "data": {
                "solveCartesianIk": True,
                "previewOnly": True,
                "enableExecution": False,
                "cartesianPositionScale": 1.0,
                "cartesianAxisSigns": "1,1,1",
                "externalAxisVectors": {"E1": [1, 0, 0]},
                "secondsPerFrame": 1,
                "timingMode": "source_speed",
            },
        },
        {"parse": parsed},
        [{"source": "parse", "sourceHandle": "program", "target": "prepare", "targetHandle": "program"}],
    )

    first_frame = prepared["action"]["joint_trajectory"][0]
    second_frame = prepared["action"]["joint_trajectory"][1]
    assert prepared["action"]["external_axis_vectors"] == {"E1": [1.0, 0.0, 0.0]}
    assert prepared["action"]["external_axis_root_motion_enabled"] is True
    assert prepared["action"]["external_axis_affects_ik"] is False
    assert first_frame["external_axes_mm"] == {"E1": 1091.395}
    assert math.isclose(first_frame["external_axis_targets_m"]["E1"], 1.091395)
    assert math.isclose(first_frame["joint_target_map"]["E1"], 1091.395)
    assert "E1" in first_frame["joint_names"]
    assert math.isclose(captured_targets[1][0] - captured_targets[0][0], 0.0)
    assert math.isclose(second_frame["root_translation"][0] - first_frame["root_translation"][0], 0.1)


def test_fanuc_m710_initial_settings_ls_seeds_ik_and_external_origin(tmp_path, monkeypatch):
    motion_source = tmp_path / "cartesian_e1.LS"
    init_source = tmp_path / "initial_joint.LS"
    motion_source.write_text(CARTESIAN_E1_LS, encoding="utf-8")
    init_source.write_text(INITIAL_JOINT_LS, encoding="utf-8")
    parsed = exec_fanuc_ls_parse(
        {"id": "parse", "data": {}},
        {"upload": {"dataset": {"path": str(motion_source)}, "initialSettings": {"path": str(init_source)}}},
        [
            {"source": "upload", "sourceHandle": "dataset", "target": "parse", "targetHandle": "dataset"},
            {"source": "upload", "sourceHandle": "initialSettings", "target": "parse", "targetHandle": "initialSettings"},
        ],
    )

    observed_seeds = []

    def fake_solve(target_position, target_rotation, seed, **kwargs):
        observed_seeds.append(np.degrees(np.asarray(seed, dtype=float)).tolist())
        return {
            "ok": True,
            "joint_positions": seed,
            "position_error_m": 0.0,
            "orientation_error_rad": 0.0,
            "configuration_branch_preserved": True,
            "max_joint_delta_rad": 0.0,
        }

    monkeypatch.setattr("backend.executors.fanuc_nodes._solve_m710_ik", fake_solve)
    prepared = exec_fanuc_m710_prepare(
        {
            "id": "prepare",
            "data": {
                "solveCartesianIk": True,
                "previewOnly": True,
                "enableExecution": False,
                "cartesianAxisSigns": "1,1,1",
                "externalAxisVectors": {"E1": [1, 0, 0]},
                "secondsPerFrame": 1,
                "timingMode": "source_speed",
            },
        },
        {"parse": parsed},
        [{"source": "parse", "sourceHandle": "program", "target": "prepare", "targetHandle": "program"}],
    )

    assert parsed["summary"]["has_initial_settings"] is True
    assert parsed["program"]["initial_settings"]["joints_deg"] == [1.0, -2.0, 3.0, -4.0, 5.0, -6.0]
    assert parsed["program"]["initial_settings"]["external_axes_mm"] == {"E1": 1000.0}
    np.testing.assert_allclose(observed_seeds[0], [1.0, -2.0, 3.0, -4.0, 5.0, -6.0], atol=1e-9)
    assert prepared["summary"]["initial_joint_seed_applied"] is True
    assert prepared["summary"]["initial_external_axes_mm"] == {"E1": 1000.0}
    assert prepared["preview"][0]["source"] == "initial_settings"
    assert prepared["preview"][1]["source"] == "initial_settings_hold"
    assert math.isclose(prepared["preview"][2]["root_translation"][0], 0.091395)
    assert prepared["preview"][0]["time_sec"] < prepared["preview"][1]["time_sec"] < prepared["preview"][2]["time_sec"]


def test_fanuc_m710_tooldata_initial_settings_seed_and_frames(tmp_path, monkeypatch):
    motion_source = tmp_path / "cartesian_l.LS"
    init_source = tmp_path / "tooldata.ls"
    motion_source.write_text(CARTESIAN_L_LS, encoding="utf-8")
    init_source.write_text(TOOLDATA_LS, encoding="utf-8")
    parsed = exec_fanuc_ls_parse(
        {"id": "parse", "data": {}},
        {"upload": {"dataset": {"path": str(motion_source)}, "initialSettings": {"path": str(init_source)}}},
        [
            {"source": "upload", "sourceHandle": "dataset", "target": "parse", "targetHandle": "dataset"},
            {"source": "upload", "sourceHandle": "initialSettings", "target": "parse", "targetHandle": "initialSettings"},
        ],
    )

    observed_seeds = []

    def fake_solve(target_position, target_rotation, seed, **kwargs):
        observed_seeds.append(np.degrees(np.asarray(seed, dtype=float)).tolist())
        return {
            "ok": True,
            "joint_positions": seed,
            "position_error_m": 0.0,
            "orientation_error_rad": 0.0,
            "configuration_branch_preserved": True,
            "max_joint_delta_rad": 0.0,
        }

    monkeypatch.setattr("backend.executors.fanuc_nodes._solve_m710_ik", fake_solve)
    prepared = exec_fanuc_m710_prepare(
        {
            "id": "prepare",
            "data": {
                "solveCartesianIk": True,
                "previewOnly": True,
                "enableExecution": False,
                "secondsPerFrame": 1,
                "timingMode": "source_speed",
                "initialPoseDurationSec": 1.5,
                "initialPoseHoldSec": 2.0,
                "initialPoseReturnSec": 2.5,
            },
        },
        {"parse": parsed},
        [{"source": "parse", "sourceHandle": "program", "target": "prepare", "targetHandle": "program"}],
    )

    initial = parsed["program"]["initial_settings"]
    assert initial["format"] == "tooldata_csv"
    assert initial["pose_name"] == "start"
    assert initial["joints_deg"] == [89.998, -38.108, 16.46, 0.0, -106.461, 0.003]
    assert initial["uframe_transforms"]["1"]["name"] == "carbody_measure"
    assert initial["utool_transforms"]["1"]["name"] == "basic_nozzle"
    np.testing.assert_allclose(observed_seeds[0], initial["joints_deg"], atol=1e-9)
    assert prepared["summary"]["initial_joint_seed_applied"] is True
    assert prepared["summary"]["initial_pose_frame_applied"] is True
    assert math.isclose(prepared["summary"]["initial_pose_duration_sec"], 1.5)
    assert math.isclose(prepared["summary"]["initial_pose_hold_sec"], 2.0)
    assert prepared["summary"]["return_to_initial_pose_on_complete"] is True
    assert math.isclose(prepared["summary"]["initial_pose_return_sec"], 2.5)
    assert prepared["preview"][0]["source"] == "initial_settings"
    assert prepared["preview"][0]["source_pose_name"] == "start"
    assert prepared["preview"][0]["joint_positions"] == initial["joints_deg"]
    assert math.isclose(prepared["preview"][0]["time_sec"], 1.5)
    assert prepared["preview"][1]["source"] == "initial_settings_hold"
    assert prepared["preview"][1]["joint_positions"] == initial["joints_deg"]
    assert math.isclose(prepared["preview"][1]["time_sec"], 3.5)
    assert prepared["preview"][2]["time_sec"] > 3.5
    assert prepared["preview"][-1]["source"] == "initial_settings_return"
    assert prepared["preview"][-1]["joint_positions"] == initial["joints_deg"]
    assert math.isclose(
        prepared["preview"][-1]["time_sec"] - prepared["preview"][-2]["time_sec"],
        2.5,
    )
    assert all(
        prepared["preview"][index]["time_sec"] < prepared["preview"][index + 1]["time_sec"]
        for index in range(len(prepared["preview"]) - 1)
    )
    assert 4 in prepared["summary"]["calibrated_uframes"]
    assert 1 in prepared["summary"]["calibrated_utools"]


def test_fanuc_m710_initial_joint_axis_signs_are_opt_in(tmp_path, monkeypatch):
    motion_source = tmp_path / "cartesian_l.LS"
    init_source = tmp_path / "tooldata.ls"
    motion_source.write_text(CARTESIAN_L_LS, encoding="utf-8")
    init_source.write_text(TOOLDATA_LS, encoding="utf-8")
    parsed = exec_fanuc_ls_parse(
        {"id": "parse", "data": {}},
        {"upload": {"dataset": {"path": str(motion_source)}, "initialSettings": {"path": str(init_source)}}},
        [
            {"source": "upload", "sourceHandle": "dataset", "target": "parse", "targetHandle": "dataset"},
            {"source": "upload", "sourceHandle": "initialSettings", "target": "parse", "targetHandle": "initialSettings"},
        ],
    )

    def fake_solve(target_position, target_rotation, seed, **kwargs):
        return {
            "ok": True,
            "joint_positions": seed,
            "position_error_m": 0.0,
            "orientation_error_rad": 0.0,
            "configuration_branch_preserved": True,
            "max_joint_delta_rad": 0.0,
        }

    monkeypatch.setattr("backend.executors.fanuc_nodes._solve_m710_ik", fake_solve)
    prepared = exec_fanuc_m710_prepare(
        {
            "id": "prepare",
            "data": {
                "solveCartesianIk": True,
                "previewOnly": True,
                "enableExecution": False,
                "timingMode": "source_speed",
                "initialJointAxisSigns": "1,-1,1,1,-1,1",
            },
        },
        {"parse": parsed},
        [{"source": "parse", "sourceHandle": "program", "target": "prepare", "targetHandle": "program"}],
    )

    assert prepared["summary"]["initial_joint_axis_signs"] == [1.0, -1.0, 1.0, 1.0, -1.0, 1.0]
    assert prepared["preview"][0]["joint_positions"] == [89.998, 38.108, 16.46, 0.0, 106.461, 0.003]


def test_fanuc_number_parser_accepts_leading_decimal_values():
    assert _number("P =      .605 deg", "P") == 0.605
    assert _number("P =     -.869 deg", "P") == -0.869
    assert _number("X =  1092.825  mm", "X") == 1092.825


def test_m710_usd_extracted_kinematics_match_zero_pose():
    np.testing.assert_allclose(
        M710_JOINT_ORIGINS,
        np.asarray(
            [
                [0.0, 0.0, 0.565],
                [0.15, 0.0, 0.0],
                [0.0, 0.0, 1.15],
                [0.0, 0.0, 0.19],
                [1.8, 0.0, 0.0],
                [0.0, 0.0, 0.0],
            ]
        ),
    )
    np.testing.assert_allclose(
        M710_JOINT_AXES,
        np.asarray(
            [
                [0.0, 0.0, 1.0],
                [0.0, 1.0, 0.0],
                [0.0, -1.0, 0.0],
                [-1.0, 0.0, 0.0],
                [0.0, -1.0, 0.0],
                [-1.0, 0.0, 0.0],
            ]
        ),
    )
    np.testing.assert_allclose(M710_TOOL_OFFSET, np.asarray([0.1, 0.0, 0.0]))
    np.testing.assert_allclose(
        np.degrees(M710_JOINT_LIMITS),
        np.asarray([[-180, 180], [-90, 135], [-80.5, 205], [-200, 200], [-140, 140], [-450, 450]]),
    )

    tcp_position, tcp_rotation = _m710_fk(np.zeros(6))
    np.testing.assert_allclose(tcp_position, M710_ZERO_TCP_POSITION, atol=1e-9)
    np.testing.assert_allclose(tcp_rotation, np.eye(3), atol=1e-9)


def test_parse_and_retarget_fanuc_ls(tmp_path):
    source = tmp_path / "sample.LS"
    source.write_text(SAMPLE_LS, encoding="utf-8")
    parsed = exec_fanuc_ls_parse(
        {"id": "parse", "data": {}},
        {"upload": {"dataset": {"path": str(source)}}},
        [{"source": "upload", "sourceHandle": "dataset", "target": "parse", "targetHandle": "dataset"}],
    )
    assert parsed["summary"] == {
        "position_count": 2,
        "motion_frame_count": 2,
        "joint_position_count": 1,
        "cartesian_position_count": 1,
        "requires_uf_ut_calibration": True,
    }
    assert parsed["program"]["frames"][0]["active_uf"] == 1
    assert parsed["program"]["frames"][0]["active_ut"] == 1
    assert parsed["program"]["positions"][1]["config"]["raw"] == "N U T, 0, 0, 0"
    assert parsed["program"]["positions"][1]["config"]["wrist"] == "T"
    assert parsed["program"]["positions"][1]["config"]["turns"] == [0, 0, 0]

    retargeted = exec_fanuc_omy3m_retarget(
        {
            "id": "retarget",
            "data": {
                "positionScale": 0.25,
                "targetOrigin": "0.35,0,0.25",
                "previewOnly": True,
            },
        },
        {"parse": parsed},
        [{"source": "parse", "sourceHandle": "program", "target": "retarget", "targetHandle": "program"}],
    )
    assert retargeted["summary"]["frame_count"] == 2
    assert retargeted["summary"]["direct_joint_frames"] == 1
    assert retargeted["summary"]["ik_frames"] == 1
    assert retargeted["action"]["preview_only"] is True
    assert math.isclose(retargeted["preview"][0]["joint_positions"][0], math.radians(10))
    assert retargeted["preview"][1]["target_position"] == [0.35, 0.0, 0.25]


def test_fanuc_omy3m_retarget_defaults_to_mirrored_y_axis(tmp_path):
    source = tmp_path / "cartesian_y.LS"
    source.write_text(CARTESIAN_Y_LS, encoding="utf-8")
    parsed = exec_fanuc_ls_parse(
        {"id": "parse", "data": {}},
        {"upload": {"dataset": {"path": str(source)}}},
        [{"source": "upload", "sourceHandle": "dataset", "target": "parse", "targetHandle": "dataset"}],
    )

    retargeted = exec_fanuc_omy3m_retarget(
        {
            "id": "retarget",
            "data": {
                "positionScale": 0.25,
                "targetOrigin": "0.35,0,0.25",
                "previewOnly": True,
                "solveIk": False,
            },
        },
        {"parse": parsed},
        [{"source": "parse", "sourceHandle": "program", "target": "retarget", "targetHandle": "program"}],
    )

    assert retargeted["action"]["target_axis_signs"] == [1.0, -1.0, 1.0]
    assert retargeted["preview"][0]["target_position"] == [0.35, 0.0, 0.25]
    assert retargeted["preview"][1]["target_position"] == [0.35, -0.025, 0.25]

    unmirrored = exec_fanuc_omy3m_retarget(
        {
            "id": "retarget",
            "data": {
                "positionScale": 0.25,
                "targetOrigin": "0.35,0,0.25",
                "targetAxisSigns": "1,1,1",
                "previewOnly": True,
                "solveIk": False,
            },
        },
        {"parse": parsed},
        [{"source": "parse", "sourceHandle": "program", "target": "retarget", "targetHandle": "program"}],
    )

    assert unmirrored["preview"][1]["target_position"] == [0.35, 0.025, 0.25]

def test_prepare_fanuc_m710_relative_cartesian_defaults_to_unmirrored_y_axis(tmp_path, monkeypatch):
    source = tmp_path / "cartesian_y.LS"
    source.write_text(CARTESIAN_Y_LS, encoding="utf-8")
    parsed = exec_fanuc_ls_parse(
        {"id": "parse", "data": {}},
        {"upload": {"dataset": {"path": str(source)}}},
        [{"source": "upload", "sourceHandle": "dataset", "target": "parse", "targetHandle": "dataset"}],
    )

    captured_targets = []

    def fake_solve(target_position, target_rotation, seed, **kwargs):
        captured_targets.append(np.asarray(target_position, dtype=float).tolist())
        return {
            "ok": True,
            "joint_positions": seed,
            "position_error_m": 0.0,
            "orientation_error_rad": 0.0,
            "configuration_branch_preserved": True,
            "max_joint_delta_rad": 0.0,
        }

    monkeypatch.setattr("backend.executors.fanuc_nodes._solve_m710_ik", fake_solve)
    prepared = exec_fanuc_m710_prepare(
        {
            "id": "prepare",
            "data": {
                "solveCartesianIk": True,
                "previewOnly": True,
                "enableExecution": False,
                "cartesianPositionScale": 1.0,
                "secondsPerFrame": 1,
                "timingMode": "source_speed",
            },
        },
        {"parse": parsed},
        [{"source": "parse", "sourceHandle": "program", "target": "prepare", "targetHandle": "program"}],
    )

    assert prepared["action"]["cartesian_axis_signs"] == [1.0, 1.0, 1.0]
    assert math.isclose(captured_targets[1][1] - captured_targets[0][1], 0.1)

    captured_targets.clear()
    exec_fanuc_m710_prepare(
        {
            "id": "prepare",
            "data": {
                "solveCartesianIk": True,
                "previewOnly": True,
                "enableExecution": False,
                "cartesianPositionScale": 1.0,
                "cartesianAxisSigns": "1,-1,1",
                "secondsPerFrame": 1,
                "timingMode": "source_speed",
            },
        },
        {"parse": parsed},
        [{"source": "parse", "sourceHandle": "program", "target": "prepare", "targetHandle": "program"}],
    )

    assert math.isclose(captured_targets[1][1] - captured_targets[0][1], -0.1)


def test_prepare_fanuc_m710_bridge_action(tmp_path):
    source = tmp_path / "sample.LS"
    source.write_text(SAMPLE_LS, encoding="utf-8")
    parsed = exec_fanuc_ls_parse(
        {"id": "parse", "data": {}},
        {"upload": {"dataset": {"path": str(source)}}},
        [{"source": "upload", "sourceHandle": "dataset", "target": "parse", "targetHandle": "dataset"}],
    )
    prepared = exec_fanuc_m710_prepare(
        {
            "id": "prepare",
            "data": {
                "secondsPerFrame": 3,
                "timingMode": "fixed_total",
                "previewOnly": False,
                "enableExecution": True,
            },
        },
        {"parse": parsed},
        [{"source": "parse", "sourceHandle": "program", "target": "prepare", "targetHandle": "program"}],
    )
    assert prepared["action"]["command"] == "apply_fanuc_trajectory"
    assert prepared["action"]["target_embodiment"] == "FANUC_M710IC_20L"
    assert prepared["action"]["preview_only"] is False
    assert prepared["summary"]["executable_joint_frames"] == 2
    assert prepared["summary"]["skipped_cartesian_frames"] == 0
    assert prepared["summary"]["ik_solved_frames"] == 1
    frame = prepared["action"]["joint_trajectory"][0]
    assert frame["time_sec"] == 2
    assert frame["joint_target_map"]["J1"] == 10
    assert frame["joint_target_map"]["J6"] == 60
    assert prepared["action"]["total_duration_sec"] == 30
    assert prepared["summary"]["seconds_per_frame"] == 15


def test_prepare_fanuc_m710_joint_replay_does_not_use_ik(tmp_path):
    source = tmp_path / "joint_only.LS"
    source.write_text(JOINT_ONLY_LS, encoding="utf-8")
    parsed = exec_fanuc_ls_parse(
        {"id": "parse", "data": {}},
        {"upload": {"dataset": {"path": str(source)}}},
        [{"source": "upload", "sourceHandle": "dataset", "target": "parse", "targetHandle": "dataset"}],
    )
    assert parsed["summary"] == {
        "position_count": 3,
        "motion_frame_count": 3,
        "joint_position_count": 3,
        "cartesian_position_count": 0,
        "requires_uf_ut_calibration": False,
    }

    prepared = exec_fanuc_m710_prepare(
        {
            "id": "prepare",
            "data": {
                "solveCartesianIk": False,
                "timingMode": "source_speed",
                "secondsPerFrame": 3,
                "previewOnly": True,
                "enableExecution": False,
            },
        },
        {"parse": parsed},
        [{"source": "parse", "sourceHandle": "program", "target": "prepare", "targetHandle": "program"}],
    )
    trajectory = prepared["action"]["joint_trajectory"]
    assert prepared["summary"]["source_frames"] == 3
    assert prepared["summary"]["executable_joint_frames"] == 3
    assert prepared["summary"]["direct_joint_frames"] == 3
    assert prepared["summary"]["ik_solved_frames"] == 0
    assert prepared["summary"]["skipped_cartesian_frames"] == 0
    assert prepared["summary"]["skipped_unresolved_frames"] == 0
    assert prepared["action"]["cartesian_mode"] == "disabled"
    assert prepared["action"]["requires_uf_ut_calibration"] is False
    assert trajectory[0]["joint_positions"] == [0, 0, 0, 0, 0, 0]
    assert trajectory[1]["joint_target_map"] == {
        "J1": 10,
        "J2": -20,
        "J3": 30,
        "J4": -40,
        "J5": 50,
        "J6": -60,
    }
    assert trajectory[1]["cnt_percent"] == 50
    assert trajectory[2]["speed"] == 75
    assert "ik_solved" not in trajectory[0]
    assert trajectory[0]["time_sec"] == 0.0
    assert trajectory[0]["time_sec"] < trajectory[1]["time_sec"] < trajectory[2]["time_sec"]


def test_prepare_fanuc_m710_direct_joint_axis_signs_are_opt_in(tmp_path):
    source = tmp_path / "joint_only.LS"
    source.write_text(JOINT_ONLY_LS, encoding="utf-8")
    parsed = exec_fanuc_ls_parse(
        {"id": "parse", "data": {}},
        {"upload": {"dataset": {"path": str(source)}}},
        [{"source": "upload", "sourceHandle": "dataset", "target": "parse", "targetHandle": "dataset"}],
    )

    prepared = exec_fanuc_m710_prepare(
        {
            "id": "prepare",
            "data": {
                "solveCartesianIk": False,
                "timingMode": "source_speed",
                "secondsPerFrame": 3,
                "previewOnly": True,
                "enableExecution": False,
                "jointAxisSigns": "1,-1,1,1,-1,1",
            },
        },
        {"parse": parsed},
        [{"source": "parse", "sourceHandle": "program", "target": "prepare", "targetHandle": "program"}],
    )

    trajectory = prepared["action"]["joint_trajectory"]
    assert prepared["summary"]["joint_axis_signs"] == [1.0, -1.0, 1.0, 1.0, -1.0, 1.0]
    assert trajectory[1]["joint_positions"] == [10, 20, 30, -40, -50, -60]
    assert trajectory[1]["joint_target_map"] == {
        "J1": 10,
        "J2": 20,
        "J3": 30,
        "J4": -40,
        "J5": -50,
        "J6": -60,
    }



def test_prepare_fanuc_m710_source_timing_can_be_scaled(tmp_path):
    source = tmp_path / "joint_only.LS"
    source.write_text(JOINT_ONLY_LS, encoding="utf-8")
    parsed = exec_fanuc_ls_parse(
        {"id": "parse", "data": {}},
        {"upload": {"dataset": {"path": str(source)}}},
        [{"source": "upload", "sourceHandle": "dataset", "target": "parse", "targetHandle": "dataset"}],
    )

    normal = exec_fanuc_m710_prepare(
        {
            "id": "prepare",
            "data": {
                "solveCartesianIk": False,
                "timingMode": "source_speed",
                "secondsPerFrame": 3,
                "trajectoryTimeScale": 1.0,
            },
        },
        {"parse": parsed},
        [{"source": "parse", "sourceHandle": "program", "target": "prepare", "targetHandle": "program"}],
    )
    faster = exec_fanuc_m710_prepare(
        {
            "id": "prepare",
            "data": {
                "solveCartesianIk": False,
                "timingMode": "source_speed",
                "secondsPerFrame": 3,
                "trajectoryTimeScale": 2.0,
            },
        },
        {"parse": parsed},
        [{"source": "parse", "sourceHandle": "program", "target": "prepare", "targetHandle": "program"}],
    )

    assert normal["action"]["joint_trajectory"][0]["time_sec"] == 0.0
    assert faster["action"]["trajectory_time_scale"] == 2.0
    assert faster["action"]["total_duration_sec"] == normal["action"]["total_duration_sec"] / 2.0


def test_prepare_fanuc_m710_cartesian_l_uses_calibrated_uf_and_source_speed(tmp_path):
    source = tmp_path / "cartesian_l.LS"
    source.write_text(CARTESIAN_L_LS, encoding="utf-8")
    parsed = exec_fanuc_ls_parse(
        {"id": "parse", "data": {}},
        {"upload": {"dataset": {"path": str(source)}}},
        [{"source": "upload", "sourceHandle": "dataset", "target": "parse", "targetHandle": "dataset"}],
    )
    assert parsed["summary"] == {
        "position_count": 2,
        "motion_frame_count": 2,
        "joint_position_count": 0,
        "cartesian_position_count": 2,
        "requires_uf_ut_calibration": True,
    }

    prepared = exec_fanuc_m710_prepare(
        {
            "id": "prepare",
            "data": {
                "timingMode": "source_speed",
                "secondsPerFrame": 3,
                "uframeTransforms": {"4": {"xyzMm": [0, 0, 0], "wprDeg": [0, 0, 0]}},
                "previewOnly": True,
            },
        },
        {"parse": parsed},
        [{"source": "parse", "sourceHandle": "program", "target": "prepare", "targetHandle": "program"}],
    )
    trajectory = prepared["action"]["joint_trajectory"]
    assert prepared["summary"]["source_frames"] == 2
    assert prepared["summary"]["executable_joint_frames"] == 2
    assert prepared["summary"]["direct_joint_frames"] == 0
    assert prepared["summary"]["ik_solved_frames"] == 2
    assert prepared["summary"]["calibrated_cartesian_frames"] == 2
    assert prepared["summary"]["relative_cartesian_frames"] == 0
    assert prepared["summary"]["skipped_cartesian_frames"] == 0
    assert prepared["action"]["calibrated_uframes"] == [4]
    assert trajectory[0]["cartesian_mode"] == "calibrated_uf_ik"
    assert trajectory[0]["active_uf"] == 4
    assert trajectory[0]["position_uf"] == 4
    assert trajectory[1]["cnt_percent"] == 50
    assert trajectory[0]["joint_positions"] == [0, 0, 0, 0, 0, 0]
    assert math.isclose(trajectory[1]["time_sec"] - trajectory[0]["time_sec"], 0.1, abs_tol=1e-4)


def test_m710_numerical_ik_recovers_reachable_pose():
    expected = np.asarray([0.15, -0.25, 0.35, 0.10, -0.20, 0.15])
    position, rotation = _m710_fk(expected)
    solved = _solve_m710_ik(position, rotation, expected + 0.01)
    assert solved["ok"] is True
    actual_position, _ = _m710_fk(np.asarray(solved["joint_positions"]))
    assert np.linalg.norm(actual_position - position) < 0.012


def test_omy3m_numerical_ik_recovers_reachable_position():
    expected = np.asarray([0.2, -0.45, 0.75, -0.25, 0.3, -0.15])
    position, _ = _omy3m_fk(expected)
    solved = _solve_omy3m_ik(
        position.tolist(),
        [0.0, 0.0, 0.0],
        expected.tolist(),
        max_iterations=20,
        position_tolerance=1e-5,
        orientation_tolerance=math.pi,
    )
    assert solved["ok"] is True
    actual_position, _ = _omy3m_fk(np.asarray(solved["joint_positions"]))
    assert np.linalg.norm(actual_position - position) < 1e-5


def test_export_isaaclab_trajectory_episode(tmp_path):
    action = {
        "joint_trajectory": [
            {"time_sec": 0.0, "joint_positions": [0, 0, 0, 0, 0, 0]},
            {
                "time_sec": 1.0,
                "joint_positions": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
                "source_position_id": 2,
                "ik_solved": True,
            },
            {
                "time_sec": 2.0,
                "joint_positions": [0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
                "source_position_id": 3,
                "ik_solved": True,
            },
        ]
    }
    exported = exec_fanuc_omy3m_isaaclab_export(
        {
            "id": "export",
            "data": {"datasetPath": str(tmp_path), "episodeName": "demo"},
        },
        {"retarget": {"action": action}, "execute": {"result": {"ok": True}}},
        [
            {"source": "retarget", "sourceHandle": "action", "target": "export", "targetHandle": "action"},
            {"source": "execute", "sourceHandle": "result", "target": "export", "targetHandle": "result"},
        ],
    )
    assert exported["ok"] is True
    assert exported["summary"]["steps"] == 2
    assert "train_isaaclab.ps1" in exported["train_command"]
    assert exported["frame_count"] == 2
    lines = (tmp_path / "demo" / "steps.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert '"measured_rollout": false' in lines[0]
