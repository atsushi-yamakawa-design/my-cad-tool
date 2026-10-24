"""書き出したDXFを ezdxf で読み戻して、寸法がスケッチ通りかを確認する。"""

import ezdxf
import pytest
from ezdxf import bbox

from alucad import HOLES, export_dxf, panel

KERF = 0.2
HOLE_LIST = [[-50, -30, "M3"], [50, -30, "M4"], [-50, 30, "M5"], [50, 30, "M6"]]


def _read(path):
    doc = ezdxf.readfile(path)
    return doc, doc.modelspace()


def _layer_size(msp, layer):
    ext = bbox.extents(msp.query(f'*[layer=="{layer}"]'))
    return round(ext.size.x, 4), round(ext.size.y, 4)


def _hole_dias(msp):
    return sorted(round(c.dxf.radius * 2, 4) for c in msp.query('CIRCLE[layer=="cut"]'))


@pytest.fixture
def plate():
    return panel(120, 80, t=3, r=5, holes=HOLE_LIST)


def test_units_are_mm(tmp_path, plate):
    doc, _ = _read(export_dxf(plate, tmp_path / "a.dxf"))
    assert doc.header["$INSUNITS"] == 4  # 4 = mm


def test_no_compensation_matches_sketch(tmp_path, plate):
    _, msp = _read(export_dxf(plate, tmp_path / "a.dxf", kerf=KERF, compensate=False))
    assert _layer_size(msp, "cut") == (120, 80)
    assert _hole_dias(msp) == sorted(HOLES.values())


def test_compensation_outer_grows_holes_shrink(tmp_path, plate):
    _, msp = _read(export_dxf(plate, tmp_path / "a.dxf", kerf=KERF, compensate=True))
    assert _layer_size(msp, "cut") == (120 + KERF, 80 + KERF)
    assert _hole_dias(msp) == pytest.approx(sorted(d - KERF for d in HOLES.values()))


def test_zero_kerf_is_same_as_off(tmp_path, plate):
    _, msp = _read(export_dxf(plate, tmp_path / "a.dxf", kerf=0))
    assert _layer_size(msp, "cut") == (120, 80)


def test_hole_positions(tmp_path, plate):
    """穴の中心が、板の左下を (0,0) にした座標で設計通りの位置にある。"""
    _, msp = _read(export_dxf(plate, tmp_path / "a.dxf", kerf=KERF))
    m = KERF / 2  # 補正で外形が広がった分だけ全体が右上にずれる
    got = sorted((round(c.dxf.center.x, 4), round(c.dxf.center.y, 4)) for c in msp.query("CIRCLE"))
    want = sorted((round(x + 60 + m, 4), round(y + 40 + m, 4)) for x, y, _ in HOLE_LIST)
    assert got == want


def test_layers_and_no_kerf_on_engrave_score(tmp_path):
    p = panel(100, 60, engrave=[[0, 0, "AB", 8]], score=[[-40, -20, 40, -20]])
    path = export_dxf(p, tmp_path / "a.dxf", kerf=KERF)
    doc, msp = _read(path)
    assert {"cut", "engrave", "score"} <= {layer.dxf.name for layer in doc.layers}
    assert len(msp.query('*[layer=="engrave"]')) > 0
    assert _layer_size(msp, "score") == (80, 0)  # 罫書き線は補正されない


def test_multiple_parts_side_by_side(tmp_path):
    a = panel(100, 60)
    b = panel(80, 50)
    _, msp = _read(export_dxf([a, b], tmp_path / "a.dxf", compensate=False, gap=5))
    assert _layer_size(msp, "cut") == (100 + 5 + 80, 60)


def test_warns_when_larger_than_bed(tmp_path):
    with pytest.warns(UserWarning, match="加工エリア"):
        export_dxf(panel(600, 400), tmp_path / "a.dxf")


@pytest.mark.parametrize("compensate", [False, True])
def test_cut_contour_is_closed(tmp_path, plate, compensate):
    """切断線の端点がすべて他の線とつながっている（開いた輪郭はレーザーで切れない）。"""
    _, msp = _read(export_dxf(plate, tmp_path / "a.dxf", kerf=KERF, compensate=compensate))
    pts = []
    for e in msp.query('LINE[layer=="cut"]'):
        pts += [e.dxf.start, e.dxf.end]
    for e in msp.query('ARC[layer=="cut"]'):
        pts += [e.start_point, e.end_point]
    assert pts
    for p in pts:
        assert sum((p - q).magnitude < 1e-6 for q in pts) >= 2
