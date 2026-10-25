"""Phase 3 サンプル: フィンガージョイントの箱（外寸 120×80×60、MDF 3mm）。

実行: uv run python examples/p3_box.py
出力（examples/out/）:
  p3_box.json       アセンブリ（キット1行）
  p3_box.step       3D
  p3_box_mdf3.dxf   6枚を加工エリア 300×210 にネスティングしたもの

組んでみて、きつい・ゆるいときは:
  - まずカーフを実測して materials.toml を直す（examples/kerf_test.py）
  - それでも合わなければ fit を調整する（+0.1 でゆるく、-0.05 できつく）。
    どの値がいいかは examples/joint_test.py のテストピースで試せる
"""

from pathlib import Path

from alucad import Assembly, export_sheets, export_step, finger_box, show

OUT = Path(__file__).parent / "out"

asm = Assembly("p3_box")
asm.add(finger_box(120, 80, 60, mat="mdf3", finger=10, fit=0.0, lid=True), name="box")

print("書き出し:", asm.save(OUT / "p3_box.json"))
print("書き出し:", export_step(asm, OUT / "p3_box.step"))
for path in export_sheets(asm, OUT, gap=3):
    print("書き出し:", path)
show(asm)
