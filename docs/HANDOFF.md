# 引き継ぎメモ（これまでの経緯と、次にやること）

クラウドの Claude Code セッションで Phase 1〜4a まで作ったときの記録。ローカルの Claude Code で続きをやるときは、
まずこのファイルと `CLAUDE.md`、`README.md` を読む。

## 持ち主について

- UI デザイナー。Python は読める程度。手順はコマンド付きで省略せず説明する
- 返事は日本語、口調は砕けた感じで。**同調するだけ・極端に中立的な返事は嫌われる**。いろいろな観点を出したうえで、自分の立場をはっきり言う
- Mac（bash）。VS Code ＋ OCP CAD Viewer、uv を使用。テザリングのことがあるので、大きいダウンロードは事前に一言
- 機材: レーザーカッター FLUX beamo 30W（Beam Studio、加工エリア 300×210mm）。3Dプリンタもある（機種は未確認）

## 決めたこと（理由つき）

| 決めたこと | 理由 |
|---|---|
| 部品は「種類＋パラメータ＋位置・回転」の Part。形状は持たず必要時にレジストリから生成 | JSON ⇄ Python が常に完全に往復し、GUI は JSON を編集するだけで済む |
| 板パーツは 2D スケッチが正、3D は押し出しただけ | 当初の要件。DXF の正しさを保証しやすい |
| カーフ補正は書き出し時に `offset(+kerf/2, Kind.ARC)` を cut レイヤーだけに | 外形は外・穴は内に1回で正しく補正される（実測で確認済み） |
| フィンガージョイントの `fit` はカーフと別（すき間の合計） | 二重補正を構造的に防ぐ |
| キット（frame_stand, finger_box）は JSON 1行。中身と天板の穴は毎回再計算 | 拘束ソルバーを作らずに「寸法を変えると全部追従」を実現 |
| `frame` の `axis` はパラメータとして JSON に残す | `.rot()` と二重管理にならないように |
| GUI は FastAPI ＋ React/three.js。形状は三角形メッシュの JSON（mm・Z上）で渡す | GLB だと単位と上軸の変換が挟まりズレの元になる |
| 移動・回転はブラウザだけ、パラメータ変更だけ Python に問い合わせ | ドラッグを軽くするため（4b で効く） |
| GUI のビルド済みファイルは `src/alucad/gui/static/` にコミット | 持ち主の Mac に Node.js を入れずに済む |
| 外部変更は 1秒ポーリング＋保存時の版チェック（409） | Claude Code と GUI を同時に使っても上書き事故が起きない |
| 自作部品は `parts/*.py` に置くと自動登録・ホットリロード | チャットから部品を増やすため。本体（src/）は触らない |
| 3Dプリント部品は z=0 がベッド面、STL は同じ形をまとめて `_x個数` | そのままスライサーに入れられる |
| DXF のパーツ間隔の既定は 3mm | 5mm だと箱の6枚が1シートに収まらなかった |

## 今の状態（2026-10 時点）

- テスト 113件すべて通過（`uv run pytest`）
- できること: frame / panel / l_bracket / corner_bracket / box_face / finger_box / frame_stand /
  angle_bracket / spacer / parts/frame_foot、DXF（カーフ補正・ネスティング・材料別）、STL、STEP、GLB、
  部品表（.md/.csv、ネジの自動判定）、加工前チェック、プレビュー画像、GUI（4a）
- 持ち主が確認済み: 3D 表示（OCP CAD Viewer）、Beam Studio で DXF が表示できること、GUI の起動

## まだ確かめていないこと（実物）

1. **はめあいテストピースを切る**: `uv run python examples/joint_test.py mdf3` → Beam Studio で切る。
   どの fit がちょうどいいか、40mm 方向の実測幅を聞く → `materials.toml` の kerf と finger_box の fit の標準値を決める
2. **カーフ実測**: `examples/kerf_test.py`。材料ごと
3. **Beam Studio の細部**: 刻印の文字（SPLINE）が崩れないか、外形が LINE/ARC のバラバラでも1本の輪郭として切れるか、
   切る順番（穴→外形になっているか）。問題があれば DXF をポリライン化する
4. **3Dプリント**: frame_foot のすき間 0.3mm、angle_bracket の強度。プリンタの機種を聞いて `materials.toml` の `[printer]` を埋める

## 次にやる候補（優先度順・僕の意見）

1. 上の「実物の確認」の結果を反映（DXF 修正・標準値の調整）← 最優先
2. GUI 4b: 3D 上でのドラッグ移動・90°回転・グリッドスナップ（drei の TransformControls）
3. GUI 4c: 接続点（Anchor）へのスナップ、寸法ハンドル（フレームの端をつまんで長さを変える）
4. GUI 4d: カットシートのプレビュー（ネスティング結果の 2D 表示）、チェックで問題の部品を 3D で赤くする
5. 見た目のデザイン: 持ち主は「まず素直な見た目で作って後から直す」方針を選んだ。4b あたりで本格的に

## 環境メモ

- GUI: `uv run alucad gui`（8000番が使用中なら、動いている GUI を開くか空きポートを自動で選ぶ）
- GUI の画面を直したら `cd gui && npm install && npm run build`（`src/alucad/gui/static/` が更新される）。
  開発中は `npm run dev` ＋ 別ターミナルで `uv run alucad gui --no-browser`
- build123d は `<0.14` に固定（API が版で変わるため。上げるときはドキュメントとソースを確認してから）
- GitHub: atsushi-yamakawa-design/my-cad-tool（public）。コミットの作者メールは GitHub の noreply アドレスにする
