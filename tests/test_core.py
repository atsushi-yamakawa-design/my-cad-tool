"""コンポーネント・配置・JSON往復のテスト。"""

import math

import numpy as np
import pytest
from build123d import Rectangle, Circle, ExportDXF

from alucad import Assembly, Part, Profile, PROFILES, catalog, frame, hole_grid, panel
from alucad import registry
from alucad.registry import REGISTRY


def _size(shape):
    s = shape.bounding_box().size
    return round(s.X, 6), round(s.Y, 6), round(s.Z, 6)


# ---- フレーム ----
@pytest.mark.parametrize(
    "axis, want", [("x", (400, 20, 20)), ("y", (20, 400, 20)), ("z", (20, 20, 400))]
)
def test_frame_axis(axis, want):
    assert _size(frame("2020", 400, axis=axis).solid()) == want


def test_frame_starts_at_origin_and_extends_plus():
    bb = frame("3030", 100, axis="x").at(10, 0, 0).solid().bounding_box()
    assert (round(bb.min.X, 6), round(bb.max.X, 6)) == (10, 110)
    assert round(bb.min.Y, 6) == -15


def test_frame_anchors():
    a = {x.name: x for x in frame("2020", 100, axis="z").at(5, 0, 0).anchors()}
    assert a["end0"].pos == (5, 0, 0) and a["end0"].normal == (0, 0, -1)
    assert a["end1"].pos == (5, 0, 100)
    assert a["side+x"].pos == (15, 0, 50) and a["side+x"].normal == (1, 0, 0)


def test_profile_can_be_swapped_with_dxf(tmp_path, monkeypatch):
    """断面を実断面DXFに差し替えられる（ここでは中心穴つきの正方形で代用）。"""
    path = tmp_path / "2020.dxf"
    ExportDXF().add_shape(Rectangle(20, 20) - Circle(2.1)).write(path)
    monkeypatch.setitem(PROFILES, "2020", Profile("2020", 20, slot=6, dxf=str(path)))
    monkeypatch.setattr(registry, "_cache", {})
    s = frame("2020", 10, axis="z").solid()
    assert s.volume == pytest.approx((400 - math.pi * 2.1**2) * 10, rel=1e-6)


# ---- 板 ----
def test_panel_solid_is_extruded_sketch():
    p = panel(300, 200, t=3)
    assert _size(p.solid()) == (300, 200, 3)


def test_panel_rejects_hole_outside():
    with pytest.raises(ValueError, match="はみ出し"):
        panel(100, 100, holes=[[49, 0, "M5"]])


def test_panel_param_validation():
    with pytest.raises(ValueError):
        panel(-10, 100)
    with pytest.raises(KeyError):
        panel(100, 100, holes=[[0, 0, "M8"]])


def test_hole_grid():
    assert hole_grid(100, 60, "M4", inset=10) == [
        [-40, -20, "M4"], [40, -20, "M4"], [-40, 20, "M4"], [40, 20, "M4"]
    ]


# ---- 回転：three.js の Euler 'XYZ'（R = Rx·Ry·Rz）と同じ定義であること ----
def _rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def test_rotation_matches_threejs_xyz():
    rx, ry, rz = 30, 45, 60
    want = _rx(math.radians(rx)) @ _ry(math.radians(ry)) @ _rz(math.radians(rz))
    loc = panel(10, 10).rot(rx, ry, rz).location
    t = loc.wrapped.Transformation()
    got = np.array([[t.Value(i, j) for j in (1, 2, 3)] for i in (1, 2, 3)])
    assert np.allclose(got, want)


# ---- JSON ----
def test_json_roundtrip(tmp_path):
    asm = Assembly("test")
    asm.add(frame("2020", 280).at(-140, 90, 140), name="rail")
    asm.add(panel(280, 200, r=3, holes=[[0, 0, "M5"]]).at(0, 0, 150).rot(0, 0, 90))
    path = asm.save(tmp_path / "a.json")
    back = Assembly.load(path)
    assert back.to_dict() == asm.to_dict()
    assert [p.name for p in back] == ["rail", "panel1"]
    assert _size(back["panel1"].solid()) == _size(asm["panel1"].solid())


def test_from_dict_validates():
    with pytest.raises(TypeError, match="不明な引数"):
        Part.from_dict({"type": "panel", "params": {"w": 10, "h": 10, "color": "red"}})


# ---- レジストリ（GUI用メタデータ） ----
def test_catalog_has_metadata():
    cat = {c["name"]: c for c in catalog()}
    assert {"frame", "panel"} <= set(cat)
    w = next(p for p in cat["panel"]["params"] if p["name"] == "w")
    assert w["unit"] == "mm" and w["type"] == "float" and w["min"] == 1


def test_registry_defaults_build():
    """全コンポーネントがデフォルト値だけで形状を作れる。"""
    from alucad import make

    for name in REGISTRY:
        assert make(name).solid().volume > 0
