"""フレームの足（3Dプリント）。parts/ の自作部品のお手本。

フレームの端にかぶせるカップ形。底の穴から M5 ボルトでフレーム端面のタップに留める。
"""

from build123d import Align, Box, Cylinder, Pos

from alucad import profiles
from alucad.holes import hole_dia
from alucad.printed import FILAMENT, SIZE
from alucad.registry import Anchor, Geometry, Param, component

CENTER_Z0 = (Align.CENTER, Align.CENTER, Align.MIN)


@component(
    "frame_foot",
    label="フレームの足",
    category="print",
    params=[
        Param("profile", str, "2020", unit="", choices=tuple(profiles.PROFILES), label="フレーム断面"),
        Param("t", float, 4.0, min=2, max=20, label="底の厚み"),
        Param("depth", float, 10.0, min=3, max=50, label="かぶせる深さ"),
        Param("wall", float, 2.5, min=1.2, max=10, label="壁の厚み"),
        Param("clearance", float, 0.3, min=0, max=1, label="すき間（片側）"),
        SIZE,
        FILAMENT,
    ],
)
def build(profile, t, depth, wall, clearance, size, filament) -> Geometry:
    """原点は底面の中心。z=0 がベッド側で、フレームは上から差し込む（フレームの端面は z=t）。"""
    s = profiles.get(profile).size
    inner = s + 2 * clearance  # 3Dプリントは穴が小さめに出るので、すき間を足す
    outer = inner + 2 * wall
    d = hole_dia(size)

    solid = Box(outer, outer, t + depth, align=CENTER_Z0)
    solid -= Pos(0, 0, t) * Box(inner, inner, depth, align=CENTER_Z0)  # フレームが入る凹み
    solid -= Cylinder(d / 2, t, align=CENTER_Z0)  # ボルトの穴
    solid -= Cylinder(d, t / 2, align=CENTER_Z0)  # ボルトの頭を沈める座ぐり（底側）

    return Geometry(
        solid=solid,
        anchors=[
            # 穴: pos はボルトの頭側の面、normal は相手（フレーム）から離れる向き
            Anchor("hole0", (0, 0, 0), (0, 0, -1), "hole"),
            Anchor("socket", (0, 0, t), (0, 0, 1), "face"),
        ],
    )
