"""alucad — アルミフレーム＋レーザーカット板のためのコードCAD。単位はすべて mm。"""

from .assembly import Assembly
from .export import cut_layers, export_dxf
from .frame import frame  # import した時点でコンポーネントが登録される
from .holes import HOLES, hole_dia, hole_grid
from .panel import panel
from .part import Part, make
from .profiles import PROFILES, Profile
from .registry import Anchor, Param, catalog
from .view import show

__all__ = [
    "Anchor",
    "Assembly",
    "HOLES",
    "PROFILES",
    "Param",
    "Part",
    "Profile",
    "catalog",
    "cut_layers",
    "export_dxf",
    "frame",
    "hole_dia",
    "hole_grid",
    "make",
    "panel",
    "show",
]
