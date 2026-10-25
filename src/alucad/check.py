"""加工前チェック。レーザーで失敗しやすい形と、組み立てで困る配置を見つける。

  error   … このまま切ると確実に困る（加工エリア・造形サイズに入らない、部品同士がめり込んでいる）
  warning … 切れるが壊れやすい・燃えやすい（穴が縁に近い、細すぎる部分がある）
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from build123d import Kind, offset

from . import materials
from .assembly import Assembly
from .export import _parts
from .part import Part

MIN_WIDTH = 1.0  # これより細い部分は警告（mm）
OVERLAP_TOL = 1e-3  # これより大きい体積の重なりを「めり込み」とみなす（mm³）


@dataclass(frozen=True)
class Issue:
    level: str  # "error" | "warning"
    part: str
    message: str

    def __str__(self):
        mark = "エラー" if self.level == "error" else "注意"
        return f"[{mark}] {self.part}: {self.message}"


def check(obj: Part | list[Part] | Assembly) -> list[Issue]:
    """全部のチェックをして、見つかった問題のリストを返す（問題なしなら空）。"""
    parts = _parts(obj)
    issues: list[Issue] = []
    for i, p in enumerate(parts):
        if p.is_flat:
            issues += _check_plate(p, p.name or f"{p.type}{i + 1}")
        elif p.is_print:
            issues += _check_print(p, p.name or f"{p.type}{i + 1}")
    issues += _check_overlaps(parts)
    return issues


def _check_plate(p: Part, name: str) -> list[Issue]:
    out = []
    cut = p.sketch()["cut"]
    t = materials.get(p.mat).t
    bed = materials.BED

    bb = cut.bounding_box()
    w, h = bb.size.X, bb.size.Y
    if not ((w <= bed[0] and h <= bed[1]) or (h <= bed[0] and w <= bed[1])):
        out.append(Issue("error", name, f"{w:.1f}×{h:.1f}mm は加工エリア {bed[0]:.0f}×{bed[1]:.0f}mm に入りません"))

    # 穴（内側の輪郭）と縁・穴どうしの間隔。板厚より狭いと割れやすい
    for face in cut.faces():
        outer, inner = face.outer_wire(), face.inner_wires()
        for k, wire in enumerate(inner):
            d = outer.distance_to(wire)
            if d < t - 1e-6:
                c = wire.bounding_box().center()
                out.append(Issue("warning", name, f"穴 ({c.X:.1f}, {c.Y:.1f}) と縁の間が {d:.2f}mm（板厚 {t}mm 未満）で割れやすい"))
        for (a, wa), (b, wb) in combinations(enumerate(inner), 2):
            d = wa.distance_to(wb)
            if d < t - 1e-6:
                ca, cb = wa.bounding_box().center(), wb.bounding_box().center()
                out.append(Issue(
                    "warning", name,
                    f"穴 ({ca.X:.1f}, {ca.Y:.1f}) と ({cb.X:.1f}, {cb.Y:.1f}) の間が {d:.2f}mm（板厚 {t}mm 未満）で割れやすい",
                ))

    if _has_thin_part(cut, MIN_WIDTH / 2):
        out.append(Issue("warning", name, f"幅 {MIN_WIDTH}mm 未満の細い部分があります（燃えたり折れたりしやすい）"))
    return out


def _check_print(p: Part, name: str) -> list[Issue]:
    """3Dプリント部品が造形サイズに入るか（materials.toml に [printer] bed があるときだけ）。"""
    bed = materials.PRINT_BED
    if bed is None:
        return []
    s = p.geometry.solid.bounding_box().size
    if s.X > bed[0] or s.Y > bed[1] or s.Z > bed[2]:
        return [Issue("error", name, f"{s.X:.0f}×{s.Y:.0f}×{s.Z:.0f}mm はプリンタの造形サイズ {bed[0]:.0f}×{bed[1]:.0f}×{bed[2]:.0f}mm に入りません")]
    return []


def _has_thin_part(sketch, d: float) -> bool:
    """形を d 縮めてから d 戻し、面積が減ったら「幅 2d 未満の部分がある」。"""
    for f in sketch.faces():
        try:
            eroded = offset(f, -d, kind=Kind.INTERSECTION)
            if eroded is None or not eroded.faces():
                return True
            if f.area - offset(eroded, d, kind=Kind.INTERSECTION).area > 1e-3:
                return True
        except Exception:  # 縮めた結果が分裂・消滅すると offset が失敗する ＝ 細い部分がある
            return True
    return False


def _check_overlaps(parts: list[Part]) -> list[Issue]:
    """部品同士の3Dのめり込み。接しているだけ（体積ゼロ）はOK。"""
    out = []
    solids = [(p.name or f"{p.type}{i + 1}", p.solid()) for i, p in enumerate(parts)]
    boxes = [s.bounding_box() for _, s in solids]
    for i, j in combinations(range(len(solids)), 2):
        a, b = boxes[i], boxes[j]
        if a.max.X <= b.min.X or b.max.X <= a.min.X or a.max.Y <= b.min.Y or b.max.Y <= a.min.Y \
                or a.max.Z <= b.min.Z or b.max.Z <= a.min.Z:
            continue  # 外接箱が離れていれば重ならない
        inter = solids[i][1] & solids[j][1]
        vol = sum(s.volume for s in inter.solids()) if inter is not None else 0.0
        if vol > OVERLAP_TOL:
            out.append(Issue("error", solids[i][0], f"{solids[j][0]} とめり込んでいます（{vol:.1f}mm³）"))
    return out
