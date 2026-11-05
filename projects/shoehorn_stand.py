"""靴べら立て（3Dプリント）。下が少し広い台形の台に、靴べらの断面の形の穴を上から開ける。

穴の形は Figma などで描いた断面の SVG パス（すき間込み）をそのまま使う。
形を変えたいときは HOLE_PATH を新しいパスの d="..." に貼り替える（M / C / Z の絶対座標だけ対応）。
mid_extra で、穴の内側のカーブの真ん中だけを押し広げて厚くできる（端に向かってなめらかに元の形へ戻る）。
"""

import re

from build123d import Align, Bezier, Pos, RectangleRounded, extrude, loft, make_face

from alucad.printed import FILAMENT
from alucad.registry import Anchor, Geometry, Param, component

# 2026_靴べら立て/pass.svg（400×121 のキャンバス、y は下向き）
HOLE_PATH = (
    "M200 0C316.59 0 409.013 54.7106 399.297 116.297C395.141 142.64 318.413 42.8974 200 45.3857"
    "C81.5859 42.8974 4.85788 142.64 0.701778 116.297C-9.01406 54.7106 83.4095 7.39703e-07 200 0Z"
)


def _beziers(path: str) -> list[list[tuple[float, float]]]:
    """SVG パスを、3次ベジェの制御点4つずつのリストにする。"""
    tokens = re.findall(r"[MCZmcz]|-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", path)
    segs, cur, i = [], None, 0
    while i < len(tokens):
        t = tokens[i]
        if t == "M":
            cur = (float(tokens[i + 1]), float(tokens[i + 2]))
            i += 3
        elif t == "C":
            i += 1
            while i < len(tokens) and tokens[i] not in "MCZmcz":
                pts = [(float(tokens[i + k]), float(tokens[i + k + 1])) for k in (0, 2, 4)]
                segs.append([cur, *pts])
                cur = pts[2]
                i += 6
        elif t in "Zz":
            i += 1
        else:
            raise ValueError(f"shoehorn_stand: SVG パスの {t!r} には対応していません（M / C / Z の絶対座標だけ）")
    return segs


def _bounds(segs) -> tuple[float, float, float, float]:
    """曲線の上の点を細かく取って、実際の外形（制御点ではなく）の範囲を求める。"""
    xs, ys = [], []
    for p0, p1, p2, p3 in segs:
        for n in range(201):
            t = n / 200
            a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t**2, t**3
            xs.append(a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0])
            ys.append(a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1])
    return min(xs), max(xs), min(ys), max(ys)


def _thicken_middle(segs, extra: float) -> None:
    """内側のカーブの真ん中の点（横の中心にあって、一番上ではない点）と、その両隣の制御点を
    extra だけ下（SVG の y＋＝厚くなる向き）へずらす。点が見つからない形なら ValueError。"""
    x0, x1, y0, _ = _bounds(segs)
    cx = (x0 + x1) / 2
    for i, seg in enumerate(segs):
        x, y = seg[3]
        if abs(x - cx) < 1e-3 * (x1 - x0) and y > y0 + 1e-6 and i + 1 < len(segs):
            nxt = segs[i + 1]
            for pt_list, k in ((seg, 2), (seg, 3), (nxt, 0), (nxt, 1)):
                px, py = pt_list[k]
                pt_list[k] = (px, py + extra)
            return
    raise ValueError("shoehorn_stand: 穴の内側の真ん中の点が見つからないので、厚みを足せません（mid_extra を 0 にしてください）")


def hole_profile(hole_w: float, mid_extra: float = 0.0):
    """穴の断面（横幅 hole_w、中心が原点、XY 平面）。SVG の y 下向きを Z 上の座標に合わせて反転する。"""
    segs = _beziers(HOLE_PATH)
    x0, x1, y0, y1 = _bounds(segs)
    s = hole_w / (x1 - x0)
    if mid_extra:
        _thicken_middle(segs, mid_extra / s)  # 横幅は変わらないので、倍率 s はそのまま使える
        x0, x1, y0, y1 = _bounds(segs)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    edges = [Bezier(*[((x - cx) * s, -(y - cy) * s) for x, y in seg]) for seg in segs]
    return make_face(edges), (x1 - x0) * s, (y1 - y0) * s


@component(
    "shoehorn_stand",
    label="靴べら立て",
    category="print",
    params=[
        Param("hole_w", float, 41.0, min=10, max=150, label="穴の横幅（すき間込み）"),
        Param("mid_extra", float, 2.0, min=-3, max=20, label="穴の真ん中の厚みを足す"),
        Param("depth", float, 50.0, min=5, max=170, label="穴の深さ"),
        Param("bottom", float, 100.0, min=20, max=180, label="底の大きさ（正方形の一辺）"),
        Param("top", float, 90.0, min=20, max=180, label="上面の大きさ（正方形の一辺）"),
        Param("h", float, 60.0, min=10, max=180, label="高さ"),
        Param("r", float, 5.0, min=0.5, max=40, label="角の丸み"),
        FILAMENT,
    ],
)
def build(hole_w, mid_extra, depth, bottom, top, h, r, filament) -> Geometry:
    """原点は底面の中心。z=0 がベッドに乗る面で、穴は上面から下へ depth の深さ。"""
    if depth > h - 2:
        raise ValueError("shoehorn_stand: 穴の底が抜けないよう、深さは高さより 2mm 以上浅くしてください")
    if r * 2 >= min(top, bottom):
        raise ValueError("shoehorn_stand: 角の丸みは、上面と底の一辺の半分より小さくしてください")
    hole, hw, hd = hole_profile(hole_w, mid_extra)
    if hw > top - 6 or hd > top - 6:
        raise ValueError("shoehorn_stand: 穴が上面からはみ出します。上面を大きくするか穴を小さくしてください")

    body = loft([RectangleRounded(bottom, bottom, r), Pos(0, 0, h) * RectangleRounded(top, top, r)])
    solid = body - Pos(0, 0, h - depth) * extrude(hole, depth)
    return Geometry(solid=solid, anchors=[Anchor("top", (0, 0, h), (0, 0, 1), "face")])
