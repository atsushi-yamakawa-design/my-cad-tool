"""GUIエディタのサーバー（FastAPI）。

画面（ブラウザ）はアセンブリJSONだけを持ち、形が変わるときだけここに問い合わせる。
中身は今の alucad の関数を呼ぶだけ。

  uv run alucad gui   → http://127.0.0.1:8000 を開く
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import Assembly, Part, bom, catalog, check, make, materials
from ..cli import build as build_files

STATIC = Path(__file__).parent / "static"
DEFAULT_DESIGNS = Path(__file__).resolve().parents[3] / "designs"
NAME_RE = re.compile(r"^[\w\-]+$")  # デザイン名に使える文字（フォルダの外を指せないように）


class PartSpec(BaseModel):
    type: str
    params: dict = {}
    pos: list[float] = [0, 0, 0]
    rot: list[float] = [0, 0, 0]
    id: str = ""


class AssemblySpec(BaseModel):
    version: int = 1
    units: str = "mm"
    up: str = "Z"
    name: str = "untitled"
    parts: list[PartSpec] = []


def create_app(designs_dir: Path | None = None) -> FastAPI:
    designs = Path(designs_dir) if designs_dir else DEFAULT_DESIGNS
    app = FastAPI(title="alucad")

    # ---- 部品の定義 ----
    @app.get("/api/catalog")
    def get_catalog():
        return {
            "components": catalog(),
            "materials": {
                k: {"label": m.label, "t": m.t, "kerf": m.kerf, "color": m.color}
                for k, m in materials.MATERIALS.items()
            },
            "bed": list(materials.BED),
        }

    @app.post("/api/validate")
    def validate(spec: PartSpec):
        """パラメータをチェックして、補完済みの params を返す（形状も作ってみる）。"""
        return {"params": _make(spec).params}

    @app.post("/api/mesh")
    def mesh(spec: PartSpec):
        """部品1つの三角形メッシュ（ローカル座標・mm・Z上）。キットは中身を返す。"""
        p = _make(spec)
        children = p.geometry.children
        if children:
            return {"kit": True, "children": [_part_dict(c) for c in children]}
        return {"kit": False, "category": _category(p), "mat": p.mat, **_tessellate(p)}

    @app.post("/api/explode")
    def explode(spec: PartSpec):
        """キットをばらばらの部品（ワールド座標）に分解する。"""
        p = _place(_make(spec), spec)
        if not p.geometry.children:
            raise HTTPException(400, "キットではありません")
        return {"parts": [_part_dict(c, strip=spec.id) for c in p.expand()]}

    # ---- アセンブリ全体 ----
    @app.post("/api/check")
    def run_check(spec: AssemblySpec):
        issues = check(_assembly(spec))
        return {"issues": [{"level": i.level, "part": i.part, "message": i.message} for i in issues]}

    @app.post("/api/bom")
    def run_bom(spec: AssemblySpec):
        b = bom(_assembly(spec))
        return {**b.to_dict(), "markdown": b.to_markdown()}

    # ---- デザインファイル（designs/*.json） ----
    @app.get("/api/designs")
    def list_designs():
        return {"designs": sorted(p.stem for p in designs.glob("*.json")), "dir": str(designs)}

    @app.get("/api/designs/{name}")
    def load_design(name: str):
        path = _design_path(designs, name)
        if not path.exists():
            raise HTTPException(404, f"{name}.json がありません")
        return Assembly.load(path).to_dict()

    @app.put("/api/designs/{name}")
    def save_design(name: str, spec: AssemblySpec):
        asm = _assembly(spec)
        asm.name = name
        path = asm.save(_design_path(designs, name))
        return {"saved": str(path)}

    @app.post("/api/designs/{name}/build")
    def build_design(name: str, spec: AssemblySpec):
        """保存してから DXF / STEP / GLB / 部品表 を designs/out/ に書き出す。"""
        save_design(name, spec)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            paths = build_files(_design_path(designs, name))
        return {"files": [str(p) for p in paths], "warnings": [str(w.message) for w in caught]}

    # ---- 画面（ビルド済みの静的ファイル） ----
    if STATIC.exists():
        app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

        @app.get("/")
        def index():
            return FileResponse(STATIC / "index.html")

    return app


# ---- 内部 ----
def _make(spec: PartSpec) -> Part:
    try:
        return make(spec.type, **spec.params)
    except (ValueError, TypeError, KeyError) as e:
        raise HTTPException(400, _message(e)) from e


def _place(p: Part, spec: PartSpec) -> Part:
    return p.at(*spec.pos).rot(*spec.rot).named(spec.id)


def _assembly(spec: AssemblySpec) -> Assembly:
    parts = []
    for s in spec.parts:
        try:
            parts.append(Part.from_dict(s.model_dump()))
        except (ValueError, TypeError, KeyError) as e:
            raise HTTPException(400, f"{s.id or s.type}: {_message(e)}") from e
    return Assembly(spec.name, parts)


def _part_dict(p: Part, strip: str = "") -> dict:
    d = p.to_dict()
    if strip and d.get("id", "").startswith(strip + "/"):
        d["id"] = d["id"].replace("/", "_")  # 分解した部品の id は "stand_top" のようにする
    return d


def _category(p: Part) -> str:
    from ..registry import get

    return get(p.type).category


def _tessellate(p: Part) -> dict:
    vertices, triangles = p.geometry.solid.tessellate(0.05, 0.2)
    return {
        "vertices": [round(c, 4) for v in vertices for c in (v.X, v.Y, v.Z)],
        "indices": [i for tri in triangles for i in tri],
    }


def _design_path(designs: Path, name: str) -> Path:
    if not NAME_RE.match(name):
        raise HTTPException(400, "デザイン名に使えるのは英数字・_・- だけです")
    return designs / f"{name}.json"


def _message(e: Exception) -> str:
    return str(e.args[0]) if isinstance(e, KeyError) and e.args else str(e)
