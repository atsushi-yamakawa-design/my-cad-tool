"""材料設定（materials.toml）の読み込み。

探す場所:
  1. 環境変数 ALUCAD_MATERIALS に書いたパス
  2. リポジトリ直下の materials.toml
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Material:
    key: str
    label: str
    t: float  # 板厚
    kerf: float  # 切断幅
    color: str = "burlywood"  # 3D表示の色


def _path() -> Path:
    env = os.environ.get("ALUCAD_MATERIALS")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "materials.toml"


def _load() -> tuple[dict[str, Material], dict]:
    path = _path()
    if not path.exists():
        raise FileNotFoundError(f"材料設定ファイルが見つかりません: {path}")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    mats = {
        key: Material(
            key, v.get("label", key), float(v["t"]), float(v["kerf"]), v.get("color", "burlywood")
        )
        for key, v in data.get("materials", {}).items()
    }
    if not mats:
        raise ValueError(f"{path}: [materials.xxx] が1つもありません")
    return mats, data.get("machine", {})


MATERIALS, MACHINE = _load()
BED: tuple[float, float] = tuple(MACHINE.get("bed", (300.0, 210.0)))


def get(key: str) -> Material:
    if key not in MATERIALS:
        raise KeyError(f"未登録の材料: {key!r}（materials.toml にあるもの: {sorted(MATERIALS)}）")
    return MATERIALS[key]
