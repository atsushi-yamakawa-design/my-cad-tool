"""Assembly：Part の集合。JSON と相互変換できる。

JSONの形（将来のGUIはこれを編集する）:
{
  "version": 1, "units": "mm", "up": "Z", "name": "...",
  "parts": [
    {"id": "leg1", "type": "frame", "params": {...}, "pos": [x, y, z], "rot": [rx, ry, rz]},
    ...
  ]
}
"""

from __future__ import annotations

import json
from pathlib import Path

from .part import Part

FORMAT_VERSION = 1


class Assembly:
    def __init__(self, name: str = "assembly", parts: list[Part] | None = None):
        self.name = name
        self.parts: list[Part] = []
        for p in parts or []:
            self.add(p)

    def add(self, part: Part, name: str | None = None) -> Part:
        """部品を追加する。id（name）が無ければ "frame1" のように自動で振る。"""
        name = name or part.name or self._next_id(part.type)
        if any(p.name == name for p in self.parts):
            raise ValueError(f"id {name!r} はすでに使われています")
        part = part.named(name)
        self.parts.append(part)
        return part

    def __iter__(self):
        return iter(self.parts)

    def __len__(self):
        return len(self.parts)

    def __getitem__(self, name: str) -> Part:
        """id で部品を取り出す。キットの中身は "stand/top" のように「キットのid/中身の名前」で取れる。"""
        for p in self.parts:
            if p.name == name:
                return p
        for p in self.expanded():
            if p.name == name:
                return p
        raise KeyError(name)

    def expanded(self) -> list[Part]:
        """キットを中身に展開した、全部品のリスト（ワールド座標）。"""
        return [q for p in self.parts for q in p.expand()]

    def flat_parts(self) -> list[Part]:
        """レーザーで切る板パーツだけ（キットの中身も含む）。"""
        return [p for p in self.expanded() if p.is_flat]

    # ---- JSON ----
    def to_dict(self) -> dict:
        return {
            "version": FORMAT_VERSION,
            "units": "mm",
            "up": "Z",
            "name": self.name,
            "parts": [p.to_dict() for p in self.parts],
        }

    @classmethod
    def from_dict(cls, d: dict) -> Assembly:
        if d.get("version") != FORMAT_VERSION:
            raise ValueError(f"未対応のバージョン: {d.get('version')}")
        return cls(d.get("name", "assembly"), [Part.from_dict(x) for x in d["parts"]])

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str | Path) -> Assembly:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def _next_id(self, type: str) -> str:
        n = 1
        while any(p.name == f"{type}{n}" for p in self.parts):
            n += 1
        return f"{type}{n}"
