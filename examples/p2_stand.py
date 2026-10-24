"""Phase 2 サンプル: キット frame_stand で台を作り、全部の形式で書き出す。

実行: uv run python examples/p2_stand.py
出力（examples/out/）:
  p2_stand.json          アセンブリ（キット1行だけ。GUIはこれを編集する）
  p2_stand.step          3D（Fusion などのCADで開ける）
  p2_stand.glb           3D（Web表示用。将来のGUIで使う）
  p2_stand_mdf3.dxf      天板（MDF 3mm）
  p2_stand_acrylic5.dxf  L字プレート8枚（アクリル 5mm）

天板の穴はフレームの位置から自動計算される。W, D, H を変えて実行し直すと、全部が追従する。
"""

from pathlib import Path

from alucad import Assembly, export_glb, export_sheets, export_step, frame_stand, show

OUT = Path(__file__).parent / "out"

W, D, H = 280, 200, 150

asm = Assembly("p2_stand")
asm.add(frame_stand(W, D, H, profile="2020", top_mat="mdf3", bracket_mat="acrylic5"), name="stand")

print("書き出し:", asm.save(OUT / "p2_stand.json"))
print("書き出し:", export_step(asm, OUT / "p2_stand.step"))
print("書き出し:", export_glb(asm, OUT / "p2_stand.glb"))
for path in export_sheets(asm, OUT):  # 材料ごとに1ファイル。カーフは materials.toml の値
    print("書き出し:", path)

top = asm["stand/top"]  # キットの中身は「キットのid/名前」で取り出せる
print("天板の穴（自動計算）:", [(x, y) for x, y, _ in top.params["holes"]])
show(asm)
