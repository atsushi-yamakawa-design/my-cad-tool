"""板（パネル）。2Dスケッチが正で、3Dはそれを板厚ぶん押し出しただけの確認用。"""

from __future__ import annotations

from build123d import Circle, Compound, Line, Pos, Rectangle, RectangleRounded, Text, extrude

from .holes import hole_dia
from .part import Part, make, place
from .registry import Anchor, Geometry, Param, component


@component(
    "panel",
    label="板",
    category="plate",
    params=[
        Param("w", float, 200.0, min=1, max=1000, label="幅"),
        Param("h", float, 150.0, min=1, max=1000, label="高さ"),
        Param("t", float, 3.0, min=0.5, max=20, label="板厚"),
        Param("r", float, 0.0, min=0, label="角R"),
        Param("holes", list, [], unit="", label="穴 [[x, y, サイズ], ...]"),
        Param("engrave", list, [], unit="", label="刻印 [[x, y, 文字, 大きさ], ...]"),
        Param("score", list, [], unit="", label="罫書き線 [[x1, y1, x2, y2], ...]"),
    ],
)
def _build(w, h, t, r, holes, engrave, score) -> Geometry:
    if r * 2 >= min(w, h):
        raise ValueError(f"panel: 角R {r} が大きすぎます（幅・高さの半分未満にしてください）")

    cut = RectangleRounded(w, h, r) if r > 0 else Rectangle(w, h)
    anchors = [
        Anchor("top", (0, 0, t), (0, 0, 1), "face"),
        Anchor("bottom", (0, 0, 0), (0, 0, -1), "face"),
    ]
    for i, (x, y, size) in enumerate(holes):
        _check_inside(x, y, hole_dia(size) / 2, w, h, f"穴{i}")
        cut -= Pos(x, y) * Circle(hole_dia(size) / 2)
        anchors.append(Anchor(f"hole{i}", (x, y, t), (0, 0, 1), "hole"))

    layers = {"cut": cut}
    if engrave:
        txt = None
        for x, y, text, size in engrave:
            t_shape = Pos(x, y) * Text(str(text), float(size))
            txt = t_shape if txt is None else txt + t_shape
        layers["engrave"] = txt
    if score:
        lines = [Line((x1, y1), (x2, y2)) for x1, y1, x2, y2 in score]
        layers["score"] = Compound(lines)

    return Geometry(solid=extrude(cut, t), layers=layers, anchors=anchors)


def panel(
    w: float,
    h: float,
    t: float = 3,
    r: float = 0,
    holes=(),
    engrave=(),
    score=(),
    **place_kw,
) -> Part:
    """四角い板を作る。原点は板の中心（下面）で、上面は z=t。

    holes:   [[x, y, "M4"], ...]   x, y は板の中心からの位置。サイズは "M3"〜"M6" か直径の数値
    engrave: [[x, y, "文字", 5], ...]  刻印（engraveレイヤー）
    score:   [[x1, y1, x2, y2], ...]  罫書き線（scoreレイヤー）
    例: panel(300, 200, t=3, r=5, holes=[[-140, -90, "M5"]])
    """
    p = make(
        "panel",
        w=w,
        h=h,
        t=t,
        r=r,
        holes=[list(x) for x in holes],
        engrave=[list(x) for x in engrave],
        score=[list(x) for x in score],
    )
    return place(p, **place_kw)


def _check_inside(x, y, rad, w, h, what):
    if abs(x) + rad > w / 2 or abs(y) + rad > h / 2:
        raise ValueError(f"panel: {what} ({x}, {y}) が板からはみ出しています")
