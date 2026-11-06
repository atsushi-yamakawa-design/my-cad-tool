"""グループ：部品をまとめて、全体でも中身でも動かせるようにしたもの。

JSON では中身を params.children にそのまま書く（中身の pos / rot はグループの中での位置・回転）:
  {"id": "rollers", "type": "group", "params": {"children": [{"id": "roller_l", "type": ..., ...}, ...]},
   "pos": [0, 0, 0], "rot": [0, 0, 0]}

グループは入れ子にできる。キットと同じく、部品表・書き出し・チェックでは中身に展開される
（中身の名前は "rollers/roller_l" のようになる）。

parts/<名前>.json に {"label": ..., "children": [...]} と書くと、そのグループがパレットの部品になる
（userparts が読み込む。GUI の「コンポーネントとして登録」がこれを書く）。
"""

from __future__ import annotations

from .part import Part
from .registry import Geometry, Param, component

GROUP = "group"


def group_parts(children: list[dict], who: str = GROUP) -> list[Part]:
    """中身の JSON を Part にする。id は必須で、グループの中で重複させない。"""
    parts, seen = [], set()
    for c in children:
        if not isinstance(c, dict) or "type" not in c:
            raise ValueError(f"{who}: 中身は {{\"id\", \"type\", \"params\", \"pos\", \"rot\"}} の形で書いてください")
        cid = c.get("id", "")
        if not cid or "/" in cid:
            raise ValueError(f"{who}: 中身の id を「/」なしで付けてください（{c['type']}）")
        if cid in seen:
            raise ValueError(f"{who}: 中身の id {cid!r} が重複しています")
        seen.add(cid)
        parts.append(Part.from_dict(c))
    return parts


@component(
    GROUP,
    label="グループ",
    category=GROUP,
    params=[Param("children", list, [], unit="", label="中身")],
)
def build_group(children) -> Geometry:
    """原点はグループの基準点。中身はこの基準点からの位置・回転で置く。"""
    return Geometry.kit(group_parts(children))
