# parts/ — 自作部品

ここに置いた `.py` ファイルの部品は、自動で alucad に登録されます。
ほかのデザインでも使い回す部品だけを置きます（1つの用途のための形は `projects/` へ）。
GUI のパレット、デザインの JSON、書き出し（DXF / STL / STEP）、部品表、加工前チェックがそのまま使えます。

- 新しく作るときは `_template.py` をコピーする（`_` で始まるファイルは読み込まれません）
- GUI を開いたままファイルを保存すると、1秒ほどで自動的に読み込み直されます
- 書き方の決まりは、リポジトリ直下の `CLAUDE.md` の「部品を作る」を参照

| ファイル | 部品 |
|---|---|
| `frame_foot.py` | フレームの足（3Dプリント）。お手本 |
| `hex_nut.py` | 六角ナット（買う部品） |
| `shaft.py` | 丸棒シャフト（買う部品） |
| `misumi_bracket.py` | ミスミのブラケット（買う部品）。HBLFSN5（2020用）・HBLFSN6-5（3030用）・HBLFSN8（40mm用）。STEP は `vendor/<型番>.stp` に置く |

## メーカーの STEP を使う部品（`vendor/`）

ミスミなどからダウンロードした CAD データは `parts/vendor/` に置きます。メーカーのデータは再配布できないので、
このフォルダは git に入りません。
Google Drive に置いて `parts/vendor` をそこへのリンクにしておくと、どの Mac でも同じ STEP を使えます:

```bash
ln -s "$HOME/Library/CloudStorage/GoogleDrive-<アカウント>/マイドライブ/cad-data/vendor" parts/vendor
```

型番を増やすときは、STEP を置いてから
`misumi_bracket.py` の `MODELS` に向きと穴の位置を1行足します。
