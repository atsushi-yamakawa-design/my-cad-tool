"""GUIエディタのサーバー（FastAPI）。

画面（ブラウザ）はアセンブリJSONだけを持ち、形が変わるときだけここに問い合わせる。
中身は今の alucad の関数を呼ぶだけ。

  uv run alucad gui   → http://127.0.0.1:8000 を開く
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import warnings
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import GROUP, Assembly, Part, bom, catalog, check, make, materials, registry, userparts
from ..cli import build as build_files
from ..export import part_color

STATIC = Path(__file__).parent / "static"
DEFAULT_DESIGNS = Path(__file__).resolve().parents[3] / "designs"
NAME_RE = re.compile(r"^[\w\-]+$")  # デザイン名に使える文字（フォルダの外を指せないように）


class PartSpec(BaseModel):
    type: str
    params: dict = {}
    pos: list[float] = [0, 0, 0]
    rot: list[float] = [0, 0, 0]
    id: str = ""


class ComponentSpec(BaseModel):
    name: str
    label: str = ""
    children: list[dict]


class AssemblySpec(BaseModel):
    version: int = 1
    units: str = "mm"
    up: str = "Z"
    name: str = "untitled"
    parts: list[PartSpec] = []


def create_app(designs_dir: Path | None = None) -> FastAPI:
    designs = Path(designs_dir) if designs_dir else DEFAULT_DESIGNS
    app = FastAPI(title="alucad")
    # 形を扱う処理は1つずつ順番に。OpenCascade は別スレッドで本当に同時に動くので、
    # 同じ形（キャッシュで共有）を同時に三角形分割・ブーリアンすると壊れる（Triangulation が None になる）
    geometry_lock = asyncio.Lock()

    @app.middleware("http")
    async def reload_user_parts(request: Request, call_next):
        """parts/ のファイルが変わっていたら部品を登録し直してから、API を1つずつ順番に処理する。"""
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        async with geometry_lock:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # 読み込みエラーは /api/watch で画面に伝える
                userparts.load()
            return await call_next(request)

    # ---- 変更の見張り（画面が1秒ごとに問い合わせる） ----
    @app.get("/api/watch")
    def watch(design: str = ""):
        stamp = _stamp(_design_path(designs, design)) if design and NAME_RE.match(design) else None
        return {"design": stamp, "parts": userparts.stamp(), "parts_errors": userparts.errors()}

    # ---- 部品の定義 ----
    @app.get("/api/catalog")
    def get_catalog():
        return {
            "components": catalog(),
            "materials": {
                k: {"label": m.label, "t": m.t, "kerf": m.kerf, "color": m.color}
                for k, m in materials.MATERIALS.items()
            },
            "filaments": {k: {"label": f.label, "color": f.color} for k, f in materials.FILAMENTS.items()},
            "bed": list(materials.BED),
        }

    @app.post("/api/validate")
    def validate(spec: PartSpec):
        """パラメータをチェックして、補完済みの params を返す（形状も作ってみる）。"""
        return {"params": _make(spec).params}

    @app.post("/api/mesh")
    def mesh(spec: PartSpec):
        """部品1つの三角形メッシュ（ローカル座標・mm・Z上）。キット・グループは中身を返す。"""
        p = _make(spec)
        if p.geometry.is_kit:
            return {"kit": True, "children": _child_dicts(p)}
        return {"kit": False, "category": p.category, "mat": p.mat, "color": part_color(p), **_tessellate(p)}

    @app.post("/api/to-group")
    def to_group(spec: PartSpec):
        """キット（や登録したグループ部品）を、同じ位置・中身のグループに変える。中身は自由に動かせるようになる。"""
        p = _make(spec)
        if not p.geometry.is_kit or p.type == GROUP:
            raise HTTPException(400, "キットではありません")
        return {"part": {"id": spec.id, "type": GROUP, "params": {"children": _child_dicts(p)}, "pos": spec.pos, "rot": spec.rot}}

    @app.post("/api/components")
    def register_component(spec: ComponentSpec):
        """グループを parts/<名前>.json に書いて、パレットの部品にする。"""
        if not NAME_RE.match(spec.name):
            raise HTTPException(400, "部品名に使えるのは英数字・_・- だけです")
        folder = userparts.parts_dir()
        if spec.name in registry.REGISTRY or any((folder / f"{spec.name}{x}").exists() for x in (".py", ".json")):
            raise HTTPException(409, f"部品名 {spec.name!r} はすでに使われています")
        if not spec.children:
            raise HTTPException(400, "中身のないグループは登録できません")
        try:
            make(GROUP, children=spec.children)  # 中身がちゃんと作れるか先に確かめる
        except (ValueError, TypeError, KeyError) as e:
            raise HTTPException(400, _message(e)) from e
        path = folder / f"{spec.name}.json"
        data = {"label": spec.label or spec.name, "children": spec.children}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        userparts.load()
        if spec.name not in registry.REGISTRY:
            raise HTTPException(400, userparts.errors().get(f"parts/{path.name}", "登録できませんでした"))
        return {"saved": str(path), "name": spec.name}

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
        return {"assembly": Assembly.load(path).to_dict(), "stamp": _stamp(path)}

    @app.put("/api/designs/{name}")
    def save_design(name: str, spec: AssemblySpec, base: str = ""):
        """保存する。base（読み込んだときの stamp）と今のファイルが違えば、外で変更されたとみなして止める。"""
        path = _design_path(designs, name)
        current = _stamp(path)
        if base and current and base != current:
            raise HTTPException(409, f"{name}.json は外部で変更されています（Claude や別の画面など）")
        asm = _assembly(spec)
        asm.name = name
        asm.save(path)
        return {"saved": str(path), "stamp": _stamp(path), "assembly": asm.to_dict()}

    @app.post("/api/designs/{name}/build")
    def build_design(name: str, spec: AssemblySpec, base: str = ""):
        """保存してから DXF / STL / STEP / GLB / 部品表 を書き出す（書き出し先は cli.default_out_dir）。"""
        saved = save_design(name, spec, base)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            paths = build_files(_design_path(designs, name))
        return {
            "files": [str(p) for p in paths],
            "warnings": [str(w.message) for w in caught],
            "stamp": saved["stamp"],
            "assembly": saved["assembly"],
        }

    # ---- 画面（ビルド済みの静的ファイル） ----
    if STATIC.exists():
        app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

        @app.get("/")
        def index():
            # 画面をビルドし直したら新しい assets を読むように、index.html はキャッシュさせない
            return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})

    return app


# ---- 内部 ----
def _make(spec: PartSpec) -> Part:
    try:
        return make(spec.type, **spec.params)
    except (ValueError, TypeError, KeyError) as e:
        raise HTTPException(400, _message(e)) from e


def _assembly(spec: AssemblySpec) -> Assembly:
    parts = []
    for s in spec.parts:
        try:
            parts.append(Part.from_dict(s.model_dump()))
        except (ValueError, TypeError, KeyError) as e:
            raise HTTPException(400, f"{s.id or s.type}: {_message(e)}") from e
    return Assembly(spec.name, parts)


def _child_dicts(p: Part) -> list[dict]:
    """キットの中身（キットの中での位置・回転）。id がない・重複している中身には "frame2" のような id を付ける。"""
    out, taken = [], set()
    for c in p.geometry.children:
        cid = c.name.replace("/", "_") if c.name else c.type
        if cid in taken or not c.name:
            n = 1
            while f"{cid}{n}" in taken:
                n += 1
            cid = f"{cid}{n}"
        taken.add(cid)
        out.append({**c.to_dict(), "id": cid})
    return out


def _stamp(path: Path) -> str | None:
    """ファイルの版の印（中身が変わると変わる）。ファイルがなければ None。"""
    if not path.exists():
        return None
    return hashlib.sha1(path.read_bytes()).hexdigest()[:12]


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
