"""部品表（BOM）とコマンドライン。"""

import json

import pytest

from alucad import Assembly, bom, finger_box, frame, frame_stand, panel
from alucad.cli import build, main


@pytest.fixture(scope="module")
def stand_asm():
    return Assembly("stand", [frame_stand(280, 200, 150).named("stand")])


def test_bom_frames(stand_asm):
    b = bom(stand_asm)
    assert dict(b.frames) == {("2020", 150): 4, ("2020", 240): 2, ("2020", 160): 2}


def test_bom_fasteners(stand_asm):
    b = bom(stand_asm)
    # 天板の穴10: 脚の端面4（タップ）＋横桟6（Tナット）／L字プレート8枚×5穴=40（Tナット）
    assert b.joints[("tap", "M5", "2020")] == 4
    assert b.joints[("tnut", "M5", "2020")] == 6 + 40
    assert sum(b.bolts.values()) == 50
    # ボルト長さ: MDF3+Tナット6=9→10、MDF3+タップ8=11→12、アクリル5+Tナット6=11→12
    assert b.bolts[("M5", 10)] == 6
    assert b.bolts[("M5", 12)] == 4 + 40


def test_bom_sheets(stand_asm):
    b = bom(stand_asm)
    assert b.sheets == {"acrylic5": 1, "mdf3": 1}
    assert len(b.plates["acrylic5"]) == 8


def test_bom_free_holes_need_nuts():
    """相手のフレームがない穴はボルト＋ナット。"""
    b = bom([panel(100, 50, holes=[[-40, 0, "M3"], [40, 0, "M3"]])])
    assert b.joints == {("nut", "M3", ""): 2}


def test_bom_tnut_on_rail_side():
    rail = frame("2020", 200, axis="x").at(-100, 0, -10)  # 上面が z=0
    plate = panel(100, 40, holes=[[0, 0, "M5"]])  # 下面が z=0
    b = bom([rail, plate])
    assert b.joints == {("tnut", "M5", "2020"): 1}


def test_bom_markdown_and_csv(stand_asm):
    b = bom(stand_asm)
    md = b.to_markdown()
    assert "| 2020 | 150 | 4 |" in md and "合計長さ: 2020: 1400mm" in md
    assert "フレーム,2020,150mm,4" in b.to_csv()
    assert json.dumps(b.to_dict(), ensure_ascii=False)


def test_cli_build_all(tmp_path, stand_asm):
    src = stand_asm.save(tmp_path / "stand.json")
    paths = build(src)
    names = sorted(p.name for p in paths)
    assert names == sorted([
        "stand_acrylic5.dxf", "stand_mdf3.dxf", "stand.step", "stand.glb", "stand_bom.md", "stand_bom.csv",
        "stand_preview.png",
    ])
    assert all(p.exists() and p.parent == tmp_path / "out" for p in paths)


def test_cli_main_only_and_out(tmp_path, capsys):
    src = Assembly("box", [finger_box(120, 80, 60)]).save(tmp_path / "box.json")
    assert main(["build", str(src), "--only", "dxf,bom", "-o", str(tmp_path / "dist")]) == 0
    out = capsys.readouterr().out
    assert "box_mdf3.dxf" in out and "box_bom.md" in out and ".step" not in out
    assert (tmp_path / "dist" / "box_mdf3.dxf").exists()


def test_cli_catalog(capsys):
    assert main(["catalog"]) == 0
    names = {c["name"] for c in json.loads(capsys.readouterr().out)}
    assert {"frame", "panel", "frame_stand", "finger_box"} <= names


def test_cli_rejects_unknown_format(tmp_path):
    src = Assembly("x", [panel(50, 50)]).save(tmp_path / "x.json")
    with pytest.raises(SystemExit):
        main(["build", str(src), "--only", "pdf"])


def test_port_state():
    import socket

    from alucad.cli import _port_state

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        port = s.getsockname()[1]
        assert _port_state(port) == "busy"  # alucad 以外が使っている
    assert _port_state(port) == "free"
