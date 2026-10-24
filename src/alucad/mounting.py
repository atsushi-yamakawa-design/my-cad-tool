"""フレームの位置から、板の取り付け穴を自動計算する。"""

from __future__ import annotations

import math
from collections.abc import Iterable

from build123d import Location

from . import profiles
from .holes import hole_dia
from .part import Part

TOL = 0.01  # 「接している」とみなす距離（mm）


def frame_holes(
    plate: Part,
    frames: Iterable[Part],
    size: str | float = "M5",
    pitch: float = 150,
    inset: float | None = None,
) -> list[list]:
    """板の下面に接しているフレームの中心線上に、取り付け穴を並べる。

    - 板と平行なフレーム（横桟）: 中心線に沿って、端から inset、間隔 pitch 以下で並べる
    - 板と垂直なフレーム（脚）: 端面の中心に1つ（端面タップ用）
    - 板に接していないフレーム、板からはみ出す穴は無視する

    戻り値は板のローカル座標の [[x, y, size], ...]。
    使い方: top = top.with_params(holes=frame_holes(top, frames))
    """
    inv = plate.location.inverse()
    bb = plate.sketch()["cut"].bounding_box()
    rad = hole_dia(size) / 2
    holes: list[list] = []

    def add(x, y):
        if not (bb.min.X + rad <= x <= bb.max.X - rad and bb.min.Y + rad <= y <= bb.max.Y - rad):
            return
        if any(math.hypot(x - hx, y - hy) < 4 * rad for hx, hy, _ in holes):
            return  # 近すぎる穴は1つにまとめる
        holes.append([round(x, 4), round(y, 4), size])

    for f in [p for fr in frames for p in fr.expand()]:
        if f.type != "frame":
            continue
        s = profiles.get(f.params["profile"]).size
        a = {x.name: x for x in f.anchors()}
        p0 = (inv * Location(a["end0"].pos)).position
        p1 = (inv * Location(a["end1"].pos)).position
        d = p1 - p0
        length = d.length

        if abs(d.Z) < TOL:  # 板と平行
            if abs(p0.Z + s / 2) > TOL:
                continue  # 上面が板の下面に接していない
            ins = s if inset is None else inset
            span = length - 2 * ins
            n = 1 if span <= 0 else math.floor(span / pitch + 1e-9) + 1
            for i in range(n):
                k = 0.5 if n == 1 else (ins + span * i / (n - 1)) / length
                add(p0.X + d.X * k, p0.Y + d.Y * k)
        elif abs(abs(d.Z) - length) < TOL:  # 板と垂直
            for p in (p0, p1):
                if abs(p.Z) < TOL:
                    add(p.X, p.Y)
    return holes
