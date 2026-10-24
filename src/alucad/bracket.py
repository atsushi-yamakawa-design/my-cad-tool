"""ブラケット（レーザーで切る平板）。

どちらも「2本のフレームが直角に突き当たる角」の側面に貼る板。
穴はフレームの中心線上に自動で並ぶ（Tナットで留める想定）。
原点は外側の角で、腕は +X と +Y に伸びる。下面が z=0。

  l_bracket       L字プレート
  corner_bracket  三角プレート（ガセット）

※ 3Dの金属アングル（L字に曲がった金具）はレーザーでは作れないので、ここでは扱わない。
"""

from __future__ import annotations

from build123d import Polygon, fillet

from . import flat, profiles
from .part import Part, make, place
from .registry import Geometry, Param, component

_COMMON = [
    Param("profile", str, "2020", unit="", choices=tuple(profiles.PROFILES), label="フレーム断面"),
    Param("arm", float, 60.0, min=20, max=300, label="腕の長さ"),
    Param("mat", str, "acrylic5", unit="", choices=flat.MAT.choices, label="材料"),
    Param("size", str, "M5", unit="", choices=("M3", "M4", "M5", "M6"), label="穴サイズ"),
    Param("r", float, 2.0, min=0, max=20, label="角R"),
]


def _rounded(points, r):
    shape = Polygon(*points, align=None)
    return fillet(shape.vertices(), r) if r > 0 else shape


@component(
    "l_bracket",
    label="L字プレート",
    category="plate",
    params=_COMMON + [Param("n", int, 2, unit="個", min=1, max=10, label="腕1本あたりの穴数")],
)
def _build_l(profile, arm, mat, size, r, n) -> Geometry:
    s = profiles.get(profile).size
    if arm < 2 * s:
        raise ValueError(f"l_bracket: 腕の長さ arm は {2 * s}mm 以上にしてください（フレーム幅の2倍）")
    pts = [(0, 0), (arm, 0), (arm, s), (s, s), (s, arm), (0, arm)]
    c = s / 2
    holes = [[c, c, size]]  # 角（突き当てられる側のフレームの端）
    for i in range(n):
        d = s + (arm - s) * (i + 0.5) / n
        holes += [[d, c, size], [c, d, size]]
    return flat.flat_geometry(_rounded(pts, r), mat, holes, name="l_bracket")


@component(
    "corner_bracket",
    label="三角プレート",
    category="plate",
    params=[p if p.name != "arm" else Param("arm", float, 80.0, min=60, max=300, label="腕の長さ") for p in _COMMON],
)
def _build_corner(profile, arm, mat, size, r) -> Geometry:
    s = profiles.get(profile).size
    if arm < 3 * s:
        raise ValueError(f"corner_bracket: 腕の長さ arm は {3 * s}mm 以上にしてください（フレーム幅の3倍）")
    pts = [(0, 0), (arm, 0), (arm, s), (s, arm), (0, arm)]
    c = s / 2
    d = arm - 1.5 * s
    holes = [[c, c, size], [d, c, size], [c, d, size]]
    return flat.flat_geometry(_rounded(pts, r), mat, holes, name="corner_bracket")


def l_bracket(profile="2020", arm=60, mat="acrylic5", size="M5", r=2, n=2, **place_kw) -> Part:
    """L字プレート。例: l_bracket("2020", arm=60, mat="acrylic5")"""
    return place(
        make("l_bracket", profile=profile, arm=arm, mat=mat, size=size, r=r, n=n), **place_kw
    )


def corner_bracket(profile="2020", arm=80, mat="acrylic5", size="M5", r=2, **place_kw) -> Part:
    """三角プレート（ガセット）。例: corner_bracket("2020", arm=80)"""
    return place(make("corner_bracket", profile=profile, arm=arm, mat=mat, size=size, r=r), **place_kw)
