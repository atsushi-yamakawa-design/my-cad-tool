"""コマンドライン: JSON（アセンブリ）から全部書き出す。

  uv run alucad build designs/stand.json            → designs/out/ に DXF・STEP・GLB・部品表
  uv run alucad build designs/stand.json -o dist    → 出力先を指定
  uv run alucad build designs/stand.json --only dxf,bom
  uv run alucad check designs/stand.json            → 加工前チェックだけ
  uv run alucad bom designs/stand.json              → 部品表を画面に表示
  uv run alucad catalog                             → 使えるコンポーネントの一覧（GUI用のJSON）

将来のGUIは、JSONを編集してこの build と同じ処理を呼ぶ。
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

FORMATS = ("dxf", "step", "glb", "bom")


def build(json_path: str | Path, out_dir: str | Path | None = None, only=FORMATS,
          compensate: bool = True, gap: float = 3.0) -> list[Path]:
    """JSONを読み込んで、指定した形式のファイルを書き出す。書き出したパスのリストを返す。"""
    from . import Assembly, export_glb, export_sheets, export_step
    from .bom import export_bom

    json_path = Path(json_path)
    asm = Assembly.load(json_path)
    out = Path(out_dir) if out_dir else json_path.parent / "out"
    paths: list[Path] = []
    if "dxf" in only and asm.flat_parts():
        paths += export_sheets(asm, out, compensate=compensate, gap=gap)
    if "step" in only:
        paths.append(export_step(asm, out / f"{asm.name}.step"))
    if "glb" in only:
        paths.append(export_glb(asm, out / f"{asm.name}.glb"))
    if "bom" in only:
        paths.append(export_bom(asm, out / f"{asm.name}_bom.md"))
        paths.append(export_bom(asm, out / f"{asm.name}_bom.csv"))
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="alucad", description="アルミフレーム＋レーザーカット板のコードCAD")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="JSONから DXF / STEP / GLB / 部品表 を書き出す")
    b.add_argument("json", help="アセンブリのJSONファイル")
    b.add_argument("-o", "--out", help="出力フォルダ（省略時は JSON と同じ場所の out/）")
    b.add_argument("--only", default=",".join(FORMATS), help=f"書き出す形式（カンマ区切り。{','.join(FORMATS)}）")
    b.add_argument("--no-kerf", action="store_true", help="カーフ補正をしない（設計寸法のまま）")
    b.add_argument("--gap", type=float, default=3.0, help="DXFでパーツ同士を空ける間隔 mm（既定 3）")
    b.add_argument("--force", action="store_true", help="チェックでエラーがあっても書き出す")

    c = sub.add_parser("check", help="加工前チェック（加工エリア・穴と縁の間隔・細い部分・めり込み）")
    c.add_argument("json", help="アセンブリのJSONファイル")

    m = sub.add_parser("bom", help="部品表を表示する")
    m.add_argument("json", help="アセンブリのJSONファイル")
    m.add_argument("--csv", action="store_true", help="CSV形式で表示")

    sub.add_parser("catalog", help="使えるコンポーネントとパラメータの一覧をJSONで表示")

    args = ap.parse_args(argv)

    if args.cmd == "build":
        only = [x.strip() for x in args.only.split(",") if x.strip()]
        bad = set(only) - set(FORMATS)
        if bad:
            ap.error(f"--only に使えない形式: {sorted(bad)}")
        if not _report_check(args.json) and not args.force:
            print("エラーがあるので書き出しを中止しました（それでも書き出すなら --force）", file=sys.stderr)
            return 1
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            paths = build(args.json, args.out, only, compensate=not args.no_kerf, gap=args.gap)
        for p in paths:
            print("書き出し:", p)
        for w in caught:
            print("注意:", w.message, file=sys.stderr)
    elif args.cmd == "check":
        return 0 if _report_check(args.json) else 1
    elif args.cmd == "bom":
        from . import Assembly
        from .bom import bom

        b_ = bom(Assembly.load(args.json))
        print(b_.to_csv() if args.csv else b_.to_markdown())
    elif args.cmd == "catalog":
        from . import catalog

        print(json.dumps(catalog(), ensure_ascii=False, indent=2))
    return 0


def _report_check(json_path) -> bool:
    """チェック結果を表示する。エラーがなければ True。"""
    from . import Assembly
    from .check import check

    issues = check(Assembly.load(json_path))
    for i in issues:
        print(i, file=sys.stderr if i.level == "error" else sys.stdout)
    errors = sum(i.level == "error" for i in issues)
    warns = len(issues) - errors
    print(f"チェック: エラー {errors} 件 / 注意 {warns} 件" if issues else "チェック: 問題なし")
    return errors == 0


if __name__ == "__main__":
    sys.exit(main())
