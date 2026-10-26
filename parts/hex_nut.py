"""六角ナット（買ってくる部品）。全ネジやボルトに通して、板を挟んで留めるときに置く。"""

from build123d import Align, Cylinder, RegularPolygon, extrude

from alucad.registry import Anchor, Geometry, Param, component

CENTER_Z0 = (Align.CENTER, Align.CENTER, Align.MIN)

# JIS B 1181 六角ナット1種の 二面幅 s と 高さ m（mm）
NUTS: dict[str, tuple[float, float]] = {
    "M3": (5.5, 2.4),
    "M4": (7.0, 3.2),
    "M5": (8.0, 4.0),
    "M6": (10.0, 5.0),
    "M8": (13.0, 6.5),
    "M10": (17.0, 8.0),
    "M12": (19.0, 10.0),
}


@component(
    "hex_nut",
    label="六角ナット",
    category="hardware",
    params=[
        Param("size", str, "M8", unit="", choices=tuple(NUTS), label="ネジの太さ"),
    ],
)
def build(size) -> Geometry:
    """原点は下の面の中心。+Z 方向へナットの高さぶん伸びる。角（頂点）は ±X 向き。"""
    s, m = NUTS[size]
    d = float(size[1:])  # ネジの呼び径。見た目用なのでネジ山は付けない
    solid = extrude(RegularPolygon(s / 2, 6, major_radius=False), m) - Cylinder(d / 2, m, align=CENTER_Z0)
    return Geometry(
        solid=solid,
        anchors=[
            Anchor("bottom", (0, 0, 0), (0, 0, -1), "face"),
            Anchor("top", (0, 0, m), (0, 0, 1), "face"),
        ],
    )
