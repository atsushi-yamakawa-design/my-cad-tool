"""丸棒シャフト（買ってくる部品）。リニアシャフトや丸棒を置くための部品。"""

from build123d import Align, Cylinder

from alucad.registry import Anchor, Geometry, Param, component

CENTER_Z0 = (Align.CENTER, Align.CENTER, Align.MIN)


@component(
    "shaft",
    label="シャフト（丸棒）",
    category="hardware",
    params=[
        Param("dia", float, 8.0, min=2, max=50, label="直径"),
        Param("length", float, 120.0, min=5, max=1000, label="長さ"),
    ],
)
def build(dia, length) -> Geometry:
    """原点は下の端面の中心。+Z 方向へ length 伸びる。"""
    return Geometry(
        solid=Cylinder(dia / 2, length, align=CENTER_Z0),
        anchors=[
            Anchor("bottom", (0, 0, 0), (0, 0, -1), "face"),
            Anchor("top", (0, 0, length), (0, 0, 1), "face"),
        ],
    )
