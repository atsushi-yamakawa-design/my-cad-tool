"""セットカラー（買う部品）。軸に止めネジ（またはクランプ）で留める輪。軸の抜け止めや、ベアリングに重さを載せるのに使う。"""

from build123d import Align, Cylinder

from alucad.registry import Anchor, Geometry, Param, component

CENTER_Z0 = (Align.CENTER, Align.CENTER, Align.MIN)


@component(
    "shaft_collar",
    label="セットカラー",
    category="hardware",
    params=[
        Param("bore", float, 8.0, min=2, max=50, label="内径"),
        Param("od", float, 14.0, min=4, max=80, label="外径"),
        Param("width", float, 8.0, min=2, max=40, label="幅"),
    ],
)
def build(bore, od, width) -> Geometry:
    """原点は下面の中心。+Z へ width。"""
    if od <= bore + 2:
        raise ValueError("shaft_collar: 外径は内径＋2mm 以上にしてください")
    solid = Cylinder(od / 2, width, align=CENTER_Z0) - Cylinder(bore / 2, width, align=CENTER_Z0)
    return Geometry(solid=solid, anchors=[Anchor("bottom", (0, 0, 0), (0, 0, -1), "face"), Anchor("top", (0, 0, width), (0, 0, 1), "face")])
