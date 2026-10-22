"""VS Code の OCP CAD Viewer で表示する。"""

from __future__ import annotations

import os

from .assembly import Assembly
from .part import Part
from .registry import get

COLORS = {"frame": "silver", "plate": "burlywood"}


def show(obj: Assembly | Part | list[Part]) -> None:
    """アセンブリや部品を OCP CAD Viewer に表示する。

    VS Code で OCP CAD Viewer が開いていないと表示できない。
    環境変数 ALUCAD_NO_SHOW=1 を付けて実行すると表示を飛ばす（ファイル書き出しだけしたいとき）。
    """
    if os.environ.get("ALUCAD_NO_SHOW") == "1":
        return
    if isinstance(obj, Part):
        parts = [obj]
    else:
        parts = list(obj)

    solids, names, colors = [], [], []
    for i, p in enumerate(parts):
        solids.append(p.solid())
        names.append(p.name or f"{p.type}{i + 1}")
        colors.append(COLORS.get(get(p.type).category, "gray"))

    try:
        from ocp_vscode import show as ocp_show

        ocp_show(*solids, names=names, colors=colors)
    except Exception as e:  # ビューアが無いときにサンプル全体を落とさない
        print(f"[alucad] 3D表示できませんでした（OCP CAD Viewer は起動していますか？）: {e}")
