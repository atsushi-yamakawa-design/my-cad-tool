"""アルミフレームの断面定義。

今は角柱（size×size の正方形）。実断面を使いたくなったら、
Profile の dxf に断面DXFのパスを入れるだけで差し替わる。
  例: PROFILES["2020"] = Profile("2020", 20, slot=6, dxf="profiles/2020.dxf")
断面DXFは「断面の中心が原点」になるように描いておくこと。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from build123d import Face, Rectangle, Sketch, Wire, import_dxf


@dataclass(frozen=True)
class Profile:
    name: str
    size: float  # 外形の一辺（mm）
    slot: float  # スロット幅（mm）
    dxf: str | None = None  # 実断面DXFのパス（None なら角柱）

    def section(self) -> Sketch:
        """断面スケッチ（XY平面・中心が原点）。"""
        if self.dxf is None:
            return Rectangle(self.size, self.size)
        return sketch_from_dxf(self.dxf)


PROFILES: dict[str, Profile] = {
    "2020": Profile("2020", 20, slot=6),
    "3030": Profile("3030", 30, slot=8),
}


def get(name: str) -> Profile:
    if name not in PROFILES:
        raise KeyError(f"未登録の断面: {name!r}（登録済み: {sorted(PROFILES)}）")
    return PROFILES[name]


def sketch_from_dxf(path: str | Path) -> Sketch:
    """DXFの閉じた輪郭から面を作る。一番大きい輪郭が外形、残りは穴になる。"""
    wires = Wire.combine(import_dxf(path))
    if not wires:
        raise ValueError(f"{path}: 閉じた輪郭が見つかりません")
    wires = sorted(wires, key=lambda w: Face(w).area, reverse=True)
    return Sketch([Face(wires[0], wires[1:])])
