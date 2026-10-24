"""書き出し（DXF / STEP / GLB）。

DXFのレイヤー:
  cut     … 切断（赤）。カーフ補正がかかるのはこのレイヤーだけ
  engrave … 刻印（黒）
  score   … 罫書き（青）

カーフ補正: レーザーは線の中心から kerf/2 ずつ材料を溶かすので、
切断線を「外形は外へ、穴は内へ」kerf/2 ずらしておくと、切り上がりが設計寸法になる。
build123d の offset() に穴あきの面を渡すと、この両方が1回で正しく処理される。
"""

from __future__ import annotations

import warnings
from collections import defaultdict
from pathlib import Path

from build123d import Color, Compound, ExportDXF, Kind, Pos, Shape, Unit, export_gltf, offset
from build123d import export_step as _b3d_export_step
from build123d.exporters import ColorIndex

from . import materials
from .assembly import Assembly
from .part import Part
from .registry import get

LAYER_COLORS = {
    "cut": ColorIndex.RED,
    "engrave": ColorIndex.BLACK,
    "score": ColorIndex.BLUE,
}
FRAME_COLOR = "silver"


def _parts(obj: Part | list[Part] | Assembly) -> list[Part]:
    """Part / Part のリスト / Assembly を、キットを展開した Part のリストにする。"""
    if isinstance(obj, Part):
        obj = [obj]
    return [q for p in obj for q in p.expand()]


def cut_layers(part: Part, kerf: float | None = None, compensate: bool = True) -> dict[str, Shape]:
    """1パーツ分のレイヤー別2D形状（カーフ補正済み・ローカル座標）。

    kerf を省略すると、パーツの材料のカーフ（materials.toml）を使う。
    """
    if not part.is_flat:
        raise ValueError(f"{part.name or part.type}: 板パーツではないのでDXFにできません")
    if kerf is None:
        kerf = materials.get(part.mat).kerf
    layers = dict(part.sketch())
    if compensate and kerf > 0:
        # Kind.ARC: 凸の角は半径 kerf/2 で丸める（ビームの軌跡そのもの）
        layers["cut"] = offset(layers["cut"], kerf / 2, kind=Kind.ARC)
    return layers


def export_dxf(
    parts: Part | list[Part] | Assembly,
    path: str | Path,
    kerf: float | None = None,
    compensate: bool = True,
    gap: float = 5.0,
) -> Path:
    """板パーツをDXF（mm）に書き出す。複数パーツは gap 空けて並べ、加工エリアの幅で折り返す。

    kerf:       カーフ（mm）。省略すると各パーツの材料の値を使う
    compensate: True ならカーフ補正をかける。False なら設計寸法そのまま
    """
    parts = [p for p in _parts(parts) if p.is_flat]
    if not parts:
        raise ValueError("DXFにできる板パーツがありません")
    mats = {p.mat for p in parts}
    if len(mats) > 1:
        warnings.warn(
            f"材料が混ざっています {sorted(mats)}。材料ごとに分けるなら export_sheets() を使ってください",
            stacklevel=2,
        )

    bed = materials.BED
    dxf = ExportDXF(unit=Unit.MM)
    for name, color in LAYER_COLORS.items():
        dxf.add_layer(name, color=color)

    # 左から右へ並べ、加工エリアの幅を超えたら上の行へ折り返す（簡易版。本格的なネスティングは Phase 3）
    x = y = row_h = used_w = 0.0
    for p in parts:
        layers = cut_layers(p, kerf, compensate)
        bb = layers["cut"].bounding_box()
        w, h = bb.size.X, bb.size.Y
        if not _fits_bed(w, h, bed):
            warnings.warn(
                f"{p.name or p.type}: {w:.1f}×{h:.1f}mm は加工エリア {bed[0]:.0f}×{bed[1]:.0f}mm に入りません",
                stacklevel=2,
            )
        if x > 0 and x + w > bed[0]:
            x, y, row_h = 0.0, y + row_h + gap, 0.0
        move = Pos(x - bb.min.X, y - bb.min.Y)
        for name, shape in layers.items():
            dxf.add_shape(move * shape, layer=name)
        used_w = max(used_w, x + w)
        x += w + gap
        row_h = max(row_h, h)

    if used_w > bed[0] or y + row_h > bed[1]:
        warnings.warn(
            f"並べた全体 {used_w:.1f}×{y + row_h:.1f}mm が加工エリアを超えています（ネスティングは Phase 3）",
            stacklevel=2,
        )

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    dxf.write(path)
    return path


def export_sheets(
    obj: Part | list[Part] | Assembly,
    out_dir: str | Path,
    prefix: str | None = None,
    compensate: bool = True,
    gap: float = 5.0,
) -> list[Path]:
    """板パーツを材料ごとに分けて、材料1つにつき1つのDXFに書き出す。

    ファイル名: <prefix>_<材料>.dxf（prefix 省略時は Assembly の名前）
    """
    if prefix is None:
        prefix = obj.name if isinstance(obj, Assembly) else "parts"
    groups: dict[str, list[Part]] = defaultdict(list)
    for p in _parts(obj):
        if p.is_flat:
            groups[p.mat].append(p)
    return [
        export_dxf(ps, Path(out_dir) / f"{prefix}_{mat}.dxf", compensate=compensate, gap=gap)
        for mat, ps in sorted(groups.items())
    ]


def to_compound(obj: Part | list[Part] | Assembly, name: str = "assembly") -> Compound:
    """3D形状をまとめた Compound（部品ごとに名前と色つき）。"""
    if isinstance(obj, Assembly):
        name = obj.name
    children = []
    for i, p in enumerate(_parts(obj)):
        s = p.solid()
        s.label = p.name or f"{p.type}{i + 1}"
        s.color = Color(part_color(p))
        children.append(s)
    return Compound(children=children, label=name)


def part_color(p: Part) -> str:
    if get(p.type).category == "frame":
        return FRAME_COLOR
    if p.mat:
        return materials.get(p.mat).color
    return "gray"


def export_step(obj: Part | list[Part] | Assembly, path: str | Path) -> Path:
    """3DアセンブリをSTEP（mm）で書き出す。部品ごとの名前と色も入る。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not _b3d_export_step(to_compound(obj), path, unit=Unit.MM):
        raise RuntimeError(f"STEPの書き出しに失敗しました: {path}")
    return path


def export_glb(obj: Part | list[Part] | Assembly, path: str | Path) -> Path:
    """3DアセンブリをGLB（glTFバイナリ）で書き出す。Web表示（three.js）用。

    build123d が Z-up → glTF の Y-up に自動で変換する。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not export_gltf(to_compound(obj), path, unit=Unit.MM, binary=True):
        raise RuntimeError(f"GLBの書き出しに失敗しました: {path}")
    return path


def _fits_bed(w: float, h: float, bed) -> bool:
    return (w <= bed[0] and h <= bed[1]) or (h <= bed[0] and w <= bed[1])
