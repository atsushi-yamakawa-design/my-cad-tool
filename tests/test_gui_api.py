"""GUIサーバーのAPI。"""

import json

import pytest
from fastapi.testclient import TestClient

from alucad import Assembly, frame_stand
from alucad.gui.server import create_app


@pytest.fixture
def client(tmp_path):
    Assembly("stand", [frame_stand().named("stand")]).save(tmp_path / "stand.json")
    return TestClient(create_app(tmp_path))


def test_catalog(client):
    d = client.get("/api/catalog").json()
    assert {c["name"] for c in d["components"]} >= {"frame", "panel", "frame_stand", "finger_box"}
    assert d["materials"]["mdf3"]["t"] == 3.0 and d["bed"] == [300, 210]


def test_mesh_single_part(client):
    d = client.post("/api/mesh", json={"type": "panel", "params": {"w": 100, "h": 50}}).json()
    assert d["kit"] is False and d["category"] == "plate" and d["mat"] == "mdf3"
    xs, zs = d["vertices"][0::3], d["vertices"][2::3]
    assert (min(xs), max(xs), min(zs), max(zs)) == (-50, 50, 0, 3)  # mm・Z上のまま
    assert len(d["indices"]) % 3 == 0 and max(d["indices"]) < len(d["vertices"]) // 3


def test_mesh_kit_returns_children(client):
    d = client.post("/api/mesh", json={"type": "frame_stand", "params": {}}).json()
    assert d["kit"] is True and len(d["children"]) == 17
    top = next(c for c in d["children"] if c["id"] == "top")
    assert top["pos"] == [0, 0, 150] and len(top["params"]["holes"]) == 10


def test_validate_fills_defaults_and_reports_errors(client):
    ok = client.post("/api/validate", json={"type": "panel", "params": {"w": 80}}).json()
    assert ok["params"]["h"] == 150 and ok["params"]["mat"] == "mdf3"
    bad = client.post("/api/validate", json={"type": "panel", "params": {"w": -1}})
    assert bad.status_code == 400 and "1mm 以上" in bad.json()["detail"]
    unknown = client.post("/api/validate", json={"type": "nope", "params": {}})
    assert unknown.status_code == 400 and "未登録" in unknown.json()["detail"]


def _load(client, name):
    return client.get(f"/api/designs/{name}").json()["assembly"]


def test_explode(client):
    stand = _load(client, "stand")["parts"][0]
    stand["pos"] = [100, 0, 0]
    parts = client.post("/api/explode", json=stand).json()["parts"]
    top = next(p for p in parts if p["id"] == "stand_top")
    assert top["pos"] == [100, 0, 150]


def test_designs_roundtrip_and_build(client, tmp_path):
    assert client.get("/api/designs").json()["designs"] == ["stand"]
    asm = _load(client, "stand")
    asm["parts"][0]["params"]["w"] = 260
    assert client.put("/api/designs/copy", json=asm).status_code == 200
    saved = json.loads((tmp_path / "copy.json").read_text(encoding="utf-8"))
    assert saved["name"] == "copy" and saved["parts"][0]["params"]["w"] == 260

    res = client.post("/api/designs/copy/build", json=asm).json()
    names = sorted(p.split("/")[-1] for p in res["files"])
    assert "copy_mdf3.dxf" in names and "copy_bom.md" in names
    assert (tmp_path / "out" / "copy.step").exists()


def test_design_name_is_restricted(client):
    asm = _load(client, "stand")
    assert client.put("/api/designs/bad name", json=asm).status_code == 400
    assert client.get("/api/designs/nothing").status_code == 404


def test_check_and_bom(client):
    asm = _load(client, "stand")
    assert client.post("/api/check", json=asm).json() == {"issues": []}
    asm["parts"][0]["params"]["w"] = 400
    issues = client.post("/api/check", json=asm).json()["issues"]
    assert issues[0]["level"] == "error" and "加工エリア" in issues[0]["message"]
    b = client.post("/api/bom", json=asm).json()
    assert {"profile": "2020", "length": 360.0, "qty": 2} in b["frames"] and "# 部品表" in b["markdown"]


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "<div id=\"root\">" in r.text


def test_save_conflict_when_changed_outside(client, tmp_path):
    first = client.get("/api/designs/stand").json()
    stamp, asm = first["stamp"], first["assembly"]
    assert client.get("/api/watch", params={"design": "stand"}).json()["design"] == stamp

    # 外部（Claude Code など）がファイルを書き換える
    Assembly("stand", [frame_stand(w=250).named("stand")]).save(tmp_path / "stand.json")
    changed = client.get("/api/watch", params={"design": "stand"}).json()["design"]
    assert changed != stamp

    # 古い stamp のまま保存しようとすると止まる
    r = client.put("/api/designs/stand", params={"base": stamp}, json=asm)
    assert r.status_code == 409 and "外部で変更" in r.json()["detail"]
    # 新しい stamp なら保存できる
    r = client.put("/api/designs/stand", params={"base": changed}, json=asm)
    assert r.status_code == 200 and r.json()["stamp"] != changed
    # 保存した内容（サーバーで整えたもの）が返る。画面はこれを次のマージの基準にする
    assert r.json()["assembly"] == client.get("/api/designs/stand").json()["assembly"]


def test_watch_reports_parts_state(client):
    w = client.get("/api/watch").json()
    assert w["design"] is None and len(w["parts"]) == 12 and w["parts_errors"] == {}


def test_mesh_has_color(client):
    d = client.post("/api/mesh", json={"type": "angle_bracket", "params": {}}).json()
    assert d["category"] == "print" and d["color"].startswith("#")
