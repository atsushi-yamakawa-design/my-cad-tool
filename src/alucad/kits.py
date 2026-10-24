"""キット（複合コンポーネント）。

複数の部品を、寸法の関係ごとまとめて1つのコンポーネントにしたもの。
JSONには「キットの種類＋パラメータ」の1行だけが入り、中身（フレーム・天板・ブラケット）と
天板の穴位置は、パラメータから毎回計算し直される。
GUIで幅を変えれば、フレームの長さも天板の穴も追従する。
"""

from __future__ import annotations

from build123d import Location, Plane, Vector

from . import flat, materials, profiles
from .bracket import l_bracket
from .frame import frame
from .mounting import frame_holes
from .panel import panel
from .part import Part, make, place
from .registry import Anchor, Geometry, Param, component


@component(
    "frame_stand",
    label="フレームの台",
    category="kit",
    params=[
        Param("w", float, 280.0, min=60, max=2000, label="天板の幅"),
        Param("d", float, 200.0, min=60, max=2000, label="天板の奥行き"),
        Param("h", float, 150.0, min=40, max=2000, label="高さ（天板の下面まで）"),
        Param("profile", str, "2020", unit="", choices=tuple(profiles.PROFILES), label="フレーム断面"),
        Param("top_mat", str, "mdf3", unit="", choices=flat.MAT.choices, label="天板の材料"),
        Param("top_r", float, 4.0, min=0, label="天板の角R"),
        Param("brackets", bool, True, unit="", label="L字プレートを付ける"),
        Param("bracket_mat", str, "acrylic5", unit="", choices=flat.MAT.choices, label="プレートの材料"),
        Param("size", str, "M5", unit="", choices=("M3", "M4", "M5", "M6"), label="ネジ"),
    ],
)
def _build_stand(w, d, h, profile, top_mat, top_r, brackets, bracket_mat, size) -> Geometry:
    s = profiles.get(profile).size
    cx, cy = w / 2 - s / 2, d / 2 - s / 2  # 脚の中心
    zr = h - s / 2  # 横桟の中心の高さ（上面が天板の下面にそろう）

    legs = [
        frame(profile, h, axis="z").at(sx * cx, sy * cy, 0).named(f"leg_{tag}")
        for sx, sy, tag in ((-1, -1, "fl"), (1, -1, "fr"), (1, 1, "br"), (-1, 1, "bl"))
    ]
    rails = [
        frame(profile, w - 2 * s, axis="x").at(-(w / 2 - s), -cy, zr).named("rail_front"),
        frame(profile, w - 2 * s, axis="x").at(-(w / 2 - s), cy, zr).named("rail_back"),
        frame(profile, d - 2 * s, axis="y").at(-cx, -(d / 2 - s), zr).named("rail_left"),
        frame(profile, d - 2 * s, axis="y").at(cx, -(d / 2 - s), zr).named("rail_right"),
    ]
    top = panel(w, d, mat=top_mat, r=top_r).at(0, 0, h).named("top")
    top = top.with_params(holes=frame_holes(top, legs + rails, size=size))
    children = legs + rails + [top]

    if brackets:
        bt = materials.get(bracket_mat).t
        for sx, sy, tag in ((-1, -1, "fl"), (1, -1, "fr"), (1, 1, "br"), (-1, 1, "bl")):
            corner = Vector(sx * w / 2, sy * d / 2, h)  # 脚の上端の外側の角
            # 前後の面（法線 ±Y）と左右の面（法線 ±X）に1枚ずつ。腕は「横桟に沿って内側」と「脚に沿って下」
            for face, normal, along in (("y", (0, sy, 0), (-sx, 0, 0)), ("x", (sx, 0, 0), (0, -sy, 0))):
                br = l_bracket(profile, mat=bracket_mat, size=size)
                children.append(
                    _on_face(br, corner, Vector(*along), Vector(0, 0, -1), Vector(*normal), bt)
                    .named(f"plate_{tag}_{face}")
                )

    return Geometry.kit(children, anchors=[Anchor("top", (0, 0, h + materials.get(top_mat).t), (0, 0, 1), "face")])


def _on_face(p: Part, corner: Vector, u: Vector, v: Vector, outward: Vector, t: float) -> Part:
    """板パーツを、フレームの外側の面に貼り付ける位置・回転にする。

    corner: 板のローカル原点を置く点（面上）, u/v: 板のローカルX/Yを向ける方向, outward: 面の外向き法線
    板の下面（z=0）がフレーム側、上面が外側になるように、必要なら u と v を入れ替える（左右対称の板が前提）。
    """
    if u.cross(v).dot(outward) > 0:
        u, v = v, u
    n = u.cross(v)  # 板のローカルZ = フレームの内側向き
    loc = Location(Plane(origin=corner - n * t, x_dir=u, z_dir=n))
    return p.at(*loc.position).rot(*loc.orientation)


def frame_stand(w=280, d=200, h=150, profile="2020", top_mat="mdf3", top_r=4, brackets=True,
                bracket_mat="acrylic5", size="M5", **place_kw) -> Part:
    """2020/3030フレームの台（脚4本＋横桟4本＋天板＋L字プレート）。天板の穴は自動計算。

    例: frame_stand(280, 200, 150)
    """
    p = make(
        "frame_stand", w=w, d=d, h=h, profile=profile, top_mat=top_mat, top_r=top_r,
        brackets=brackets, bracket_mat=bracket_mat, size=size,
    )
    return place(p, **place_kw)
