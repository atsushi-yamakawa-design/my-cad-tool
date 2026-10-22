# alucad

アルミフレーム（2020/3030）＋レーザーカット板のための、自分用コードCAD。
build123d（algebra mode）製。単位はすべて mm。

- 板パーツは **2Dスケッチが正**。3Dは押し出しただけの確認用
- 部品は「種類＋パラメータ＋位置・回転」の `Part`。アセンブリはそのままJSONになる
- DXFは `cut`（赤）/ `engrave`（黒）/ `score`（青）の3レイヤー。カーフ補正は書き出し時にかける

```python
from alucad import frame, panel, Assembly, export_dxf, show

asm = Assembly("demo")
asm.add(frame("2020", 280).at(-140, 0, 10))
asm.add(panel(280, 200, t=3, r=4, holes=[[0, 0, "M5"]]).at(0, 0, 20))
export_dxf(asm, "out/top.dxf", kerf=0.2)
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
git clone https://github.com/<あなたのユーザー名>/alucad.git
cd alucad
```

### 3. 依存パッケージを入れる

```bash
uv sync
```
Python 本体も含めて、`.venv/` フォルダに全部入る（PCの他の環境は汚さない）。初回は数分かかる。

### 4. VS Code の準備

1. VS Code で `alucad` フォルダを開く
2. 拡張機能（左の四角いアイコン）で **「OCP CAD Viewer」**（作者 bernhard-42）をインストール
3. 拡張機能 **「Python」**（Microsoft）も入っていなければインストール
4. コマンドパレット（macOS: `Cmd+Shift+P` / Windows: `Ctrl+Shift+P`）→ **「Python: Select Interpreter」** → `./.venv/bin/python`（Windows は `.\.venv\Scripts\python.exe`）を選ぶ
5. 左のサイドバーに出る OCP CAD Viewer のアイコンからビューアを開く（コマンドパレットで「OCP CAD Viewer: Open viewer」でも可）

---

## 使い方

### サンプルを動かす

ビューアを開いた状態で:
```bash
uv run python examples/p1_panel.py    # 穴あき板1枚 → DXF
uv run python examples/p1_stand.py    # 2020フレームの小さな台 → JSON + 天板DXF
```
- 3Dがビューアに表示される
- `examples/out/` に DXF / JSON が出る

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

### Beam Studio に読み込む

1. Beam Studio で「ファイル → 開く」（またはドラッグ＆ドロップ）で `examples/out/*.dxf` を開く
2. 単位を聞かれたら **mm**
3. レイヤーが `cut` / `engrave` / `score` に分かれていることを確認し、レイヤーごとに加工方法を設定する

---

## 主なAPI

| 関数 | 内容 |
|---|---|
| `frame(profile="2020", length=400, axis="x")` | フレーム。原点は片側の端面中心、そこから `axis` の＋方向へ伸びる |
| `panel(w, h, t=3, r=0, holes=[], engrave=[], score=[])` | 板。原点は板の中心（下面）。`holes=[[x, y, "M4"], ...]` |
| `hole_grid(w, h, size="M5", inset=10, nx=2, ny=2)` | 板の縁から inset の位置に等間隔の穴リスト |
| `.at(x, y, z)` / `.rot(x, y, z)` | 位置・回転（度、XYZ順＝three.js の Euler 'XYZ' と同じ） |
| `Assembly(name)` / `.add(part, name=)` / `.save(path)` / `Assembly.load(path)` | アセンブリとJSON |
| `export_dxf(parts, path, kerf=0.2, compensate=True, gap=5)` | DXF書き出し（加工エリア 300×210 を超えると警告） |
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
- [ ] Phase 2: 材料設定、ブラケット、フレームからの穴位置自動計算、STEP
- [ ] Phase 3: フィンガージョイント、ネスティング
- [ ] Phase 4: Web GUI（JSON を編集する）
