"""parts/ と projects/ の自作部品を読み込む。

parts/    … いろいろなデザインで使い回す部品。GUI のパレット（コンポーネント集）に出る
projects/ … 1つの用途のための形（例: 靴べら立て）。1プロジェクト＝1ファイル（projects/<名前>.py）。
             JSON・GUI のプロパティ・書き出しでは普通の部品と同じに使えるが、パレットには出さない

どちらも alucad を import したときに自動で読み込まれ、中で @component を付けた関数が登録される。
parts/<名前>.json は、部品の組み合わせ（グループ）をそのまま1つの部品にしたもの（alucad.group を参照）。
ファイルを書き換えたら load() を呼び直すだけで登録し直される（GUIは自動で呼ぶ）。
「_」で始まるファイルは読み込まない。

探す場所: 環境変数 ALUCAD_PARTS / ALUCAD_PROJECTS、なければリポジトリ直下の parts/ と projects/
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import traceback
import warnings
from pathlib import Path

from . import registry

_state: dict = {"stamp": None, "errors": {}}


def parts_dir() -> Path:
    env = os.environ.get("ALUCAD_PARTS")
    return Path(env) if env else Path(__file__).resolve().parents[2] / "parts"


def projects_dir() -> Path:
    env = os.environ.get("ALUCAD_PROJECTS")
    return Path(env) if env else Path(__file__).resolve().parents[2] / "projects"


def _files() -> list[tuple[Path, str, str]]:
    """読み込むファイル。(パス, エラー表示用の名前, プロジェクト名) のリスト。"""
    out = []
    for d, folder, is_project in ((parts_dir(), "parts", False), (projects_dir(), "projects", True)):
        if d.is_dir():
            for f in sorted([*d.glob("*.py"), *(d.glob("*.json") if not is_project else [])]):
                if not f.name.startswith("_"):
                    out.append((f, f"{folder}/{f.name}", f.stem if is_project else ""))
    return out


def _stamp() -> tuple:
    return tuple((key, f.stat().st_mtime_ns, f.stat().st_size) for f, key, _ in _files())


def stamp() -> str:
    """parts/ と projects/ の中身が変わると変わる文字列（GUIの変更検知用）。"""
    return hashlib.sha1(repr(_stamp()).encode()).hexdigest()[:12]


def errors() -> dict[str, str]:
    """読み込みに失敗したファイル（"parts/x.py" など）とエラーメッセージ。"""
    return dict(_state["errors"])


def load(force: bool = False) -> bool:
    """parts/ と projects/ を読み込む（前回から変わっていなければ何もしない）。読み込み直したら True。"""
    st = _stamp()
    if st == _state["stamp"] and not force:
        return False

    # 前回 parts/ と projects/ から登録した部品をいったん消す（消したファイルの部品も消えるように）
    for name in [n for n, c in registry.REGISTRY.items() if c.source]:
        del registry.REGISTRY[name]
    registry._cache.clear()

    errs = {}
    # .json（グループ）は中身に .py の部品を使うので、.py を全部読んでから
    for f, key, project in sorted(_files(), key=lambda t: t[0].suffix == ".json"):
        if f.suffix == ".json":
            try:
                _load_group(f)
            except Exception as e:
                errs[key] = "".join(traceback.format_exception_only(type(e), e)).strip()
            continue
        mod_name = f"alucad_{'projects' if project else 'parts'}.{f.stem}"
        registry._current_source = str(f)
        registry._current_project = project
        try:
            spec = importlib.util.spec_from_file_location(mod_name, f)
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
        except Exception as e:  # 1ファイルの間違いで全体を止めない
            errs[key] = "".join(traceback.format_exception_only(type(e), e)).strip()
            for name in [n for n, c in registry.REGISTRY.items() if c.source == str(f)]:
                del registry.REGISTRY[name]
        finally:
            registry._current_source = ""
            registry._current_project = ""

    _state.update(stamp=st, errors=errs)
    for name, msg in errs.items():
        warnings.warn(f"{name} を読み込めませんでした: {msg}", stacklevel=2)
    return True


def _load_group(f: Path) -> None:
    """parts/<名前>.json（グループを登録したもの）を、パラメータなしの部品として登録する。"""
    from .group import GROUP, build_group, group_parts

    data = json.loads(f.read_text(encoding="utf-8"))
    children = data.get("children")
    if not isinstance(children, list) or not children:
        raise ValueError("children（中身の部品のリスト）がありません")
    name = f.stem
    if name in registry.REGISTRY:
        raise ValueError(f"部品名 {name!r} はすでに使われています（{registry.REGISTRY[name].source or 'alucad 本体'}）")
    group_parts(children, name)  # 書き方の間違いは読み込むときに知らせる
    registry.REGISTRY[name] = registry.ComponentDef(
        name,
        data.get("label") or name,
        GROUP,
        [],
        lambda: build_group(children),
        str(f),
        data.get("description", ""),
    )
