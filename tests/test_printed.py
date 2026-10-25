"""3Dプリント部品・STL書き出し・プレビュー・part コマンド。"""

import math

import pytest
from build123d import Vector

from alucad import Assembly, angle_bracket, bom, check, export_prints, frame, materials, spacer
from alucad.cli import main


def test_angle_bracket_shape_and_holes():
    a = angle_bracket("2020", arm=30, t=4)
    s = a.solid()
    bb = s.bounding_box()
    assert (round(bb.size.X, 6), round(bb.size.Y, 6), round(bb.size.Z, 6)) == (30, 20, 30)
    assert round(bb.min.Z, 6) == 0  # z=0 がベッド側
    c = 4 + (30 - 4) / 2
    assert not s.is_inside(Vector(c, 0, 2))  # 床側の穴が貫通
    assert not s.is_inside(Vector(2, 0, c))  # 壁側の穴が貫通
    assert s.is_inside(Vector(c + 5, 0, 2))


def test_angle_bracket_validation():
    with pytest.raises(ValueError):
        angle_bracket(arm=10, t=4, size="M6")  # 厚み＋穴＋余白が入らない


def test_spacer_volume():
    s = spacer(od=10, h=5, size="M3").solid()
    assert s.volume == pytest.approx(math.pi * (5**2 - 1.7**2) * 5, rel=1e-6)


@pytest.fixture
def corner():
    rail = frame("2020", 200, axis="x").at(0, 0, -10).named("rail")
    post = frame("2020", 100, axis="z").at(-10, 0, -20).named("post")
    return [rail, post, angle_bracket().named("ab1"), angle_bracket().at(100, 0, 0).named("ab2"),
            spacer().at(150, 40, 0).named("sp")]


def test_print_parts_in_bom(corner):
    b = bom(corner)
    assert [(lb, n) for lb, _, _, _, _, n in b.prints] == [("L字アングル（3Dプリント）", 2), ("スペーサー（3Dプリント）", 1)]
    # ab1: 床側→レール(Tナット)、壁側→ポスト(Tナット)。ab2: 床側→レール、壁側→相手なし(ナット)。スペーサーは数えない
    assert b.joints == {("tnut", "M5", "2020"): 3, ("nut", "M5", ""): 1}
    assert dict(b.bolts) == {("M5", 10): 4}
    assert "## 3Dプリント部品" in b.to_markdown()


def test_export_prints_groups_identical(tmp_path, corner):
    paths = export_prints(Assembly("c", corner), tmp_path)
    assert sorted(p.name for p in paths) == ["c_angle_bracket_x2.stl", "c_spacer_x1.stl"]
    assert paths[0].read_bytes()[:5] in (b"solid", b"STL E")  # STL のヘッダ


def test_export_prints_numbers_variants(tmp_path):
    parts = [spacer(h=5), spacer(h=5), spacer(h=8)]
    names = sorted(p.name for p in export_prints(parts, tmp_path, prefix="s"))
    assert names == ["s_spacer_1_x2.stl", "s_spacer_2_x1.stl"]


def test_check_print_bed(monkeypatch):
    assert check([angle_bracket(arm=100)]) == []  # プリンタ未設定ならチェックしない
    monkeypatch.setattr(materials, "PRINT_BED", (80, 80, 80))
    (issue,) = check([angle_bracket(arm=100)])
    assert issue.level == "error" and "造形サイズ" in issue.message


def test_cli_part_and_preview(tmp_path, capsys):
    png, stl = tmp_path / "a.png", tmp_path / "a.stl"
    assert main(["part", "angle_bracket", "--set", "arm=40", "--set", "size=M4", "--png", str(png), "--stl", str(stl)]) == 0
    out = capsys.readouterr().out
    assert '"arm": 40.0' in out and '"size": "M4"' in out and "40 × 20 × 40" in out
    assert png.read_bytes()[:4] == b"\x89PNG" and stl.stat().st_size > 1000

    assert main(["part", "angle_bracket", "--set", "arm=5"]) == 1
    assert "10mm 以上" in capsys.readouterr().err

    src = Assembly("c", [angle_bracket()]).save(tmp_path / "c.json")
    assert main(["preview", str(src)]) == 0
    assert (tmp_path / "out" / "c_preview.png").exists()


def test_cli_build_includes_stl(tmp_path, corner):
    src = Assembly("c", corner).save(tmp_path / "c.json")
    assert main(["build", str(src), "--only", "stl"]) == 0
    assert (tmp_path / "out" / "c_angle_bracket_x2.stl").exists()
