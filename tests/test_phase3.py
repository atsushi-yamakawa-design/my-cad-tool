"""Phase 3: フィンガージョイントとネスティング。"""

import ezdxf
import pytest
from ezdxf import bbox

from alucad import BED, MATERIALS, Assembly, box_face, catalog, export_dxf, export_sheets, finger_box, panel
from alucad.joint import segments
from alucad.nest import shelf_pack

T = MATERIALS["mdf3"].t


def _solids(kit):
    return [p.solid() for p in kit.expand()]


def _union(solids):
    u = solids[0]
    for s in solids[1:]:
        u = u + s
    return u


# ---- フィンガージョイント ----
def test_segments_are_odd_and_at_least_3():
    assert [segments(L, 10) for L in (10, 40, 60, 80, 120)] == [3, 5, 7, 9, 13]
    assert all(segments(L, 7) % 2 == 1 for L in range(20, 300, 7))


@pytest.mark.parametrize("lid", [True, False])
def test_box_has_no_gaps_or_overlaps(lid):
    """全部の板の体積の合計 ＝ 合体させた体積 ＝ 外寸の箱から内側の空洞を引いた体積。"""
    w, d, h = 120, 80, 60
    solids = _solids(finger_box(w, d, h, mat="mdf3", lid=lid))
    assert len(solids) == (6 if lid else 5)
    inner_h = h - 2 * T if lid else h - T
    shell = w * d * h - (w - 2 * T) * (d - 2 * T) * inner_h
    total = sum(s.volume for s in solids)
    assert total == pytest.approx(shell, rel=1e-9)
    assert _union(solids).volume == pytest.approx(shell, rel=1e-9)


def test_box_outer_size():
    s = _union(_solids(finger_box(150, 100, 70, mat="acrylic5", finger=12))).bounding_box().size
    assert (round(s.X, 6), round(s.Y, 6), round(s.Z, 6)) == (150, 100, 70)


def test_box_odd_dimensions_still_fit():
    """凹凸の幅で割り切れない寸法でも、すき間・重なりなし。"""
    w, d, h, t = 133.3, 77.7, 51.1, MATERIALS["acrylic3"].t
    solids = _solids(finger_box(w, d, h, mat="acrylic3", finger=9))
    shell = w * d * h - (w - 2 * t) * (d - 2 * t) * (h - 2 * t)
    assert sum(s.volume for s in solids) == pytest.approx(shell, rel=1e-9)
    assert _union(solids).volume == pytest.approx(shell, rel=1e-9)


def test_fit_removes_expected_material():
    """fit を付けると、凹の両側が fit/4 ずつ広がる（凸と凹のすき間の合計が fit）。"""
    fit = 0.2
    for edges in ("A---", "B---"):
        a0 = box_face(40, 30, edges=edges, finger=8).sketch()["cut"].area
        a1 = box_face(40, 30, edges=edges, finger=8, fit=fit).sketch()["cut"].area
        # 40mm / finger 8 → 5分割。A: 内側の凹2つ×両側、B: 端の凹2つ×内側＋真ん中の凹×両側 → どちらも4辺
        assert a0 - a1 == pytest.approx(4 * fit / 4 * T)


def test_edges_validation():
    with pytest.raises(ValueError, match="edges"):
        box_face(40, 30, edges="AAX-")
    with pytest.raises(ValueError, match="edges"):
        box_face(40, 30, edges="AAA")


def test_box_face_dxf_with_kerf(tmp_path):
    k = MATERIALS["mdf3"].kerf
    path = export_dxf(box_face(120, 80, edges="AAAA"), tmp_path / "a.dxf")
    s = bbox.extents(ezdxf.readfile(path).modelspace()).size
    assert (round(s.x, 4), round(s.y, 4)) == (120 + k, 80 + k)


def test_finger_box_json_and_catalog(tmp_path):
    asm = Assembly("b", [finger_box(100, 80, 50, fit=0.1, lid=False).named("box")])
    back = Assembly.load(asm.save(tmp_path / "b.json"))
    assert back.to_dict() == asm.to_dict()
    assert len(back.expanded()) == 5
    names = {c["name"] for c in catalog()}
    assert {"box_face", "finger_box"} <= names


# ---- ネスティング ----
def _overlap(a, b):
    (ax, ay, aw, ah), (bx, by, bw, bh) = a, b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def _rects(sizes, slots):
    out = []
    for (w, h), s in zip(sizes, slots):
        if s.rotated:
            w, h = h, w
        out.append((s.sheet, s.x, s.y, w, h))
    return out


def test_shelf_pack_within_sheet_and_no_overlap():
    sizes = [(120, 80), (120, 80), (120, 60), (120, 60), (80, 60), (80, 60), (50, 50), (100, 30)]
    slots = shelf_pack(sizes, 300, 210, gap=3)
    rects = _rects(sizes, slots)
    for sheet, x, y, w, h in rects:
        assert x >= 0 and y >= 0 and x + w <= 300 and y + h <= 210
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            if a[0] == b[0]:
                assert not _overlap(a[1:], b[1:])


def test_shelf_pack_new_sheet_when_full():
    slots = shelf_pack([(140, 100)] * 6, 300, 210, gap=5)  # 1枚に 2×2=4個
    assert [s.sheet for s in slots].count(0) == 4
    assert max(s.sheet for s in slots) == 1


def test_shelf_pack_rotates_to_fit():
    (s,) = shelf_pack([(50, 250)], 300, 210)  # 縦長のままでは高さ210に入らない
    assert s.rotated and not s.oversize


def test_shelf_pack_oversize_gets_own_sheet():
    slots = shelf_pack([(50, 50), (600, 400), (50, 50)], 300, 210)
    big = slots[1]
    assert big.oversize
    assert big.sheet not in {slots[0].sheet, slots[2].sheet}


def test_export_sheets_splits_into_multiple_files(tmp_path):
    parts = [panel(140, 100, mat="acrylic3") for _ in range(6)]
    with _no_warning():
        paths = export_sheets(parts, tmp_path, prefix="n")
    assert [p.name for p in paths] == ["n_acrylic3_1.dxf", "n_acrylic3_2.dxf"]
    counts = []
    for p in paths:
        msp = ezdxf.readfile(p).modelspace()
        s = bbox.extents(msp).size
        assert s.x <= BED[0] and s.y <= BED[1]
        counts.append(len(msp.query("LINE")) // 4)
    assert counts == [4, 2]


def test_export_sheets_box_fits_one_sheet(tmp_path):
    paths = export_sheets(Assembly("b", [finger_box(120, 80, 60)]), tmp_path, gap=3)
    assert [p.name for p in paths] == ["b_mdf3.dxf"]
    s = bbox.extents(ezdxf.readfile(paths[0]).modelspace()).size
    assert s.x <= BED[0] and s.y <= BED[1]


class _no_warning:
    """ブロック内で警告が出ないことを確認する。"""

    def __enter__(self):
        import warnings

        self._cm = warnings.catch_warnings(record=True)
        self.log = self._cm.__enter__()
        warnings.simplefilter("always")

    def __exit__(self, *exc):
        self._cm.__exit__(*exc)
        assert not [w for w in self.log if issubclass(w.category, UserWarning)], [str(w.message) for w in self.log]
