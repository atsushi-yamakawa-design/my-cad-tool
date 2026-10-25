"""フィンガージョイント（板同士を凹凸で組む箱）。

辺の種類（edges の1文字）:
  "A" … 両端が凸で始まる凹凸（凸・凹・凸・…・凸）
  "B" … 両端が凹で始まる凹凸（A のちょうど逆。A の辺とかみ合う）
  "-" … 凹凸なし（まっすぐ）

凹の深さは板厚（相手の板も同じ材料の前提）。凹凸の数は辺の長さ÷finger に近い奇数で、
同じ長さの辺どうしは必ず同じ分割になるので、A と B がぴったりかみ合う。

カーフについて: 書き出し時のカーフ補正で凸も凹も設計寸法どおりに切れる（＝すき間ゼロ）。
fit は「意図的なすき間」だけを担当する。凸と凹のすき間の合計（mm）で、
+ でゆるく、- できつくなる。カーフをここで足し引きしないこと（二重補正になる）。
"""

from __future__ import annotations

from build123d import Align, Location, Plane, Pos, Rectangle, Vector

from . import flat, materials
from .part import Part, make, place
from .registry import Geometry, Param, component


def segments(length: float, finger: float) -> int:
    """辺を何分割するか（3以上の奇数）。"""
    n = max(3, round(length / finger))
    return n if n % 2 == 1 else n + 1


def _edge_cuts(kind: str, length: float, depth: float, finger: float, fit: float):
    """1辺ぶんの「凹」の区間 [(start, end), ...]（辺に沿った座標 0〜length）。"""
    if kind == "-":
        return []
    n = segments(length, finger)
    s = length / n
    e = fit / 4  # 凹を両側に fit/4 ずつ広げる。相手の板も同じだけ広がるので、すき間の合計が fit になる
    first_in = 1 if kind == "A" else 0
    cuts = []
    for i in range(first_in, n, 2):
        a = 0.0 if i == 0 else i * s - e
        b = length if i == n - 1 else (i + 1) * s + e
        cuts.append((a, b))
    return cuts


def finger_outline(w: float, h: float, edges: str, depth: float, finger: float, fit: float):
    """凹凸つきの外形スケッチ（中心が原点）。edges は 下・右・上・左 の順の4文字。"""
    if len(edges) != 4 or any(c not in "AB-" for c in edges):
        raise ValueError(f"edges は 'A' 'B' '-' の4文字で指定してください（下・右・上・左）: {edges!r}")
    shape = Rectangle(w, h, align=(Align.MIN, Align.MIN))
    bottom, right, top, left = edges
    for a, b in _edge_cuts(bottom, w, depth, finger, fit):
        shape -= Pos(a, 0) * Rectangle(b - a, depth, align=(Align.MIN, Align.MIN))
    for a, b in _edge_cuts(top, w, depth, finger, fit):
        shape -= Pos(a, h - depth) * Rectangle(b - a, depth, align=(Align.MIN, Align.MIN))
    for a, b in _edge_cuts(left, h, depth, finger, fit):
        shape -= Pos(0, a) * Rectangle(depth, b - a, align=(Align.MIN, Align.MIN))
    for a, b in _edge_cuts(right, h, depth, finger, fit):
        shape -= Pos(w - depth, a) * Rectangle(depth, b - a, align=(Align.MIN, Align.MIN))
    return Pos(-w / 2, -h / 2) * shape


@component(
    "box_face",
    label="箱の板（フィンガージョイント）",
    category="plate",
    params=[
        Param("w", float, 120.0, min=10, max=1000, label="幅"),
        Param("h", float, 80.0, min=10, max=1000, label="高さ"),
        flat.MAT,
        Param("edges", str, "AAAA", unit="", label="辺の種類（下・右・上・左。A/B/-）"),
        Param("finger", float, 10.0, min=3, max=200, label="凹凸の幅（目安）"),
        Param("fit", float, 0.0, min=-1, max=1, label="すき間（+でゆるい）"),
        flat.HOLES,
        flat.ENGRAVE,
    ],
)
def _build_face(w, h, mat, edges, finger, fit, holes, engrave) -> Geometry:
    t = materials.get(mat).t
    if min(w, h) <= 2 * t:
        raise ValueError(f"box_face: 幅・高さは板厚の2倍（{2 * t}mm）より大きくしてください")
    outline = finger_outline(w, h, edges, t, finger, fit)
    return flat.flat_geometry(outline, mat, holes, engrave, name="box_face")


def box_face(w, h, mat="mdf3", edges="AAAA", finger=10, fit=0.0, holes=(), engrave=(), **place_kw) -> Part:
    """フィンガージョイントの板1枚。原点は板の中心（下面）。

    edges: 下・右・上・左 の順に "A"（凸始まり）/ "B"（凹始まり）/ "-"（まっすぐ）
    例: box_face(120, 80, edges="AB-B")
    """
    p = make(
        "box_face", w=w, h=h, mat=mat, edges=edges, finger=finger, fit=fit,
        holes=flat.as_lists(holes), engrave=flat.as_lists(engrave),
    )
    return place(p, **place_kw)


@component(
    "finger_box",
    label="フィンガージョイントの箱",
    category="kit",
    params=[
        Param("w", float, 120.0, min=20, max=1000, label="幅（外寸）"),
        Param("d", float, 80.0, min=20, max=1000, label="奥行き（外寸）"),
        Param("h", float, 60.0, min=20, max=1000, label="高さ（外寸）"),
        flat.MAT,
        Param("finger", float, 10.0, min=3, max=200, label="凹凸の幅（目安）"),
        Param("fit", float, 0.0, min=-1, max=1, label="すき間（+でゆるい）"),
        Param("lid", bool, True, unit="", label="ふたを付ける"),
    ],
)
def _build_box(w, d, h, mat, finger, fit, lid) -> Geometry:
    t = materials.get(mat).t
    top_edge = "A" if lid else "-"
    side_top = "B" if lid else "-"
    kw = dict(mat=mat, finger=finger, fit=fit)

    def put(p: Part, origin, x_dir, z_dir) -> Part:
        loc = Location(Plane(origin=Vector(*origin), x_dir=x_dir, z_dir=z_dir))
        return p.at(*loc.position).rot(*loc.orientation)

    # 板のローカルZ（板厚の向き）は箱の内側へ、側面の板のローカルY（板の「上」）は箱の上へ。
    # 外側の面が箱の外寸にそろう
    front_edges = "AA" + top_edge + "A"
    side_edges = "BB" + side_top + "B"
    faces = [
        put(box_face(w, d, edges="BABA", **kw), (0, 0, 0), (1, 0, 0), (0, 0, 1)).named("bottom"),
        put(box_face(w, h, edges=front_edges, **kw), (0, -d / 2, h / 2), (-1, 0, 0), (0, 1, 0)).named("front"),
        put(box_face(w, h, edges=front_edges, **kw), (0, d / 2, h / 2), (1, 0, 0), (0, -1, 0)).named("back"),
        put(box_face(d, h, edges=side_edges, **kw), (-w / 2, 0, h / 2), (0, 1, 0), (1, 0, 0)).named("left"),
        put(box_face(d, h, edges=side_edges, **kw), (w / 2, 0, h / 2), (0, -1, 0), (-1, 0, 0)).named("right"),
    ]
    if lid:
        faces.append(put(box_face(w, d, edges="BABA", **kw), (0, 0, h), (1, 0, 0), (0, 0, -1)).named("top"))
    return Geometry.kit(faces)


def finger_box(w=120, d=80, h=60, mat="mdf3", finger=10, fit=0.0, lid=True, **place_kw) -> Part:
    """フィンガージョイントの箱（外寸 w×d×h）。底面の中心が原点。

    例: finger_box(120, 80, 60, mat="mdf3", finger=10)
    """
    p = make("finger_box", w=w, d=d, h=h, mat=mat, finger=finger, fit=fit, lid=lid)
    return place(p, **place_kw)
