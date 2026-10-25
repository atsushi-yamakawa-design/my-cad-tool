"""コマンドライン: JSON（アセンブリ）から全部書き出す。

  uv run alucad build designs/stand.json            → designs/out/ に DXF・STL・STEP・GLB・部品表
  uv run alucad build designs/stand.json -o dist    → 出力先を指定
  uv run alucad build designs/stand.json --only dxf,bom
  uv run alucad check designs/stand.json            → 加工前チェックだけ
  uv run alucad bom designs/stand.json              → 部品表を画面に表示
  uv run alucad preview designs/stand.json          → 4方向のプレビュー画像（PNG）
  uv run alucad part frame_foot --set depth=12 --png foot.png --stl foot.stl
                                                    → 部品を1つだけ作って確認・書き出し
  uv run alucad catalog                             → 使えるコンポーネントの一覧（GUI用のJSON）
  uv run alucad gui                                 → GUIエディタをブラウザで開く

将来のGUIは、JSONを編集してこの build と同じ処理を呼ぶ。
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

FORMATS = ("dxf", "stl", "step", "glb", "bom", "png")


def build(json_path: str | Path, out_dir: str | Path | None = None, only=FORMATS,
          compensate: bool = True, gap: float = 3.0) -> list[Path]:
    """JSONを読み込んで、指定した形式のファイルを書き出す。書き出したパスのリストを返す。"""
    from . import Assembly, export_glb, export_prints, export_sheets, export_step
    from .bom import export_bom

    json_path = Path(json_path)
    asm = Assembly.load(json_path)
    out = Path(out_dir) if out_dir else json_path.parent / "out"
    paths: list[Path] = []
    if "dxf" in only and asm.flat_parts():
        paths += export_sheets(asm, out, compensate=compensate, gap=gap)
    if "stl" in only and any(p.is_print for p in asm.expanded()):
        paths += export_prints(asm, out)
    if "step" in only:
        paths.append(export_step(asm, out / f"{asm.name}.step"))
    if "glb" in only:
        paths.append(export_glb(asm, out / f"{asm.name}.glb"))
    if "png" in only:
        from .preview import render

        paths.append(render(asm, out / f"{asm.name}_preview.png", asm.name))
    if "bom" in only:
        paths.append(export_bom(asm, out / f"{asm.name}_bom.md"))
        paths.append(export_bom(asm, out / f"{asm.name}_bom.csv"))
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="alucad", description="アルミフレーム＋レーザーカット板のコードCAD")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="JSONから DXF / STL / STEP / GLB / 部品表 を書き出す")
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

    pv = sub.add_parser("preview", help="デザインの4方向プレビューをPNGで書き出す")
    pv.add_argument("json", help="アセンブリのJSONファイル")
    pv.add_argument("-o", "--out", help="出力するPNG（省略時は out/<名前>_preview.png）")

    pt = sub.add_parser("part", help="部品を1つだけ作って、寸法・接続点を表示／書き出す")
    pt.add_argument("type", help="部品の種類（catalog の name）")
    pt.add_argument("--set", action="append", default=[], metavar="名前=値", help="パラメータ（何回でも指定できる）")
    pt.add_argument("--params", help='パラメータをJSONでまとめて指定（例: \'{"w": 40}\'）')
    pt.add_argument("--png", help="プレビュー画像の出力先")
    pt.add_argument("--stl", help="STLの出力先")
    pt.add_argument("--step", help="STEPの出力先")
    pt.add_argument("--dxf", help="DXFの出力先（板パーツのみ）")

    g = sub.add_parser("gui", help="GUIエディタを起動してブラウザで開く")
    g.add_argument("--port", type=int, default=8000, help="ポート番号（既定 8000）")
    g.add_argument("--designs", help="デザインJSONのフォルダ（既定はリポジトリの designs/）")
    g.add_argument("--no-browser", action="store_true", help="ブラウザを自動で開かない")

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
    elif args.cmd == "preview":
        from . import Assembly
        from .preview import render

        asm = Assembly.load(args.json)
        out = Path(args.out) if args.out else Path(args.json).parent / "out" / f"{asm.name}_preview.png"
        print("書き出し:", render(asm, out, asm.name))
    elif args.cmd == "part":
        return _part(args)
    elif args.cmd == "gui":
        return _run_gui(args.port, args.designs, not args.no_browser)
    elif args.cmd == "catalog":
        from . import catalog

        print(json.dumps(catalog(), ensure_ascii=False, indent=2))
    return 0


def _run_gui(port: int, designs: str | None, open_browser: bool) -> int:
    import threading
    import webbrowser

    import uvicorn

    from .gui.server import create_app

    for p in range(port, port + 20):
        state = _port_state(p)
        if state == "alucad":  # もう GUI が動いている → それを開くだけ
            url = f"http://127.0.0.1:{p}"
            print(f"GUIエディタはすでに起動しています: {url}")
            print("（止めたいときは、起動したターミナルで Ctrl+C）")
            if open_browser:
                webbrowser.open(url)
            return 0
        if state == "free":
            if p != port:
                print(f"ポート {port} はほかのアプリが使っているので、{p} で起動します")
            port = p
            break
    else:
        print(f"ポート {port}〜{port + 19} がすべて使用中です。--port で別の番号を指定してください", file=sys.stderr)
        return 1

    url = f"http://127.0.0.1:{port}"
    print(f"GUIエディタ: {url}  （終了は Ctrl+C）")
    if open_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    uvicorn.run(create_app(Path(designs) if designs else None), host="127.0.0.1", port=port, log_level="warning")
    return 0


def _port_state(port: int) -> str:
    """"free"（空き）/ "alucad"（alucad の GUI が動いている）/ "busy"（ほかのアプリ）"""
    import socket
    import urllib.request

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", port)) != 0:
            return "free"
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/watch", timeout=1) as r:
            return "alucad" if b'"parts"' in r.read() else "busy"
    except Exception:
        return "busy"


def _part(args) -> int:
    from . import export_dxf, export_step, make
    from .preview import render

    params = json.loads(args.params) if args.params else {}
    for kv in args.set:
        key, _, raw = kv.partition("=")
        try:
            params[key] = json.loads(raw)  # 数値・true/false・リストはそのまま
        except json.JSONDecodeError:
            params[key] = raw  # それ以外は文字列（"M5" など）
    try:
        p = make(args.type, **params)
    except (ValueError, TypeError, KeyError) as e:
        print("エラー:", e.args[0] if isinstance(e, KeyError) and e.args else e, file=sys.stderr)
        return 1

    bb = p.solid().bounding_box()
    print(f"部品: {args.type}")
    print("パラメータ:", json.dumps(p.params, ensure_ascii=False))
    print(f"外形: X {bb.min.X:g}〜{bb.max.X:g} / Y {bb.min.Y:g}〜{bb.max.Y:g} / Z {bb.min.Z:g}〜{bb.max.Z:g} mm"
          f"（{bb.size.X:g} × {bb.size.Y:g} × {bb.size.Z:g}）")
    print(f"体積: {p.solid().volume:.1f} mm³")
    for a in p.anchors():
        print(f"接続点: {a.name:10s} {a.kind:5s} pos={a.pos} normal={a.normal}")
    if args.png:
        print("書き出し:", render(p, args.png, args.type))
    if args.stl:
        from build123d import export_stl

        Path(args.stl).parent.mkdir(parents=True, exist_ok=True)
        export_stl(p.geometry.solid, args.stl, tolerance=0.01, angular_tolerance=0.2)
        print("書き出し:", args.stl)
    if args.step:
        print("書き出し:", export_step(p, args.step))
    if args.dxf:
        if not p.is_flat:
            print("エラー: DXF にできるのは板パーツだけです", file=sys.stderr)
            return 1
        print("書き出し:", export_dxf(p, args.dxf))
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
