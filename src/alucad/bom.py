"""部品表（BOM）。アセンブリから「買うもの・切るもの」の一覧を作る。

- フレーム: 断面×長さごとの本数（長さ指定カットの注文用）
- 板: 材料ごとのパーツ一覧と、加工エリアに並べたときのシート枚数
- ネジ類: 板の穴から相手を探して判定する
    フレームの側面に当たる穴 → ボルト＋Tナット
    フレームの端面に当たる穴 → ボルト＋端面タップ加工
    相手のフレームがない穴   → ボルト＋ナット（板同士など）
  ボルトの長さは目安（板厚＋ねじ込み代を、よくある長さに切り上げ）。
  3Dプリント部品は厚み t パラメータを持つもの（L字アングルなど）だけネジを数える。
- 3Dプリント部品: 同じ形ごとの個数
"""

from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from build123d import Location, Vector

from . import materials, registry
from .assembly import Assembly
from .export import _parts, _sizes, cut_layers, print_groups
from .holes import hole_dia
from .nest import shelf_pack
from .part import Part

BOLT_LENGTHS = (6, 8, 10, 12, 16, 20, 25, 30, 35, 40)
GRIP = {"tnut": 6.0, "tap": 8.0, "nut": 5.0}  # 板厚に足すねじ込み代の目安（mm）
KIND_LABEL = {"tnut": "Tナット", "tap": "端面タップ", "nut": "ナット"}


@dataclass
class Bom:
    name: str
    frames: Counter = field(default_factory=Counter)  # (断面, 長さ) → 本数
    plates: dict = field(default_factory=lambda: defaultdict(list))  # 材料 → [(名前, 幅, 高さ)]
    sheets: dict = field(default_factory=dict)  # 材料 → シート枚数
    bolts: Counter = field(default_factory=Counter)  # (サイズ, 長さ) → 本数
    joints: Counter = field(default_factory=Counter)  # (種類, サイズ, 断面 or "") → 個数
    prints: list = field(default_factory=list)  # [(ラベル, フィラメント, 幅, 奥行き, 高さ, 個数)]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "frames": [{"profile": p, "length": L, "qty": n} for (p, L), n in sorted(self.frames.items())],
            "plates": {
                m: [{"name": nm, "w": w, "h": h} for nm, w, h in ps] for m, ps in sorted(self.plates.items())
            },
            "sheets": dict(sorted(self.sheets.items())),
            "bolts": [{"size": s, "length": L, "qty": n} for (s, L), n in sorted(self.bolts.items())],
            "joints": [
                {"kind": k, "size": s, "profile": p, "qty": n} for (k, s, p), n in sorted(self.joints.items())
            ],
            "prints": [
                {"label": lb, "filament": f, "size": [w, d, h], "qty": n} for lb, f, w, d, h, n in self.prints
            ],
        }

    def to_markdown(self) -> str:
        out = [f"# 部品表: {self.name}", ""]
        if self.frames:
            out += ["## アルミフレーム（長さ指定カット）", "", "| 断面 | 長さ (mm) | 本数 |", "|---|---:|---:|"]
            out += [f"| {p} | {_num(L)} | {n} |" for (p, L), n in sorted(self.frames.items())]
            total = {}
            for (p, L), n in self.frames.items():
                total[p] = total.get(p, 0) + L * n
            out += ["", "合計長さ: " + " / ".join(f"{p}: {_num(v)}mm" for p, v in sorted(total.items())), ""]
        if self.plates:
            out += ["## 板（レーザーカット）", "", "| 材料 | シート枚数 | パーツ数 |", "|---|---:|---:|"]
            for m, ps in sorted(self.plates.items()):
                out.append(f"| {materials.get(m).label} | {self.sheets.get(m, '-')} | {len(ps)} |")
            out += ["", "| 材料 | パーツ | 幅 × 高さ (mm) |", "|---|---|---|"]
            for m, ps in sorted(self.plates.items()):
                out += [f"| {materials.get(m).label} | {nm} | {_num(w)} × {_num(h)} |" for nm, w, h in ps]
            out.append("")
        if self.prints:
            out += ["## 3Dプリント部品", "", "| 部品 | フィラメント | 大きさ (mm) | 個数 |", "|---|---|---|---:|"]
            out += [f"| {lb} | {f} | {_num(w)} × {_num(d)} × {_num(h)} | {n} |" for lb, f, w, d, h, n in self.prints]
            out.append("")
        if self.bolts or self.joints:
            out += ["## ネジ類（目安）", "", "| 品名 | サイズ | 本数・個数 |", "|---|---|---:|"]
            out += [f"| 六角穴付きボルト | {s}×{L} | {n} |" for (s, L), n in sorted(self.bolts.items())]
            for (k, s, p), n in sorted(self.joints.items()):
                name = f"{KIND_LABEL[k]}（{p}用）" if p else KIND_LABEL[k]
                out.append(f"| {name} | {s} | {n} |")
            if any(k == "tap" for k, _, _ in self.joints):
                out += ["", "※ 端面タップ: フレームの端面の穴にネジ山を切る加工（注文時に指定するか、タップで自分で切る）"]
            out.append("")
        return "\n".join(out)

    def to_csv(self) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["分類", "品名", "仕様", "数量"])
        for (p, L), n in sorted(self.frames.items()):
            w.writerow(["フレーム", p, f"{_num(L)}mm", n])
        for m, ps in sorted(self.plates.items()):
            w.writerow(["板", materials.get(m).label, f"{len(ps)}パーツ", f"{self.sheets.get(m, '')}シート"])
        for lb, f, x, y, z, n in self.prints:
            w.writerow(["3Dプリント", lb, f"{f} {_num(x)}×{_num(y)}×{_num(z)}mm", n])
        for (s, L), n in sorted(self.bolts.items()):
            w.writerow(["ネジ", "六角穴付きボルト", f"{s}×{L}", n])
        for (k, s, p), n in sorted(self.joints.items()):
            w.writerow(["ネジ", KIND_LABEL[k], f"{s} {p}".strip(), n])
        return buf.getvalue()


def bom(obj: Part | list[Part] | Assembly, gap: float = 3.0) -> Bom:
    """アセンブリから部品表を作る。"""
    name = obj.name if isinstance(obj, Assembly) else "parts"
    parts = _parts(obj)
    frames = [p for p in parts if p.type == "frame"]
    b = Bom(name)

    for f in frames:
        b.frames[(f.params["profile"], round(f.params["length"], 2))] += 1

    by_mat: dict[str, list[Part]] = defaultdict(list)
    for p in parts:
        if p.is_flat:
            bb = p.sketch()["cut"].bounding_box()
            b.plates[p.mat].append((p.name or p.type, round(bb.size.X, 2), round(bb.size.Y, 2)))
            by_mat[p.mat].append(p)
        t = _thickness(p)
        if t is None:
            continue
        for kind, size, prof in _hole_partners(p, frames, t):
            length = _bolt_length(t + GRIP[kind])
            b.bolts[(size, length)] += 1
            b.joints[(kind, size, prof)] += 1

    for p, n in print_groups(parts):
        s = p.geometry.solid.bounding_box().size
        f = materials.FILAMENTS.get(p.params.get("filament", ""))
        b.prints.append((registry.get(p.type).label, f.label if f else "-", *(round(v, 1) for v in (s.X, s.Y, s.Z)), n))

    bed = materials.BED
    for m, ps in by_mat.items():
        items = [(p, cut_layers(p)) for p in ps]
        slots = shelf_pack(_sizes(items), bed[0], bed[1], gap, True)
        b.sheets[m] = max(s.sheet for s in slots) + 1
    return b


def export_bom(obj: Part | list[Part] | Assembly, path: str | Path) -> Path:
    """部品表を書き出す。拡張子 .md なら表、.csv なら表計算ソフト用。"""
    path = Path(path)
    b = bom(obj)
    text = b.to_csv() if path.suffix.lower() == ".csv" else b.to_markdown()
    path.parent.mkdir(parents=True, exist_ok=True)
    # CSV は Excel で文字化けしないように BOM付きUTF-8
    path.write_text(text, encoding="utf-8-sig" if path.suffix.lower() == ".csv" else "utf-8")
    return path


def _thickness(p: Part) -> float | None:
    """ボルトが貫通する厚み。板は材料の板厚、3Dプリント部品は t パラメータ。どちらもなければ数えない。"""
    if p.is_flat:
        return materials.get(p.mat).t
    if p.is_print and isinstance(p.params.get("t"), (int, float)):
        return float(p.params["t"])
    return None


def _hole_partners(plate: Part, frames: list[Part], t: float):
    """板（や3Dプリント部品）の各穴について、(種類, サイズ, 断面) を返す。"""
    for a in plate.geometry.anchors:
        if a.kind != "hole":
            continue
        idx = int(a.name.removeprefix("hole"))
        size = plate.params["holes"][idx][2] if "holes" in plate.params else plate.params.get("size", "M5")
        size = size if isinstance(size, str) else f"φ{hole_dia(size)}"
        # 穴の軸上で、板の上下それぞれ 1mm 外側の点（ワールド座標）
        top = plate.location * Location(a.pos)
        n = Vector(*a.normal)
        probes = [Location(Vector(*a.pos) + n * 1.0), Location(Vector(*a.pos) - n * (t + 1.0))]
        world = [(plate.location * pr).position for pr in probes]
        axis = (plate.location * Location(Vector(*a.pos) + n)).position - top.position

        hit = None
        for f in frames:
            solid = f.solid()
            if any(solid.is_inside(pt) for pt in world):
                fa = {x.name: x for x in f.anchors()}
                d = Vector(*fa["end1"].pos) - Vector(*fa["end0"].pos)
                parallel = abs(abs(d.normalized().dot(axis.normalized())) - 1) < 1e-6
                hit = ("tap" if parallel else "tnut", size, f.params["profile"])
                break
        yield hit or ("nut", size, "")


def _bolt_length(need: float) -> int:
    for L in BOLT_LENGTHS:
        if L >= need:
            return L
    return int(round(need))


def _num(v: float) -> str:
    return f"{v:g}"
