"""加工前チェック。"""

from build123d import Pos, Rectangle

from alucad import Assembly, check, finger_box, frame, frame_stand, l_bracket, panel
from alucad.check import _has_thin_part
from alucad.cli import main


def _msgs(issues, level=None):
    return [i.message for i in issues if level is None or i.level == level]


def test_good_designs_have_no_issues():
    """既存のキット・部品で誤検出しない。"""
    assert check(Assembly("s", [frame_stand().named("stand")])) == []
    assert check([finger_box(120, 80, 60)]) == []
    assert check([finger_box(100, 60, 40, mat="acrylic5", lid=False)]) == []
    assert check([l_bracket("3030", arm=90)]) == []


def test_too_large_for_bed():
    (issue,) = check([panel(400, 100)])
    assert issue.level == "error" and "加工エリア" in issue.message


def test_rotated_fit_is_ok():
    assert check([panel(200, 290)]) == []  # 90°回せば 300×210 に入る


def test_hole_near_edge():
    issues = check([panel(100, 50, mat="mdf3", holes=[[45, 0, "M5"]])])  # 縁まで 5 − 2.75 = 2.25mm < 3
    assert any("縁の間が 2.25mm" in m for m in _msgs(issues, "warning"))


def test_hole_far_enough_from_edge():
    assert check([panel(100, 50, mat="acrylic3", holes=[[44, 0, "M5"]])]) == []  # 縁まで 3.25mm ≥ 板厚 3mm


def test_holes_too_close():
    issues = check([panel(100, 50, holes=[[0, 0, "M5"], [7, 0, "M5"]])])  # 7 − 5.5 = 1.5mm
    assert any("の間が 1.50mm" in m for m in _msgs(issues, "warning"))


def test_thin_part_detection():
    neck = Rectangle(100, 50) - Pos(0, 12.65) * Rectangle(10, 24.7) - Pos(0, -12.65) * Rectangle(10, 24.7)
    assert _has_thin_part(neck, 0.5)  # 幅 0.6mm のくびれ
    wide = Rectangle(100, 50) - Pos(0, 12.8) * Rectangle(10, 24.4) - Pos(0, -12.8) * Rectangle(10, 24.4)
    assert not _has_thin_part(wide, 0.5)  # 幅 1.2mm


def test_overlap_detected():
    a = panel(100, 50)
    b = panel(100, 50).at(50, 0, 1)  # 半分重なって 1mm 上 → 2mm 分めり込む
    issues = check([a, b])
    assert _msgs(issues, "error") == ["panel2 とめり込んでいます（5000.0mm³）"]


def test_touching_is_not_overlap():
    rail = frame("2020", 200, axis="x").at(-100, 0, -10)
    top = panel(200, 40)
    assert check([rail, top]) == []


def test_cli_check_and_build_stops_on_error(tmp_path, capsys):
    bad = Assembly("bad", [panel(400, 100)]).save(tmp_path / "bad.json")
    assert main(["check", str(bad)]) == 1
    assert main(["build", str(bad), "--only", "bom"]) == 1
    assert not (tmp_path / "out").exists()
    assert main(["build", str(bad), "--only", "bom", "--force"]) == 0
    assert (tmp_path / "out" / "bad_bom.md").exists()
