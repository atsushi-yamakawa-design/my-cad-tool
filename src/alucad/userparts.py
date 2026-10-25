"""parts/ フォルダの自作部品を読み込む。

parts/ に置いた .py ファイルは、alucad を import したときに自動で読み込まれ、
中で @component を付けた関数が部品として登録される（パレット・JSON・書き出し・部品表で使える）。
ファイルを書き換えたら load() を呼び直すだけで登録し直される（GUIは自動で呼ぶ）。
「_」で始まるファイルは読み込まない。

探す場所: 環境変数 ALUCAD_PARTS、なければリポジトリ直下の parts/
"""

from __future__ import annotations

import hashlib
import importlib.util
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


def _files() -> list[Path]:
    d = parts_dir()
    return sorted(f for f in d.glob("*.py") if not f.name.startswith("_")) if d.is_dir() else []


def _stamp() -> tuple:
    return tuple((f.name, f.stat().st_mtime_ns, f.stat().st_size) for f in _files())


def stamp() -> str:
    """parts/ の中身が変わると変わる文字列（GUIの変更検知用）。"""
    return hashlib.sha1(repr(_stamp()).encode()).hexdigest()[:12]


def errors() -> dict[str, str]:
    """読み込みに失敗したファイルとエラーメッセージ。"""
    return dict(_state["errors"])


def load(force: bool = False) -> bool:
    """parts/ を読み込む（前回から変わっていなければ何もしない）。読み込み直したら True。"""
    st = _stamp()
    if st == _state["stamp"] and not force:
        return False

    # 前回 parts/ から登録した部品をいったん消す（消したファイルの部品も消えるように）
    for name in [n for n, c in registry.REGISTRY.items() if c.source]:
        del registry.REGISTRY[name]
    registry._cache.clear()

    errs = {}
    for f in _files():
        mod_name = f"alucad_parts.{f.stem}"
        registry._current_source = str(f)
        try:
            spec = importlib.util.spec_from_file_location(mod_name, f)
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
        except Exception as e:  # 1ファイルの間違いで全体を止めない
            errs[f.name] = "".join(traceback.format_exception_only(type(e), e)).strip()
            for name in [n for n, c in registry.REGISTRY.items() if c.source == str(f)]:
                del registry.REGISTRY[name]
        finally:
            registry._current_source = ""

    _state.update(stamp=st, errors=errs)
    for name, msg in errs.items():
        warnings.warn(f"parts/{name} を読み込めませんでした: {msg}", stacklevel=2)
    return True
