# CLAUDE.md — alucad（my-cad-tool）で作業する Claude へ

アルミフレーム（2020/3030）＋レーザーカット板＋3Dプリント部品の設計ツール。持ち主は UI デザイナーで、
Python は読める程度。**チャットで頼まれた設計を、デザインJSONと自作部品で実現する**のがあなたの主な仕事。
返事は日本語で、専門用語には短い説明を添える。

## まず知っておくこと

- **これまでの経緯・決めたこと・次にやることは `docs/HANDOFF.md`**。新しい会話の最初に読む

- 単位はすべて **mm**、座標は **Z が上**（build123d と同じ）。回転は XYZ オイラー角（度、Intrinsic XYZ ＝ three.js の 'XYZ'）
- 持ち主はたいてい **GUI（`uv run alucad gui`）をブラウザで開いたまま**会話している。
  `designs/*.json` と `parts/*.py` を保存すると、GUI は1秒ほどで自動的に読み込み直す。
  GUI 側に未保存の変更があるときは、画面に「外部で変更されました」と確認が出る
- レーザーは FLUX beamo（加工エリア 300×210mm）。材料・カーフ・フィラメントは `materials.toml`
- コマンドは必ず `uv run` を付けて実行する（`uv run alucad ...`, `uv run pytest`）

## 頼まれごと別のやり方

### 1. デザインに部品を足す・動かす・寸法を変える → `designs/<名前>.json` を編集
```json
{
  "version": 1, "units": "mm", "up": "Z", "name": "stand",
  "parts": [
    {"id": "stand", "type": "frame_stand", "params": {"w": 280, "d": 200, "h": 150}, "pos": [0, 0, 0], "rot": [0, 0, 0]},
    {"id": "foot1", "type": "frame_foot", "params": {}, "pos": [-130, -90, -4], "rot": [0, 0, 0]}
  ]
}
```
- `type` と `params` の名前・型・範囲は **`uv run alucad catalog`** で確認する（推測しない）。
  `params` は省略したものがデフォルトになる
- `id` は重複させない。「/」は使わない
- 形状（頂点など）を JSON に書かない。JSON は「種類＋パラメータ＋位置・回転」だけ
- 位置は部品の **原点** の位置。原点がどこかは部品ごとに違う（下の「部品の原点」）。
  迷ったら `uv run alucad part <type>` で外形と接続点を確認してから置く
- **グループ**（`"type": "group"`）は部品をまとめたもの。中身は `params.children` にそのまま書き、中身の pos / rot はグループの中での値。
  入れ子にできる。部品表・書き出し・チェックでは中身に展開され、名前は `"グループid/中身id"`（例: `rollers/roller_l`）。
  中身の id はグループの中で重複させない。GUI では ⌘G でまとめる、⌘⇧G で解除、キットは「グループに変換」でグループになる
  ```json
  {"id": "rollers", "type": "group", "params": {"children": [
    {"id": "roller_l", "type": "sea_roller", "params": {}, "pos": [-107, 0, 23], "rot": [0, 0, 0]}
  ]}, "pos": [0, 0, 0], "rot": [0, 0, 0]}
  ```
- グループを部品として登録したものは `parts/<名前>.json`（`{"label": "日本語名", "children": [...]}`）。パラメータなしの部品としてパレットの「グループ」に出る
- 画面の「隠す」は表示だけで JSON には入らない（ブラウザに覚える）。書き出しや部品表には含まれる
- キット（`frame_stand`, `finger_box`）の中身は自動計算。中身だけ変えたいときは、
  キットのパラメータで足りるか先に考え、無理なら持ち主に「分解してよいか」聞く

### 2. 新しい形を作る → まず「プロジェクト」か「部品」かを決める
- **何かを作ってと頼まれたら、基本は `projects/<名前>.py`（プロジェクト）に作る。** 1つの用途のための形（例: 靴べら立て）。
  JSON・GUI のプロパティ・書き出しでは普通に使えるが、**GUI のパレット（コンポーネント集）には出ない**。1プロジェクト＝1ファイル
- **`parts/<名前>.py`（部品＝コンポーネント集に登録）にするのは、持ち主が「登録して」と言ったときだけ。**
  ナット・足・ブラケットのように、ほかのデザインでも使い回せそうなものは、作ったあとに「部品として登録しようか？」と**提案**する（勝手に登録しない）
- 書き方はどちらも同じ。`parts/_template.py` をコピーして書き換える。お手本は `parts/frame_foot.py`
- `@component("名前", label="日本語名", category=..., params=[Param(...), ...])` を付けた関数が部品になる
  - **関数の引数と params を同じ名前・同じ順番に**（違うと登録時にエラー）
  - Param には `label`（日本語）, `unit`, `min`, `max`, `choices` をできるだけ付ける（GUI の入力欄になる）
  - パラメータは JSON にできる値だけ（float, int, str, bool, list）
  - 寸法が成り立たないときは `ValueError("部品名: 〜してください")` を日本語で投げる
- category ごとの決まり
  - `print`（3Dプリント）: **z=0 の面がプリンタのベッドに乗る面**。オーバーハングが少ない向きで作る。
    `from alucad.printed import FILAMENT, SIZE` の FILAMENT を params に入れる。
    はめあい部分には `clearance`（片側 0.2〜0.3mm）を付ける（3Dプリントは穴が小さめに出る）
  - `plate`（レーザーで切る板）: 外形の Sketch を作り `alucad.flat.flat_geometry(outline, mat, holes)` で Geometry にする。
    `flat.MAT` を params に入れる。板厚は材料で決まる
- 取り付け穴は `Anchor("hole0", pos, normal, "hole")` を付ける。**pos はボルトの頭側の面上の点、normal は相手（フレーム）から離れる向き**。
  厚みを `t` パラメータで持っていれば、部品表がTナット／タップ／ナットとボルト長さを自動で数える
- 使える穴径: `from alucad.holes import hole_dia` → `hole_dia("M5")` = 5.5（JIS 2級）
- build123d は **algebra mode**（`Box(...) - Cylinder(...)`, `Pos(x,y,z) * shape`）で書く。builder mode（`with BuildPart()`）は使わない。
  API は版で変わるので、知らない関数は推測せず `.venv/lib/python3.12/site-packages/build123d/` を確認する

### 3. 部品を単体で書き出す（デザインに入れない）
```bash
uv run alucad part frame_foot --set depth=12 --set size=M4 --png out/foot.png --stl out/foot.stl
```
`--set 名前=値` は何回でも。`--params '{"w": 40}'` でまとめて指定もできる。`--step`, `--dxf`（板のみ）も使える。

### 4. デザイン全体を書き出す
```bash
uv run alucad build designs/stand.json        # DXF・STL・STEP・GLB・部品表・プレビュー（書き出し先は下のルール）
uv run alucad build designs/stand.json --only stl,png
```
書き出し先は、リポジトリ直下の `alucad.local.toml`（git に入れない）の `[out_dirs]` にデザイン名があればそのフォルダ、なければ `designs/out/`。
build は最初に加工前チェックをして、エラーがあれば止まる（`--force` で無視）。

### 書き出し先のルール（持ち主が人の手で使うファイル）
- **プリント・カットするもの、持ち主が開いていじるもの**（DXF・STL・STEP・部品表など）は、持ち主の Google Drive の
  **「プロト・実験」フォルダの中のプロジェクトのフォルダ**（例: `2026_sea`）か、持ち主が指定したフォルダに書き出す
- **Drive の `cad-data` には書き出さない。** cad-data は AI やソフトが読みに行く場所（メーカーの STEP の `cad-data/vendor/` など）
- デザインの build は `alucad.local.toml` の `[out_dirs]` で決まる。部品単体（`alucad part`）やテストの書き出しは `--stl` / `--out` などでそのフォルダを指定する
- **書き出し先のフォルダがまだないときは、勝手に決めない。** 「プロト・実験に `2026_<名前>` を作ってよいか」を持ち主に確認してから作り、
  デザインなら `[out_dirs]` に足す（ほかの場所がよければそれに従う）
- Drive のパスはメールアドレスを含むので、`alucad.local.toml` 以外（コードやドキュメント）には書かない

## 作ったら必ず確認する（この順で）

1. `uv run alucad part <type> --png out/<type>.png` か `uv run alucad preview designs/<名前>.json` で **PNG を書き出して自分で見る**。
   4方向（iso / front / top / right）と外形寸法が描かれる。意図した形・向き・大きさか確かめる
2. `uv run alucad check designs/<名前>.json` で加工前チェック（めり込み・加工エリア・穴と縁の距離・細い部分）
3. 自作部品やプロジェクトを足したら `uv run pytest -q` が通ることを確認する（`tests/test_parts_folder.py` が parts/ と projects/ の全部をデフォルト値で作ってみる）
4. 持ち主には「何を作ったか・どこを見ればいいか（GUI で選ぶ部品の id など）」を短く伝える

## 部品の原点（よく使うもの）

| type | 原点 | 向き |
|---|---|---|
| frame | 片側の端面の中心 | `axis` の＋方向へ `length` 伸びる |
| panel | 板の中心・下面 | 上面は z=板厚 |
| l_bracket / corner_bracket | 外側の角・下面 | 腕は +X と +Y |
| box_face | 板の中心・下面 | |
| frame_stand | 床面の中心 | 天板の下面が z=h |
| finger_box | 底面の中心 | 外寸 w×d×h |
| angle_bracket | 外側の角 | 腕は +X（床側）と +Z（壁側）、幅は Y に中心振り分け |
| spacer / frame_foot | 底面の中心 | z=0 がベッド側 |

## やらないこと

- `src/alucad/` 本体は、頼まれない限り変えない（部品は `parts/` に作る）。本体を変えたら `uv run pytest` を通す
- `src/alucad/gui/static/` は手で編集しない（`gui/` のソースから `npm run build` で作る）
- `designs/out/`, `examples/out/` は出力置き場。コミットしない
- 持ち主が GUI で編集中かもしれないので、`designs/*.json` を書き換える前に「変更してよいか」が会話から明らかでなければ一言確認する
