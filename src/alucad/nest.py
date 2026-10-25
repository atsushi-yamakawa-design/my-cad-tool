"""簡易ネスティング（長方形の行詰め＝シェルフ法）。

パーツの外接長方形を、背の高い順に左から右へ並べ、幅を超えたら次の行、
高さを超えたら次のシートへ。凹んだ形の隙間に詰めるような最適化はしない。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Slot:
    sheet: int  # 何枚目のシートか（0始まり）
    x: float  # 左下の位置
    y: float
    rotated: bool  # 90°回転して置いたか
    oversize: bool = False  # シートに入らない大きさ（1枚に1つだけ置く）


def shelf_pack(
    sizes: list[tuple[float, float]],
    width: float,
    height: float | None = None,
    gap: float = 3.0,
    rotate: bool = True,
) -> list[Slot]:
    """長方形 (w, h) のリストを並べる。戻り値は入力と同じ順番の Slot。

    height=None なら高さ無制限（シートは1枚）。
    rotate=True なら、横長に置く／入らないときは90°回す。
    """
    oriented = []
    for w, h in sizes:
        rot = False
        if rotate:
            fits = w <= width and (height is None or h <= height)
            fits_rot = h <= width and (height is None or w <= height)
            if (h > w and fits_rot) or (not fits and fits_rot):
                rot = True
        oriented.append((h, w, rot) if rot else (w, h, rot))

    order = sorted(range(len(sizes)), key=lambda i: (-oriented[i][1], -oriented[i][0]))
    slots: list[Slot | None] = [None] * len(sizes)
    sheet, x, y, row_h = 0, 0.0, 0.0, 0.0
    used = False  # 今のシートに何か置いたか

    for i in order:
        w, h, rot = oriented[i]
        if w > width or (height is not None and h > height):
            if used:
                sheet, used = sheet + 1, False
            slots[i] = Slot(sheet, 0.0, 0.0, rot, oversize=True)
            sheet, x, y, row_h = sheet + 1, 0.0, 0.0, 0.0
            continue
        if x > 0 and x + w > width:
            x, y, row_h = 0.0, y + row_h + gap, 0.0
        if height is not None and used and y + h > height:
            sheet, x, y, row_h = sheet + 1, 0.0, 0.0, 0.0
        slots[i] = Slot(sheet, x, y, rot)
        used = True
        x += w + gap
        row_h = max(row_h, h)
    return slots
