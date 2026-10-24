"""カーフ（切断幅）測定用のテストピース。

実行: uv run python examples/kerf_test.py mdf3        ← 材料キー（materials.toml）を指定
出力（examples/out/）:
  kerf_test_<材料>_off.dxf  補正なし。これを切ってカーフを測る
  kerf_test_<材料>_on.dxf   補正あり（今の materials.toml の値）。測った値を入れた後の確認用

測り方（ノギスで）:
  1. _off を切る。50×25mm の板に φ10 の穴が開いたピースができる
  2. 板の幅（50mm の方向）を測る → カーフ ≒ 50 − 測った幅
  3. 穴の直径を測る          → カーフ ≒ 測った直径 − 10
  4. 2と3の平均を materials.toml の kerf に書く
  5. _on を切って、幅 50.0 / 穴 10.0 に近ければOK
"""

import sys
from pathlib import Path

from alucad import MATERIALS, export_dxf, panel

OUT = Path(__file__).parent / "out"

mat = sys.argv[1] if len(sys.argv) > 1 else "mdf3"
if mat not in MATERIALS:
    sys.exit(f"材料 {mat!r} は materials.toml にありません（{', '.join(MATERIALS)}）")
kerf = MATERIALS[mat].kerf


def piece(label: str):
    return panel(50, 25, mat=mat, holes=[[-12, 0, 10.0]], engrave=[[10, 0, label, 5]])


off = export_dxf(piece("OFF"), OUT / f"kerf_test_{mat}_off.dxf", compensate=False)
on = export_dxf(piece(f"k{kerf}"), OUT / f"kerf_test_{mat}_on.dxf", compensate=True)
print(f"材料: {MATERIALS[mat].label}（今の kerf = {kerf}mm）")
print("書き出し:", off)
print("書き出し:", on)
