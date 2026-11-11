"""平ワッシャー（買う部品）。"""

from build123d import Align, Cylinder

from alucad.registry import Anchor, Geometry, Param, component

CENTER_Z0 = (Align.CENTER, Align.CENTER, Align.MIN)


@component(
    "washer",
    label="ワッシャー",
    category="hardware",
    params=[
        Param("d", float, 8.0, min=1, max=50, label="内径"),
        Param("od", float, 12.0, min=2, max=80, label="外径"),
        Param("t", float, 1.0, min=0.1, max=10, label="厚み"),
    ],
)
def build(d, od, t) -> Geometry:
    """原点は下面の中心。+Z へ t。"""
    if od <= d:
        raise ValueError("washer: 外径は内径より大きくしてください")
    solid = Cylinder(od / 2, t, align=CENTER_Z0) - Cylinder(d / 2, t, align=CENTER_Z0)
    return Geometry(solid=solid, anchors=[Anchor("bottom", (0, 0, 0), (0, 0, -1), "face"), Anchor("top", (0, 0, t), (0, 0, 1), "face")])
