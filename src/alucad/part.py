"""Part：コンポーネント1個の「種類＋パラメータ＋位置・回転」。

Part 自体は形状を持たない。形状は必要になったときにレジストリから生成する。
だから Part ⇄ JSON は常に完全に往復できる（将来のGUIはこのJSONを編集する）。
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from build123d import Intrinsic, Location, Shape, Sketch, Vector

from . import registry


@dataclass(frozen=True)
class Part:
    type: str
    params: dict
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)  # XYZ オイラー角（度）。three.js の 'XYZ' と同じ
    name: str = ""

    # ---- 配置（メソッドチェーン用。元の Part は変えずに新しい Part を返す） ----
    def at(self, x: float = 0, y: float = 0, z: float = 0) -> Part:
        """位置を指定する（絶対座標・mm）。"""
        return replace(self, position=(float(x), float(y), float(z)))

    def rot(self, x: float = 0, y: float = 0, z: float = 0) -> Part:
        """回転を指定する（度。X→Y→Z の順に、回転後の軸まわりで回す＝Intrinsic XYZ）。"""
        return replace(self, rotation=(float(x), float(y), float(z)))

    def named(self, name: str) -> Part:
        return replace(self, name=name)

    def with_params(self, **params) -> Part:
        """パラメータの一部を変えた Part を返す（位置・回転・名前はそのまま）。"""
        new = make(self.type, **{**self.params, **params})
        return replace(new, position=self.position, rotation=self.rotation, name=self.name)

    # ---- 形状 ----
    @property
    def location(self) -> Location:
        return Location(self.position, self.rotation, Intrinsic.XYZ)

    @property
    def geometry(self) -> registry.Geometry:
        """ローカル座標の形状一式。"""
        return registry.build(self.type, self.params)

    def solid(self) -> Shape:
        """配置済みの3D形状。"""
        return self.location * self.geometry.solid

    def sketch(self) -> dict[str, Sketch | Shape]:
        """板パーツの2Dスケッチ（レイヤー別・ローカル座標）。DXFはここから作る。"""
        return self.geometry.layers

    @property
    def mat(self) -> str | None:
        """材料キー（板パーツのみ）。"""
        return self.params.get("mat")

    def expand(self) -> list[Part]:
        """キットを中身の Part（ワールド座標）に展開する。キットでなければ [self]。"""
        children = self.geometry.children
        if not children:
            return [self]
        out = []
        for c in children:
            loc = self.location * c.location
            name = f"{self.name}/{c.name}" if self.name else c.name
            world = replace(c, position=_t(loc.position), rotation=_t(loc.orientation), name=name)
            out += world.expand()
        return out

    @property
    def category(self) -> str:
        return registry.get(self.type).category

    @property
    def is_print(self) -> bool:
        """3Dプリントする部品かどうか。"""
        return self.category == "print"

    @property
    def is_flat(self) -> bool:
        """レーザーで切る板パーツかどうか。"""
        return "cut" in self.geometry.layers

    def anchors(self) -> list[registry.Anchor]:
        """接続点（ワールド座標）。"""
        loc = self.location
        rot_only = Location((0, 0, 0), self.rotation, Intrinsic.XYZ)
        out = []
        for a in self.geometry.anchors:
            p = loc * Location(a.pos)
            n = rot_only * Location(a.normal)
            out.append(
                registry.Anchor(a.name, _t(p.position), _t(n.position), a.kind)
            )
        return out

    # ---- JSON ----
    def to_dict(self) -> dict:
        d = {"id": self.name} if self.name else {}
        d.update(
            type=self.type,
            params=self.params,
            pos=list(self.position),
            rot=list(self.rotation),
        )
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Part:
        return make(d["type"], **d.get("params", {})).at(*d.get("pos", (0, 0, 0))).rot(
            *d.get("rot", (0, 0, 0))
        ).named(d.get("id", ""))


def make(type: str, **params) -> Part:
    """種類名と引数から Part を作る。

    引数チェックと形状生成をここで一度やっておく（結果はキャッシュされる）。
    おかしな寸法は、それを書いた行でエラーになる。
    """
    p = Part(type, registry.validate(type, params))
    p.geometry
    return p


def place(p: Part, at=None, rot=None, name: str = "") -> Part:
    """部品関数の at= / rot= / name= キーワード引数を Part に反映する。"""
    if at is not None:
        p = p.at(*at)
    if rot is not None:
        p = p.rot(*rot)
    if name:
        p = p.named(name)
    return p


def _t(v: Vector) -> tuple[float, float, float]:
    return (round(v.X, 9), round(v.Y, 9), round(v.Z, 9))
