"""フランジ付きベアリング（買う部品）。外輪の片側につば（フランジ）があり、板の穴に落とし込むだけで抜け止めになる。

板に付けるときは、穴を外径＋0.1mm くらいにして落とし込み、つばの上から押さえ（3Dプリントの輪など）で留める。
アクリルに圧入すると割れやすいので、きつい穴に押し込まない。
"""

from build123d import Align, Cylinder, Pos

from alucad.registry import Anchor, Geometry, Param, component

CENTER_Z0 = (Align.CENTER, Align.CENTER, Align.MIN)

# 型番 → (内径, 外径, 幅, つばの外径, つばの厚み)
MODELS = {
    "F608ZZ": (8.0, 22.0, 7.0, 25.0, 1.5),
    "F688ZZ": (8.0, 16.0, 5.0, 18.0, 1.1),
    "F625ZZ": (5.0, 16.0, 5.0, 18.0, 1.0),
    "F623ZZ": (3.0, 10.0, 4.0, 11.5, 1.0),
}


@component(
    "flange_bearing",
    label="フランジ付きベアリング",
    category="hardware",
    params=[Param("model", str, "F608ZZ", unit="", choices=tuple(MODELS), label="型番")],
)
def build(model) -> Geometry:
    """原点はつばの下面（板に乗る面）の中心。つばは +Z 側（z=0〜つばの厚み）、本体は -Z へ伸びる。
    内輪・外輪の上面はつばの上面と同じ高さ（接続点 top）。下面は接続点 bottom。"""
    d, D, B, fd, ft = MODELS[model]
    solid = Pos(0, 0, ft - B) * Cylinder(D / 2, B, align=CENTER_Z0) + Cylinder(fd / 2, ft, align=CENTER_Z0)
    solid -= Pos(0, 0, ft - B) * Cylinder(d / 2, B, align=CENTER_Z0)
    return Geometry(
        solid=solid,
        anchors=[
            Anchor("seat", (0, 0, 0), (0, 0, -1), "face"),
            Anchor("top", (0, 0, ft), (0, 0, 1), "face"),
            Anchor("bottom", (0, 0, ft - B), (0, 0, -1), "face"),
        ],
    )
