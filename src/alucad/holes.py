"""ボルト通し穴のプリセットと穴パターン。

穴径は JIS B 1001 ボルト穴径の2級（一般的な「ちょっと余裕のある通し穴」）。
"""

from __future__ import annotations

HOLES: dict[str, float] = {
    "M3": 3.4,
    "M4": 4.5,
    "M5": 5.5,
    "M6": 6.6,
}


def hole_dia(size: str | float) -> float:
    """"M4" のようなプリセット名、または直径（mm）の数値から穴径を返す。"""
    if isinstance(size, str):
        if size not in HOLES:
            raise KeyError(f"未登録の穴サイズ: {size!r}（使えるもの: {sorted(HOLES)}、または直径の数値）")
        return HOLES[size]
    return float(size)


def hole_grid(
    w: float, h: float, size: str | float = "M5", inset: float = 10, nx: int = 2, ny: int = 2
) -> list[list]:
    """板（w×h、中心が原点）の縁から inset の位置に、nx×ny 個の穴を等間隔で並べる。

    戻り値は panel(holes=...) にそのまま渡せる [[x, y, size], ...]。
    """
    xs = _spread(w / 2 - inset, nx)
    ys = _spread(h / 2 - inset, ny)
    return [[x, y, size] for y in ys for x in xs]


def _spread(half: float, n: int) -> list[float]:
    if n == 1:
        return [0.0]
    step = 2 * half / (n - 1)
    return [round(-half + i * step, 6) for i in range(n)]
