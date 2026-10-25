"""3Dプリント部品。

決まりごと:
  - ローカル座標の z=0 の面がプリンタのベッドに乗る面（そのまま書き出せば刷りやすい向き）
  - category="print"、材料は filament パラメータ（materials.toml の [filaments.xxx]）
  - 取り付け穴は Anchor(kind="hole") で、pos は「ボルトの頭側の面」、normal は相手から離れる向き
    （部品表がこの穴からTナット・タップを判定する。板パーツと同じ決まり）
"""

from __future__ import annotations

from build123d import Align, Axis, Box, Cylinder, Polygon, Plane, Pos, Rot, extrude, fillet

from . import materials, profiles
from .holes import HOLES, hole_dia
from .part import Part, make, place
from .registry import Anchor, Geometry, Param, component

FILAMENT = Param("filament", str, "pla", unit="", choices=tuple(materials.FILAMENTS), label="フィラメント")
SIZE = Param("size", str, "M5", unit="", choices=tuple(HOLES), label="ネジ")
_MIN_CY = (Align.MIN, Align.CENTER, Align.MIN)
_CENTER_Z0 = (Align.CENTER, Align.CENTER, Align.MIN)


@component(
    "angle_bracket",
    label="L字アングル（3Dプリント）",
    category="print",
    params=[
        Param("profile", str, "2020", unit="", choices=tuple(profiles.PROFILES), label="フレーム断面"),
        Param("arm", float, 30.0, min=10, max=200, label="腕の長さ"),
        Param("t", float, 4.0, min=1.5, max=20, label="厚み"),
        SIZE,
        Param("ribs", bool, True, unit="", label="補強リブ"),
        FILAMENT,
    ],
)
def _build_angle(profile, arm, t, size, ribs, filament) -> Geometry:
    """フレームの内側の角に入れるL字アングル。幅はフレームの太さ。

    原点は外側の角。腕は +X（ベッドに寝る側）と +Z（立ち上がる側）に伸びる。
    """
    w = profiles.get(profile).size
    d = hole_dia(size)
    rib_t = 2.0
    if arm < t + d + 2:
        raise ValueError(f"angle_bracket: 腕の長さは {t + d + 2:.1f}mm 以上にしてください（厚み＋穴＋余白）")
    if ribs and w < d + 2 * rib_t + 2:
        raise ValueError(f"angle_bracket: フレーム幅 {w}mm ではリブと穴が入りません（ribs=False にしてください）")

    solid = Box(arm, w, t, align=_MIN_CY) + Box(t, w, arm, align=_MIN_CY)
    inner = solid.edges().filter_by(Axis.Y).filter_by_position(Axis.X, t - 0.01, t + 0.01)
    inner = inner.filter_by_position(Axis.Z, t - 0.01, t + 0.01)
    solid = fillet(inner, min(t, arm - t - d) * 0.8)
    if ribs:
        r = arm - 2
        tri = extrude(Plane.XZ * Polygon((t, t), (r, t), (t, r), align=None), rib_t)  # y: -rib_t〜0
        solid += Pos(0, w / 2, 0) * tri + Pos(0, -w / 2 + rib_t, 0) * tri

    c = t + (arm - t) / 2  # 穴の中心（腕の、角から先の部分の真ん中）
    hole = Cylinder(d / 2, t, align=_CENTER_Z0)
    solid -= Pos(c, 0, 0) * hole  # ベッド側の腕（Z方向の穴）
    solid -= Pos(0, 0, c) * Rot(0, 90, 0) * hole  # 立ち上がる腕（X方向の穴）
    anchors = [
        Anchor("hole0", (c, 0, t), (0, 0, 1), "hole"),
        Anchor("hole1", (t, 0, c), (1, 0, 0), "hole"),
        Anchor("bottom", (c, 0, 0), (0, 0, -1), "face"),
        Anchor("back", (0, 0, c), (-1, 0, 0), "face"),
    ]
    return Geometry(solid=solid, anchors=anchors)


@component(
    "spacer",
    label="スペーサー（3Dプリント）",
    category="print",
    params=[
        Param("od", float, 10.0, min=3, max=100, label="外径"),
        Param("h", float, 10.0, min=0.5, max=200, label="高さ"),
        SIZE,
        FILAMENT,
    ],
)
def _build_spacer(od, h, size, filament) -> Geometry:
    """ボルトを通す円筒スペーサー。原点は底面の中心。"""
    d = hole_dia(size)
    if od < d + 2:
        raise ValueError(f"spacer: 外径は {d + 2:.1f}mm 以上にしてください（穴径＋肉厚1mm×2）")
    solid = Cylinder(od / 2, h, align=_CENTER_Z0) - Cylinder(d / 2, h, align=_CENTER_Z0)
    return Geometry(
        solid=solid,
        anchors=[
            Anchor("hole0", (0, 0, h), (0, 0, 1), "hole"),
            Anchor("top", (0, 0, h), (0, 0, 1), "face"),
            Anchor("bottom", (0, 0, 0), (0, 0, -1), "face"),
        ],
    )


def angle_bracket(profile="2020", arm=30, t=4, size="M5", ribs=True, filament="pla", **place_kw) -> Part:
    """3Dプリントの L字アングル。例: angle_bracket("2020", arm=30).at(10, 0, 0)"""
    return place(make("angle_bracket", profile=profile, arm=arm, t=t, size=size, ribs=ribs, filament=filament), **place_kw)


def spacer(od=10, h=10, size="M5", filament="pla", **place_kw) -> Part:
    """3Dプリントの円筒スペーサー。例: spacer(10, 5, "M3")"""
    return place(make("spacer", od=od, h=h, size=size, filament=filament), **place_kw)
