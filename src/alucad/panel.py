"""板（パネル）。2Dスケッチが正で、3Dはそれを板厚ぶん押し出しただけの確認用。"""

from __future__ import annotations

from build123d import Rectangle, RectangleRounded

from . import flat
from .part import Part, make, place
from .registry import Geometry, Param, component


@component(
    "panel",
    label="板",
    category="plate",
    params=[
        Param("w", float, 200.0, min=1, max=1000, label="幅"),
        Param("h", float, 150.0, min=1, max=1000, label="高さ"),
        flat.MAT,
        Param("r", float, 0.0, min=0, label="角R"),
        flat.HOLES,
        flat.ENGRAVE,
        flat.SCORE,
    ],
)
def _build(w, h, mat, r, holes, engrave, score) -> Geometry:
    if r * 2 >= min(w, h):
        raise ValueError(f"panel: 角R {r} が大きすぎます（幅・高さの半分未満にしてください）")
    outline = RectangleRounded(w, h, r) if r > 0 else Rectangle(w, h)
    return flat.flat_geometry(outline, mat, holes, engrave, score, name="panel")


def panel(
    w: float,
    h: float,
    mat: str = "mdf3",
    r: float = 0,
    holes=(),
    engrave=(),
    score=(),
    t: float | None = None,
    **place_kw,
) -> Part:
    """四角い板を作る。原点は板の中心（下面）で、上面は z=板厚。

    mat:     材料（materials.toml のキー）。板厚とカーフは材料で決まる
    holes:   [[x, y, "M4"], ...]   x, y は板の中心からの位置。サイズは "M3"〜"M6" か直径の数値
    engrave: [[x, y, "文字", 5], ...]  刻印（engraveレイヤー）
    score:   [[x1, y1, x2, y2], ...]  罫書き線（scoreレイヤー）
    t:       板厚の確認用。指定すると材料の板厚と一致するかチェックする
    例: panel(300, 200, mat="acrylic3", r=5, holes=[[-140, -90, "M5"]])
    """
    flat.check_t(mat, t)
    p = make(
        "panel",
        w=w,
        h=h,
        mat=mat,
        r=r,
        holes=flat.as_lists(holes),
        engrave=flat.as_lists(engrave),
        score=flat.as_lists(score),
    )
    return place(p, **place_kw)
