"""Phase 1 サンプル: 穴あき板を1枚作って DXF に書き出す。

実行: uv run python examples/p1_panel.py
出力: examples/out/p1_panel.dxf（カーフ補正あり）
      examples/out/p1_panel_nokerf.dxf（補正なし＝設計寸法そのまま）
"""

from pathlib import Path

from alucad import export_dxf, hole_grid, panel, show

OUT = Path(__file__).parent / "out"
KERF = 0.2  # 仮の値。Phase 2 で材料ごとに設定ファイルへ移す

plate = panel(
    200,
    120,
    t=3,
    r=6,
    holes=hole_grid(200, 120, "M4", inset=10) + [[0, 0, "M6"]],
    engrave=[[0, -40, "alucad", 8]],
    score=[[-90, 40, 90, 40]],
)

print("書き出し:", export_dxf(plate, OUT / "p1_panel.dxf", kerf=KERF))
print("書き出し:", export_dxf(plate, OUT / "p1_panel_nokerf.dxf", kerf=KERF, compensate=False))
show(plate)
