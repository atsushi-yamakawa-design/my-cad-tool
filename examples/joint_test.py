"""フィンガージョイントのはめあい（fit）を試すテストピース。

実行: uv run python examples/joint_test.py mdf3        ← 材料キー（materials.toml）を指定
      uv run python examples/joint_test.py mdf3 --out ~/どこか/フォルダ   ← 書き出し先を変える
出力: examples/out/joint_test_<材料>.dxf

fit を -0.1 / 0 / +0.1 / +0.2 に変えた「凸の板（A）」と「凹の板（B）」のペアが4組できる。
同じ数字どうしを直角に組んでみて、ちょうどいい固さの fit を finger_box(fit=...) に使う。
（カーフ補正は materials.toml の値でかかる。先にカーフを実測しておくと fit は 0 付近に収まるはず）
"""

import sys
from pathlib import Path

from alucad import MATERIALS, box_face, export_dxf

FITS = [-0.1, 0.0, 0.1, 0.2]

args = sys.argv[1:]
OUT = Path(__file__).parent / "out"
if "--out" in args:
    i = args.index("--out")
    OUT = Path(args[i + 1]).expanduser()
    del args[i : i + 2]

mat = args[0] if args else "mdf3"
if mat not in MATERIALS:
    sys.exit(f"材料 {mat!r} は materials.toml にありません（{', '.join(MATERIALS)}）")

pieces = []
for fit in FITS:
    label = f"{fit:+.1f}"
    pieces.append(box_face(30, 25, mat=mat, edges="A---", finger=8, fit=fit, engrave=[[0, 3, f"A {label}", 4]]))
    pieces.append(box_face(30, 25, mat=mat, edges="B---", finger=8, fit=fit, engrave=[[0, 3, f"B {label}", 4]]))

path = export_dxf(pieces, OUT / f"joint_test_{mat}.dxf", gap=3)
print(f"材料: {MATERIALS[mat].label}（kerf = {MATERIALS[mat].kerf}mm）")
print("書き出し:", path)
