"""板パーツ（レーザーで切るもの）の共通処理。

外形スケッチ＋穴＋刻印＋罫書き線から、レイヤー別の2Dと、押し出した3Dを作る。
"""

from __future__ import annotations

from build123d import Circle, Compound, Line, Pos, Sketch, Text, extrude

from . import materials
from .holes import hole_dia
from .registry import Anchor, Geometry, Param

# 板パーツに共通の引数（GUIのプロパティパネル用メタデータ）
MAT = Param("mat", str, "mdf3", unit="", choices=tuple(materials.MATERIALS), label="材料")
HOLES = Param("holes", list, [], unit="", label="穴 [[x, y, サイズ], ...]")
ENGRAVE = Param("engrave", list, [], unit="", label="刻印 [[x, y, 文字, 大きさ], ...]")
SCORE = Param("score", list, [], unit="", label="罫書き線 [[x1, y1, x2, y2], ...]")


def flat_geometry(
    outline: Sketch,
    mat: str,
    holes=(),
    engrave=(),
    score=(),
    anchors: list[Anchor] | None = None,
    name: str = "板",
) -> Geometry:
    """外形スケッチ（XY平面）から板パーツの Geometry を作る。下面が z=0、上面が z=板厚。"""
    t = materials.get(mat).t
    cut = outline
    anchors = list(anchors or [])
    anchors += [
        Anchor("top", (0, 0, t), (0, 0, 1), "face"),
        Anchor("bottom", (0, 0, 0), (0, 0, -1), "face"),
    ]
    for i, (x, y, size) in enumerate(holes):
        hole = Pos(x, y) * Circle(hole_dia(size) / 2)
        if (hole - outline).area > 1e-6:
            raise ValueError(f"{name}: 穴{i} ({x}, {y}) が外形からはみ出しています")
        cut -= hole
        anchors.append(Anchor(f"hole{i}", (x, y, t), (0, 0, 1), "hole"))

    layers = {"cut": cut}
    if engrave:
        layers["engrave"] = Compound(
            [Pos(x, y) * Text(str(text), float(size)) for x, y, text, size in engrave]
        )
    if score:
        layers["score"] = Compound([Line((x1, y1), (x2, y2)) for x1, y1, x2, y2 in score])

    return Geometry(solid=extrude(cut, t), layers=layers, anchors=anchors)


def as_lists(items) -> list[list]:
    """タプルのリストなどを JSON にしやすい「リストのリスト」にそろえる。"""
    return [list(x) for x in items]


def check_t(mat: str, t: float | None) -> None:
    """t= が指定されていたら、材料の板厚と一致するか確認する。"""
    if t is not None and abs(materials.get(mat).t - t) > 1e-9:
        raise ValueError(
            f"t={t} が材料 {mat!r} の板厚 {materials.get(mat).t} と一致しません"
            f"（板厚は材料で決まります。materials.toml を確認してください）"
        )
