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

from build123d import Color, Compound, ExportDXF, Kind, Pos, Rot, Shape, Unit, export_gltf, offset
from build123d import export_step as _b3d_export_step
from build123d.exporters import ColorIndex

from . import materials
from .assembly import Assembly
from .nest import shelf_pack
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
    rotate: bool = False,
) -> Path:
    """板パーツを1つのDXF（mm）に書き出す。

    パーツは背の高い順に、加工エリアの幅で折り返しながら並べる（高さは無制限＝1ファイル）。
    加工エリアに収まるように複数シートへ分けたいときは export_sheets() を使う。

    kerf:       カーフ（mm）。省略すると各パーツの材料の値を使う
    compensate: True ならカーフ補正をかける。False なら設計寸法そのまま
    rotate:     True なら横長になるようにパーツを90°回して並べる
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
    items = [(p, cut_layers(p, kerf, compensate)) for p in parts]
    slots = shelf_pack(_sizes(items), materials.BED[0], None, gap, rotate)
    w, h = _write(items, slots, Path(path))
    bed = materials.BED
    if w > bed[0] + 1e-9 or h > bed[1] + 1e-9:
        warnings.warn(
            f"並べた全体 {w:.1f}×{h:.1f}mm が加工エリア {bed[0]:.0f}×{bed[1]:.0f}mm を超えています"
            "（export_sheets() なら複数シートに分けます）",
            stacklevel=2,
        )
    return Path(path)


def export_sheets(
    obj: Part | list[Part] | Assembly,
    out_dir: str | Path,
    prefix: str | None = None,
    compensate: bool = True,
    gap: float = 5.0,
    rotate: bool = True,
) -> list[Path]:
    """板パーツを材料ごとに分け、加工エリアに収まるようにネスティングしてDXFに書き出す。

    ファイル名: <prefix>_<材料>.dxf。1枚に収まらなければ <prefix>_<材料>_1.dxf, _2.dxf, …
    （prefix 省略時は Assembly の名前）
    """
    if prefix is None:
        prefix = obj.name if isinstance(obj, Assembly) else "parts"
    groups: dict[str, list[Part]] = defaultdict(list)
    for p in _parts(obj):
        if p.is_flat:
            groups[p.mat].append(p)

    bed = materials.BED
    paths = []
    for mat, ps in sorted(groups.items()):
        items = [(p, cut_layers(p, None, compensate)) for p in ps]
        slots = shelf_pack(_sizes(items), bed[0], bed[1], gap, rotate)
        for item, slot in zip(items, slots):
            if slot.oversize:
                p = item[0]
                warnings.warn(f"{p.name or p.type} は加工エリア {bed[0]:.0f}×{bed[1]:.0f}mm に入りません", stacklevel=2)
        n = max(s.sheet for s in slots) + 1
        for k in range(n):
            sel = [(it, sl) for it, sl in zip(items, slots) if sl.sheet == k]
            name = f"{prefix}_{mat}.dxf" if n == 1 else f"{prefix}_{mat}_{k + 1}.dxf"
            path = Path(out_dir) / name
            _write([it for it, _ in sel], [sl for _, sl in sel], path)
            paths.append(path)
    return paths


def _sizes(items) -> list[tuple[float, float]]:
    out = []
    for _, layers in items:
        bb = layers["cut"].bounding_box()
        out.append((bb.size.X, bb.size.Y))
    return out


def _write(items, slots, path: Path) -> tuple[float, float]:
    """並べ終わった位置でDXFを書く。戻り値は使った範囲の幅・高さ。"""
    dxf = ExportDXF(unit=Unit.MM)
    for name, color in LAYER_COLORS.items():
        dxf.add_layer(name, color=color)
    used_w = used_h = 0.0
    for (_, layers), slot in zip(items, slots):
        if slot.rotated:
            layers = {k: Rot(0, 0, 90) * v for k, v in layers.items()}
        bb = layers["cut"].bounding_box()
        move = Pos(slot.x - bb.min.X, slot.y - bb.min.Y)
        for name, shape in layers.items():
            dxf.add_shape(move * shape, layer=name)
        used_w = max(used_w, slot.x + bb.size.X)
        used_h = max(used_h, slot.y + bb.size.Y)
    path.parent.mkdir(parents=True, exist_ok=True)
    dxf.write(path)
    return used_w, used_h


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

