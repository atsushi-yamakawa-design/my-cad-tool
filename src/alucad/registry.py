"""コンポーネント登録の仕組み。

各コンポーネント（frame, panel, ...）は「形状を作る関数」＋「メタデータ」で登録する。
メタデータ（引数名・型・単位・デフォルト・範囲）は、将来GUIのパーツパレットや
プロパティパネルを自動生成するのに使う。
"""

from __future__ import annotations

import inspect
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from build123d import Compound, Shape, Sketch


@dataclass(frozen=True)
class Param:
    """コンポーネントの引数1つ分のメタデータ。"""

    name: str
    type: type
    default: Any
    unit: str = "mm"
    min: float | None = None
    max: float | None = None
    choices: tuple | None = None
    label: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.__name__
        if self.choices is not None:
            d["choices"] = list(self.choices)
        return d


@dataclass(frozen=True)
class Anchor:
    """接続点（取り付け面・穴・端面）。座標はコンポーネントのローカル座標。"""

    name: str
    pos: tuple[float, float, float]
    normal: tuple[float, float, float]
    kind: str  # "end" | "face" | "hole" | "slot"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Geometry:
    """コンポーネントが生成する形状一式（ローカル座標）。

    - solid:  3D形状（確認・STEP用）
    - layers: 板パーツの2Dスケッチ。{"cut": ..., "engrave": ..., "score": ...}
              板パーツではこちらが「正」で、solid はこれを押し出しただけ。
    """

    solid: Shape
    layers: dict[str, Sketch | Shape] = field(default_factory=dict)
    anchors: list[Anchor] = field(default_factory=list)
    children: list = field(default_factory=list)  # キット（複合コンポーネント）の中身の Part

    @classmethod
    def kit(cls, children: list, anchors: list[Anchor] | None = None) -> Geometry:
        """中身の Part（キットのローカル座標で配置済み）からキットの形状を作る。"""
        return cls(
            solid=Compound([c.solid() for c in children]),
            anchors=anchors or [],
            children=children,
        )


@dataclass
class ComponentDef:
    name: str
    label: str
    category: str
    params: list[Param]
    build: Callable[..., Geometry]
    source: str = ""  # parts/ フォルダの部品なら、そのファイルのパス
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "category": self.category,
            "description": self.description,
            "user": bool(self.source),
            "params": [p.to_dict() for p in self.params],
        }


REGISTRY: dict[str, ComponentDef] = {}
_current_source = ""  # parts/ を読み込み中のファイル（userparts が設定する）


def component(name: str, *, label: str, category: str, params: list[Param]):
    """形状生成関数をコンポーネントとして登録するデコレータ。

    デコレートした関数そのものはそのまま返す（形状生成関数として残す）。
    ユーザーが使う frame() / panel() は、各モジュールで make() を呼ぶ薄い関数として書く。
    """

    def deco(fn: Callable[..., Geometry]):
        sig_names = list(inspect.signature(fn).parameters)
        meta_names = [p.name for p in params]
        if sig_names != meta_names:
            raise TypeError(
                f"{name}: 関数の引数 {sig_names} と Param 定義 {meta_names} が一致しません"
            )
        if name in REGISTRY and REGISTRY[name].source != _current_source:
            raise ValueError(f"部品名 {name!r} はすでに使われています（{REGISTRY[name].source or 'alucad 本体'}）")
        doc = inspect.getdoc(fn) or ""
        REGISTRY[name] = ComponentDef(name, label, category, params, fn, _current_source, doc)
        return fn

    return deco


def get(name: str) -> ComponentDef:
    if name not in REGISTRY:
        raise KeyError(f"未登録のコンポーネント: {name!r}（登録済み: {sorted(REGISTRY)}）")
    return REGISTRY[name]


def validate(name: str, params: dict) -> dict:
    """デフォルト値を補い、型・範囲・選択肢をチェックした params を返す。"""
    cdef = get(name)
    known = {p.name for p in cdef.params}
    unknown = set(params) - known
    if unknown:
        raise TypeError(f"{name}: 不明な引数 {sorted(unknown)}（使える引数: {sorted(known)}）")

    out = {}
    for p in cdef.params:
        v = params.get(p.name, p.default)
        if p.type is float and isinstance(v, int) and not isinstance(v, bool):
            v = float(v)
        if p.type is list and isinstance(v, tuple):
            v = list(v)
        if not isinstance(v, p.type):
            raise TypeError(f"{name}.{p.name}: {p.type.__name__} が必要です（値: {v!r}）")
        if p.choices is not None and v not in p.choices:
            raise ValueError(f"{name}.{p.name}: {list(p.choices)} のどれかを指定してください（値: {v!r}）")
        if p.min is not None and v < p.min:
            raise ValueError(f"{name}.{p.name}: {p.min}{p.unit} 以上にしてください（値: {v}）")
        if p.max is not None and v > p.max:
            raise ValueError(f"{name}.{p.name}: {p.max}{p.unit} 以下にしてください（値: {v}）")
        out[p.name] = v
    return out


_cache: dict[str, Geometry] = {}


def build(name: str, params: dict) -> Geometry:
    """params から形状を生成する（同じ params なら結果を使い回す）。"""
    key = name + json.dumps(params, sort_keys=True)
    if key not in _cache:
        _cache[key] = get(name).build(**params)
    return _cache[key]


def catalog() -> list[dict]:
    """全コンポーネントのメタデータ（GUIのパレット／プロパティパネル用）。"""
    return [c.to_dict() for c in REGISTRY.values()]
