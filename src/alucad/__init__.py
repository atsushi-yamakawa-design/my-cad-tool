"""alucad — アルミフレーム＋レーザーカット板のためのコードCAD。単位はすべて mm。"""

# 部品モジュールを import した時点で、コンポーネントがレジストリに登録される
from .assembly import Assembly
from .bom import bom, export_bom
from .bracket import corner_bracket, l_bracket
from .check import Issue, check
from .export import cut_layers, export_dxf, export_glb, export_sheets, export_step
from .frame import frame
from .holes import HOLES, hole_dia, hole_grid
from .joint import box_face, finger_box
from .kits import frame_stand
from .materials import BED, MATERIALS, Material
from .mounting import frame_holes
from .panel import panel
from .part import Part, make
from .profiles import PROFILES, Profile
from .registry import Anchor, Param, catalog
from .view import show

__all__ = [
    "Anchor",
    "Assembly",
    "BED",
    "HOLES",
    "Issue",
    "MATERIALS",
    "Material",
    "PROFILES",
    "Param",
    "Part",
    "Profile",
    "bom",
    "box_face",
    "catalog",
    "check",
    "corner_bracket",
    "cut_layers",
    "export_bom",
    "export_dxf",
    "export_glb",
    "export_sheets",
    "export_step",
    "finger_box",
    "frame",
    "frame_holes",
    "frame_stand",
    "hole_dia",
    "hole_grid",
    "l_bracket",
    "make",
    "panel",
    "show",
]
