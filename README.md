# alucad

アルミフレーム（2020/3030）＋レーザーカット板のための、自分用コードCAD。
build123d（algebra mode）製。単位はすべて mm。

- 板パーツは **2Dスケッチが正**。3Dは押し出しただけの確認用
- 部品は「種類＋パラメータ＋位置・回転」の `Part`。アセンブリはそのままJSONになる
- DXFは `cut`（赤）/ `engrave`（黒）/ `score`（青）の3レイヤー。カーフ補正は書き出し時にかける

```python
from alucad import Assembly, frame_stand, export_sheets, export_step, show

asm = Assembly("demo")
asm.add(frame_stand(280, 200, 150, top_mat="mdf3"), name="stand")  # 天板の穴はフレームから自動計算
export_sheets(asm, "out")       # 材料ごとのDXF（カーフ補正は materials.toml の値）
export_step(asm, "out/demo.step")
show(asm)
```

---

## セットアップ（最初の1回だけ）

### 1. uv をインストール

macOS / Linux（ターミナル）:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Windows（PowerShell）:
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
インストールしたら**ターミナルを開き直して**、`uv --version` でバージョンが出ればOK。

### 2. リポジトリを取ってくる

```bash
git clone https://github.com/atsushi-yamakawa-design/my-cad-tool.git
cd my-cad-tool
```

### 3. 依存パッケージを入れる

```bash
uv sync
```
Python 本体も含めて、`.venv/` フォルダに全部入る（PCの他の環境は汚さない）。初回は数分かかる。

### 4. VS Code の準備

1. VS Code で `my-cad-tool` フォルダを開く
2. 拡張機能（左の四角いアイコン）で **「OCP CAD Viewer」**（作者 bernhard-42）をインストール
3. 拡張機能 **「Python」**（Microsoft）も入っていなければインストール
4. コマンドパレット（macOS: `Cmd+Shift+P` / Windows: `Ctrl+Shift+P`）→ **「Python: Select Interpreter」** → `./.venv/bin/python`（Windows は `.\.venv\Scripts\python.exe`）を選ぶ
5. 左のサイドバーに出る OCP CAD Viewer のアイコンからビューアを開く（コマンドパレットで「OCP CAD Viewer: Open viewer」でも可）

---

## 使い方

### デザインをJSONで書いて、コマンドで全部書き出す（おすすめ）

`designs/` にアセンブリのJSONを置いて:
```bash
uv run alucad build designs/stand.json          # designs/out/ に DXF・STEP・GLB・部品表
uv run alucad build designs/box.json --only dxf,bom
uv run alucad check designs/stand.json          # 加工前チェックだけ
uv run alucad bom designs/stand.json            # 部品表を画面に表示（--csv でCSV）
uv run alucad catalog                           # 使えるコンポーネントとパラメータの一覧
```
JSONの `params` の数字を書き換えて build し直すだけで、形も穴も部品表も追従する。
パラメータ名は `uv run alucad catalog` で確認できる。将来のGUIもこのJSONを編集する。

### 加工前チェック

`alucad build` は書き出す前に自動でチェックし、エラーがあれば止まる（`--force` で無視して書き出す）。
- エラー: 加工エリアに入らない板 / 部品同士の3Dのめり込み
- 注意: 穴と縁・穴どうしの間が板厚より狭い（割れやすい）/ 幅 1mm 未満の細い部分（燃えやすい・折れやすい）

Python からは `check(asm)` で問題のリストが取れる。

### 部品表（BOM）

`alucad build` で `<名前>_bom.md`（読む用）と `<名前>_bom.csv`（Excel用）が出る。
- アルミフレーム: 断面×長さごとの本数（長さ指定カットの注文にそのまま使える）
- 板: 材料ごとのシート枚数とパーツ一覧
- ネジ: 穴の位置から相手を判定（フレーム側面→Tナット、端面→タップ、相手なし→ナット）。ボルト長さは目安

### サンプルを動かす

ビューアを開いた状態で:
```bash
uv run python examples/p1_panel.py    # 穴あき板1枚 → DXF
uv run python examples/p1_stand.py    # 台を部品から手で組む → JSON + 天板DXF
uv run python examples/p2_stand.py    # 同じ台をキット1行で → JSON / STEP / GLB / 材料別DXF
uv run python examples/p3_box.py      # フィンガージョイントの箱 → ネスティングしたDXF
uv run python examples/kerf_test.py mdf3   # カーフ測定用テストピース
uv run python examples/joint_test.py mdf3  # フィンガージョイントのはめあい（fit）テストピース
```
- 3Dがビューアに表示される
- `examples/out/` に DXF / JSON / STEP / GLB が出る

ファイルだけ欲しい（3D表示しない）ときは:
```bash
ALUCAD_NO_SHOW=1 uv run python examples/p1_stand.py          # macOS / Linux
$env:ALUCAD_NO_SHOW=1; uv run python examples/p1_stand.py    # Windows PowerShell
```

### テスト

```bash
uv run pytest
```
DXFを ezdxf で読み戻して、外形寸法・穴径・穴位置・輪郭が閉じているか、を確認している。

### 材料とカーフ（materials.toml）

リポジトリ直下の `materials.toml` に、材料ごとの板厚・カーフ・表示色と、加工エリアを書く。
材料を増やすときは `[materials.xxx]` を足すだけ（`xxx` が `mat="xxx"` で使う名前）。

カーフの初期値は目安なので、材料ごとに一度は実測する:
1. `uv run python examples/kerf_test.py mdf3` → `examples/out/kerf_test_mdf3_off.dxf` を切る
2. ノギスで測る: カーフ ≒ (50 − 板の幅) と (穴径 − 10) の平均
3. `materials.toml` の `kerf` を書き換える
4. `kerf_test_mdf3_on.dxf` を切って、幅 50.0 / 穴 10.0 に近いか確認

### フィンガージョイントのはめあい

`finger_box(..., fit=0.0)` の `fit` は「凸と凹のすき間の合計（mm）」。+ でゆるく、- できつくなる。
カーフ補正は書き出し時に別でかかるので、`fit` にカーフを足し引きしないこと。

1. まずカーフを実測する（上の手順）。これで `fit=0` がほぼ「すき間ゼロ」になる
2. `uv run python examples/joint_test.py mdf3` で fit = -0.1 / 0 / +0.1 / +0.2 のペアを切って組んでみる
3. ちょうどいい値を `finger_box(fit=...)` に使う

### Beam Studio に読み込む

1. Beam Studio で「ファイル → 開く」（またはドラッグ＆ドロップ）で `examples/out/*.dxf` を開く
2. 単位を聞かれたら **mm**
3. レイヤーが `cut` / `engrave` / `score` に分かれていることを確認し、レイヤーごとに加工方法を設定する

---

## 主なAPI

| 関数 | 内容 |
|---|---|
| `frame(profile="2020", length=400, axis="x")` | フレーム。原点は片側の端面中心、そこから `axis` の＋方向へ伸びる |
| `panel(w, h, mat="mdf3", r=0, holes=[], engrave=[], score=[])` | 板。原点は板の中心（下面）。`holes=[[x, y, "M4"], ...]`。板厚は材料で決まる |
| `l_bracket(profile="2020", arm=60, mat="acrylic5", size="M5", n=2)` | L字プレート。穴はフレーム中心線上 |
| `corner_bracket(profile="2020", arm=80, mat="acrylic5", size="M5")` | 三角プレート（ガセット） |
| `frame_stand(w, d, h, profile="2020", top_mat="mdf3", brackets=True)` | キット: 脚4本＋横桟4本＋天板＋L字プレート8枚 |
| `finger_box(w, d, h, mat="mdf3", finger=10, fit=0.0, lid=True)` | キット: フィンガージョイントの箱（外寸指定）。5〜6枚の板 |
| `box_face(w, h, mat, edges="AAAA", finger=10, fit=0.0)` | フィンガージョイントの板1枚。edges は下・右・上・左に A（凸始まり）/ B（凹始まり）/ -（まっすぐ） |
| `frame_holes(plate, frames, size="M5", pitch=150)` | 板の下に接するフレームから、取り付け穴を自動計算 |
| `hole_grid(w, h, size="M5", inset=10, nx=2, ny=2)` | 板の縁から inset の位置に等間隔の穴リスト |
| `.at(x, y, z)` / `.rot(x, y, z)` | 位置・回転（度、XYZ順＝three.js の Euler 'XYZ' と同じ） |
| `.with_params(**kw)` | パラメータを一部変えた部品（位置はそのまま） |
| `Assembly(name)` / `.add(part, name=)` / `.save(path)` / `Assembly.load(path)` | アセンブリとJSON。キットの中身は `asm["stand/top"]` で取れる |
| `export_dxf(parts, path, kerf=None, compensate=True, gap=3)` | 1つのDXFに全部。kerf 省略で材料の値。加工エリアの幅で折り返して並べる |
| `export_sheets(asm, out_dir, gap=3)` | 材料ごとに、加工エリアに収まるようネスティングしたDXF。入りきらなければ `_1`, `_2`… に分割 |
| `export_step(asm, path)` / `export_glb(asm, path)` | 3D書き出し（部品名・色つき） |
| `bom(asm)` / `export_bom(asm, path)` | 部品表（.md / .csv） |
| `check(asm)` | 加工前チェック。問題（Issue）のリスト |
| `show(obj)` | OCP CAD Viewer に表示 |
| `catalog()` | 全コンポーネントのメタデータ（将来のGUI用） |

穴プリセット（JIS B 1001 2級）: M3=3.4 / M4=4.5 / M5=5.5 / M6=6.6 mm

### フレーム断面を実断面にする

`src/alucad/profiles.py` の `PROFILES` で、`dxf=` に断面DXF（中心が原点）のパスを入れる:
```python
"2020": Profile("2020", 20, slot=6, dxf="profiles/2020.dxf"),
```

## ロードマップ

- [x] Phase 1: frame / panel / DXF（カーフ補正）/ 寸法テスト / JSON
- [x] Phase 2: 材料設定、ブラケット、フレームからの穴位置自動計算、キット、STEP / GLB
- [x] Phase 3: フィンガージョイント、ネスティング
- [ ] Phase 4: Web GUI（JSON を編集する）
