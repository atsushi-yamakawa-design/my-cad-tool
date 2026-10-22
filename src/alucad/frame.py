"""アルミフレーム。"""

from __future__ import annotations

from build123d import Intrinsic, Location, extrude

from . import profiles
from .part import Part, make, place
from .registry import Anchor, Geometry, Param, component

# axis ごとの向き（ローカルZ軸をその方向へ向ける回転）
_AXIS_ROT = {"z": (0, 0, 0), "x": (0, 90, 0), "y": (-90, 0, 0)}
_AXIS_VEC = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}


@component(
    "frame",
    label="アルミフレーム",
    category="frame",
    params=[
        Param("profile", str, "2020", unit="", choices=tuple(profiles.PROFILES), label="断面"),
        Param("length", float, 400.0, min=1, max=3000, label="長さ"),
        Param("axis", str, "x", unit="", choices=("x", "y", "z"), label="向き"),
    ],
)
def _build(profile: str, length: float, axis: str) -> Geometry:
    prof = profiles.get(profile)
    rot = Location((0, 0, 0), _AXIS_ROT[axis], Intrinsic.XYZ)
    solid = rot * extrude(prof.section(), length)

    d = _AXIS_VEC[axis]
    end1 = tuple(c * length for c in d)
    mid = tuple(c * length / 2 for c in d)
    anchors = [
        Anchor("end0", (0, 0, 0), tuple(-c for c in d), "end"),
        Anchor("end1", end1, d, "end"),
    ]
    # 側面4つ（軸に直交する2方向 × 正負）
    s = prof.size / 2
    for ax in "xyz":
        if ax == axis:
            continue
        for sign, tag in ((1, "+"), (-1, "-")):
            n = tuple(sign * c for c in _AXIS_VEC[ax])
            pos = tuple(m + s * c for m, c in zip(mid, n))
            anchors.append(Anchor(f"side{tag}{ax}", pos, n, "face"))
    return Geometry(solid=solid, anchors=anchors)


def frame(profile: str = "2020", length: float = 400, axis: str = "x", **place_kw) -> Part:
    """アルミフレームを1本作る。

    原点が片方の端面の中心で、そこから axis 方向（+側）へ length だけ伸びる。
    例: frame("2020", 400).at(0, 0, 10)
        frame("2020", 150, axis="z", at=(0, 0, 0))
    """
    return place(make("frame", profile=profile, length=length, axis=axis), **place_kw)

