"""Phase 2: 材料設定・ブラケット・穴位置の自動計算・キット・STEP。"""

import ezdxf
import pytest
from build123d import import_step
from ezdxf import bbox

from alucad import (
    MATERIALS,
    Assembly,
    Part,
    corner_bracket,
    export_dxf,
    export_glb,
    export_sheets,
    export_step,
    frame,
    frame_holes,
    frame_stand,
    l_bracket,
    panel,
)


def _size(shape):
    s = shape.bounding_box().size
    return round(s.X, 4), round(s.Y, 4), round(s.Z, 4)


def _cut_size(path):
    msp = ezdxf.readfile(path).modelspace()
    s = bbox.extents(msp.query('*[layer=="cut"]')).size
    return round(s.x, 4), round(s.y, 4)


def _holes(part):
    return sorted((round(a.pos[0], 4), round(a.pos[1], 4)) for a in part.geometry.anchors if a.kind == "hole")


# ---- 材料 ----
def test_materials_loaded():
    assert {"mdf3", "acrylic3", "acrylic5"} <= set(MATERIALS)
    assert MATERIALS["acrylic5"].t == 5.0


def test_panel_thickness_from_material():
    assert _size(panel(100, 50, mat="acrylic5").solid()) == (100, 50, 5)


def test_panel_t_must_match_material():
    panel(100, 50, mat="acrylic3", t=3)  # 一致していればOK
    with pytest.raises(ValueError, match="板厚"):
        panel(100, 50, mat="acrylic3", t=5)


def test_unknown_material():
    with pytest.raises(ValueError):
        panel(100, 50, mat="wood99")


def test_dxf_uses_material_kerf(tmp_path):
    k = MATERIALS["acrylic3"].kerf
    assert _cut_size(export_dxf(panel(100, 50, mat="acrylic3"), tmp_path / "a.dxf")) == (100 + k, 50 + k)


def test_export_sheets_splits_by_material(tmp_path):
    parts = [panel(100, 50, mat="mdf3"), panel(80, 40, mat="acrylic5"), panel(60, 30, mat="mdf3")]
    paths = export_sheets(parts, tmp_path, prefix="x")
    assert sorted(p.name for p in paths) == ["x_acrylic5.dxf", "x_mdf3.dxf"]
    k = MATERIALS["mdf3"].kerf
    assert _cut_size(tmp_path / "x_mdf3.dxf") == (round(100 + k + 3 + 60 + k, 4), 50 + k)


def test_dxf_wraps_rows_at_bed_width(tmp_path):
    parts = [panel(100, 50) for _ in range(4)]  # 4枚で 415mm > 300mm → 2行
    w, h = _cut_size(export_dxf(parts, tmp_path / "a.dxf", compensate=False, gap=5))
    assert (w, h) == (100 * 2 + 5, 50 * 2 + 5)


# ---- ブラケット ----
def test_l_bracket_shape_and_holes():
    b = l_bracket("2020", arm=60, n=2, mat="acrylic5")
    assert _size(b.solid()) == (60, 60, 5)
    # 全部の穴がフレームの中心線（10mm）上
    assert _holes(b) == sorted([(10, 10), (30, 10), (50, 10), (10, 30), (10, 50)])


def test_l_bracket_3030():
    b = l_bracket("3030", arm=90, n=1)
    assert _holes(b) == sorted([(15, 15), (60, 15), (15, 60)])


def test_corner_bracket():
    c = corner_bracket("2020", arm=80)
    assert _size(c.solid()) == (80, 80, 5)
    assert _holes(c) == sorted([(10, 10), (50, 10), (10, 50)])
    with pytest.raises(ValueError):
        corner_bracket("2020", arm=50)


# ---- 穴位置の自動計算 ----
def test_frame_holes_on_rails_and_leg_ends():
    s = 20
    legs = [frame("2020", 100, axis="z").at(x, y, 0) for x in (-90, 90) for y in (-40, 40)]
    rail = frame("2020", 160, axis="x").at(-80, -40, 100 - s / 2)  # 上面が z=100
    far = frame("2020", 160, axis="x").at(-80, 40, 50)  # 板に接していない → 無視
    top = panel(200, 100).at(0, 0, 100)
    holes = frame_holes(top, legs + [rail, far], size="M4", pitch=100)
    xy = sorted((x, y) for x, y, _ in holes)
    # 脚の端面4つ ＋ 横桟の中心線上（端から20mm、間隔120 ≤ pitch）に2つ
    assert xy == sorted([(-90, -40), (-90, 40), (90, -40), (90, 40), (-60, -40), (60, -40)])
    assert all(sz == "M4" for *_, sz in holes)


def test_frame_holes_follow_rotated_panel():
    """板を回転して置いても、板のローカル座標で正しい穴になる。"""
    leg = frame("2020", 100, axis="z").at(20, 10, 0)
    top = panel(100, 60).at(0, 0, 100).rot(0, 0, 90)  # ワールド(20, 10) → 板のローカル(10, -20)
    (x, y, _), = frame_holes(top, [leg])
    assert (round(x, 4), round(y, 4)) == (10, -20)


def test_frame_holes_single_hole_when_short():
    """横桟が短く、穴の間隔 pitch より狭いときは中央に1つ。"""
    rail = frame("2020", 160, axis="x").at(-80, 0, 90)
    holes = frame_holes(panel(200, 100).at(0, 0, 100), [rail], pitch=200)
    assert [(x, y) for x, y, _ in holes] == [(0, 0)]


def test_with_params_keeps_placement():
    p = panel(100, 50).at(1, 2, 3).rot(0, 0, 90).named("a")
    q = p.with_params(r=5)
    assert (q.position, q.rotation, q.name, q.params["r"]) == (p.position, p.rotation, "a", 5)


# ---- キット ----
@pytest.fixture(scope="module")
def stand():
    return frame_stand(280, 200, 150).named("stand")


def test_kit_json_is_one_line(tmp_path, stand):
    asm = Assembly("t", [stand])
    d = asm.to_dict()
    assert len(d["parts"]) == 1 and d["parts"][0]["type"] == "frame_stand"
    assert Assembly.load(asm.save(tmp_path / "a.json")).to_dict() == d


def test_kit_expands(stand):
    names = [p.name for p in stand.expand()]
    assert len(names) == 4 + 4 + 1 + 8
    assert "stand/top" in names and "stand/plate_fl_x" in names


def test_kit_top_holes_on_frames(stand):
    top = Assembly("t", [stand])["stand/top"]
    xy = {(x, y) for x, y, _ in top.params["holes"]}
    assert {(-130, -90), (130, -90), (130, 90), (-130, 90)} <= xy  # 脚の端面
    assert (130, 0) in xy  # 右の横桟の中央


def test_kit_plates_outside_frames(stand):
    parts = stand.expand()
    frames = [p.solid() for p in parts if p.type == "frame"]
    plates = [p for p in parts if p.type == "l_bracket"]
    assert len(plates) == 8
    for p in plates:
        s = p.solid()
        assert sum((s & f).volume for f in frames) == pytest.approx(0, abs=1e-6)
        # どこかのフレームに面で接している（距離ゼロ）
        assert min(s.distance_to(f) for f in frames) == pytest.approx(0, abs=1e-6)


def test_kit_expand_matches_kit_solid(stand):
    """展開した部品の位置が、キットとして作った3Dと一致する。"""
    moved = stand.at(10, 20, 0).rot(0, 0, 30)
    total = sum(p.solid().volume for p in moved.expand())
    assert total == pytest.approx(moved.solid().volume, rel=1e-6)
    a = moved.solid().bounding_box()
    b = sum((p.solid() for p in moved.expand()[1:]), moved.expand()[0].solid()).bounding_box()
    assert (round(a.min.X, 3), round(a.max.Y, 3)) == (round(b.min.X, 3), round(b.max.Y, 3))


def test_kit_parameter_change_follows(stand):
    wide = stand.with_params(w=290)
    top = [p for p in wide.expand() if p.name.endswith("top")][0]
    assert top.params["w"] == 290
    assert (135, -90) in {(x, y) for x, y, _ in top.params["holes"]}


def test_kit_sheets(tmp_path, stand):
    paths = export_sheets(Assembly("s", [stand]), tmp_path)
    assert sorted(p.name for p in paths) == ["s_acrylic5.dxf", "s_mdf3.dxf"]
    k = MATERIALS["mdf3"].kerf
    assert _cut_size(tmp_path / "s_mdf3.dxf") == (280 + k, 200 + k)


# ---- STEP / GLB ----
def test_step_roundtrip(tmp_path, stand):
    path = export_step(Assembly("s", [stand]), tmp_path / "a.step")
    back = import_step(path)
    assert len(back.solids()) == 17
    assert _size(back) == _size(stand.solid())


def test_glb_written(tmp_path):
    path = export_glb(panel(100, 50), tmp_path / "a.glb")
    assert path.read_bytes()[:4] == b"glTF"


def test_from_dict_kit():
    p = Part.from_dict({"type": "frame_stand", "params": {"w": 300, "brackets": False}})
    assert len(p.expand()) == 9
