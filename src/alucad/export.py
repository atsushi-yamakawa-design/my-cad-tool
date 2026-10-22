"""書き出し（DXF）。

レイヤー:
  cut     … 切断（赤）。カーフ補正がかかるのはこのレイヤーだけ
  engrave … 刻印（黒）
  score   … 罫書き（青）

カーフ補正: レーザーは線の中心から kerf/2 ずつ材料を溶かすので、
切断線を「外形は外へ、穴は内へ」kerf/2 ずらしておくと、切り上がりが設計寸法になる。
build123d の offset() に穴あきの面を渡すと、この両方が1回で正しく処理される。
"""

from __future__ import annotations

import warnings
from pathlib import Path

from build123d import ExportDXF, Kind, Pos, Shape, Unit, offset
from build123d.exporters import ColorIndex

from .assembly import Assembly
from .part import Part

LAYER_COLORS = {
    "cut": ColorIndex.RED,
    "engrave": ColorIndex.BLACK,
    "score": ColorIndex.BLUE,
}

# FLUX beamo の加工エリア（mm）。Phase 2 で材料設定ファイルへ移す
BED = (300.0, 210.0)


def cut_layers(part: Part, kerf: float = 0.0, compensate: bool = True) -> dict[str, Shape]:
    """1パーツ分のレイヤー別2D形状（カーフ補正済み・ローカル座標）。"""
    if not part.is_flat:
        raise ValueError(f"{part.name or part.type}: 板パーツではないのでDXFにできません")
    layers = dict(part.sketch())
    if compensate and kerf > 0:
        # Kind.ARC: 凸の角は半径 kerf/2 で丸める（ビームの軌跡そのもの）
        layers["cut"] = offset(layers["cut"], kerf / 2, kind=Kind.ARC)
    return layers


def export_dxf(
    parts: Part | list[Part] | Assembly,
    path: str | Path,
    kerf: float = 0.0,
    compensate: bool = True,
    gap: float = 5.0,
) -> Path:
    """板パーツをDXF（mm）に書き出す。複数パーツは左から横一列に gap 空けて並べる。

    kerf:       カーフ（切断幅, mm）
    compensate: True ならカーフ補正をかける。False なら設計寸法そのまま
    """
    if isinstance(parts, Part):
        parts = [parts]
    elif isinstance(parts, Assembly):
        parts = parts.flat_parts()
    parts = [p for p in parts if p.is_flat]
    if not parts:
        raise ValueError("DXFにできる板パーツがありません")

    dxf = ExportDXF(unit=Unit.MM)
    for name, color in LAYER_COLORS.items():
        dxf.add_layer(name, color=color)

    x = 0.0
    top = 0.0
    for p in parts:
        layers = cut_layers(p, kerf, compensate)
        bb = layers["cut"].bounding_box()
        w, h = bb.size.X, bb.size.Y
        if not _fits_bed(w, h):
            warnings.warn(
                f"{p.name or p.type}: {w:.1f}×{h:.1f}mm は加工エリア {BED[0]:.0f}×{BED[1]:.0f}mm に入りません",
                stacklevel=2,
            )
        move = Pos(x - bb.min.X, -bb.min.Y)
        for name, shape in layers.items():
            dxf.add_shape(move * shape, layer=name)
        x += w + gap
        top = max(top, h)

    if x - gap > BED[0] or top > BED[1]:
        warnings.warn(
            f"並べた全体 {x - gap:.1f}×{top:.1f}mm が加工エリアを超えています（ネスティングは Phase 3）",
            stacklevel=2,
        )

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    dxf.write(path)
    return path


def _fits_bed(w: float, h: float) -> bool:
    return (w <= BED[0] and h <= BED[1]) or (h <= BED[0] and w <= BED[1])
