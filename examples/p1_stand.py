"""Phase 1 サンプル: 2020フレームで 280×200 の天板を支える小さな台。

実行: uv run python examples/p1_stand.py
出力: examples/out/p1_stand.json（アセンブリ）
      examples/out/p1_stand_top.dxf（天板）

ここでは部品を1つずつ手で組み、天板の穴位置も手で計算している。
同じ台を、穴の自動計算・ブラケットつきのキット1行で作るのが examples/p2_stand.py。
"""

from pathlib import Path

from alucad import Assembly, PROFILES, export_dxf, frame, panel, show

OUT = Path(__file__).parent / "out"

W, D, H = 280, 200, 150  # 天板の幅・奥行き、天板下面までの高さ
PROF = "2020"
S = PROFILES[PROF].size  # フレームの太さ = 20

asm = Assembly("p1_stand")

# 脚 4本（四隅。外形が天板とそろう位置）
cx, cy = W / 2 - S / 2, D / 2 - S / 2  # 脚の中心 = (±130, ±90)
for i, (sx, sy) in enumerate([(-1, -1), (1, -1), (1, 1), (-1, 1)], start=1):
    asm.add(frame(PROF, H, axis="z").at(sx * cx, sy * cy, 0), name=f"leg{i}")

# 上の横桟（脚と脚の間）
zr = H - S / 2  # 横桟の中心の高さ
for sy, tag in ((-1, "front"), (1, "back")):
    asm.add(frame(PROF, W - 2 * S, axis="x").at(-(W / 2 - S), sy * cy, zr), name=f"rail_{tag}")
for sx, tag in ((-1, "left"), (1, "right")):
    asm.add(frame(PROF, D - 2 * S, axis="y").at(sx * cx, -(D / 2 - S), zr), name=f"rail_{tag}")

# 天板。四隅は脚の端面タップ（M5）、辺の中央は横桟のTナット（M5）に留める想定
holes = [[sx * cx, sy * cy, "M5"] for sx in (-1, 1) for sy in (-1, 1)]
holes += [[0, -cy, "M5"], [0, cy, "M5"], [-cx, 0, "M5"], [cx, 0, "M5"]]
asm.add(panel(W, D, t=3, r=4, holes=holes).at(0, 0, H), name="top")

print("書き出し:", asm.save(OUT / "p1_stand.json"))
print("書き出し:", export_dxf(asm, OUT / "p1_stand_top.dxf", kerf=0.2))
show(asm)
