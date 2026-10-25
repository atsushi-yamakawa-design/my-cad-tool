"""parts/ フォルダの自作部品。"""

import pytest

from alucad import Assembly, bom, catalog, check, frame, make, userparts
from alucad.registry import REGISTRY

PART_SRC = '''
from build123d import Align, Box
from alucad.printed import FILAMENT
from alucad.registry import Geometry, Param, component

@component("test_block", label="テストブロック", category="print",
           params=[Param("w", float, {w}, min=1, label="幅"), FILAMENT])
def build(w, filament):
    """テスト用"""
    return Geometry(solid=Box(w, 10, 5, align=(Align.CENTER, Align.CENTER, Align.MIN)))
'''


def test_repo_parts_build_with_defaults():
    """リポジトリの parts/ にある部品は、どれもデフォルト値で形が作れる。"""
    user = [n for n, c in REGISTRY.items() if c.source]
    assert "frame_foot" in user
    assert userparts.errors() == {}
    for name in user:
        assert make(name).solid().volume > 0, name


def test_frame_foot_on_leg():
    leg = frame("2020", 100, axis="z").at(0, 0, 4)
    foot = make("frame_foot")
    assert check([leg, foot]) == []  # すき間があるのでめり込まない
    b = bom([leg, foot])
    assert dict(b.joints) == {("tap", "M5", "2020"): 1}


@pytest.fixture
def tmp_parts(tmp_path, monkeypatch):
    monkeypatch.setenv("ALUCAD_PARTS", str(tmp_path))
    userparts.load(force=True)
    yield tmp_path
    monkeypatch.delenv("ALUCAD_PARTS")
    userparts.load(force=True)


def _bump(path, text):
    """書き換えを確実に検知させるため、サイズの違う内容で書く。"""
    path.write_text(text, encoding="utf-8")


def test_add_change_and_remove_user_part(tmp_parts):
    assert "frame_foot" not in REGISTRY  # 別フォルダに切り替わった

    f = tmp_parts / "block.py"
    _bump(f, PART_SRC.replace("{w}", "20.0"))
    assert userparts.load() is True
    assert make("test_block").solid().bounding_box().size.X == pytest.approx(20)
    entry = next(c for c in catalog() if c["name"] == "test_block")
    assert entry["user"] is True and entry["description"] == "テスト用"

    _bump(f, PART_SRC.replace("{w}", "35.0") + "\n# changed\n")
    assert userparts.load() is True
    assert make("test_block").solid().bounding_box().size.X == pytest.approx(35)
    assert userparts.load() is False  # 変わっていなければ何もしない

    f.unlink()
    userparts.load()
    assert "test_block" not in REGISTRY


def test_broken_user_part_is_reported_not_fatal(tmp_parts):
    (tmp_parts / "ok.py").write_text(PART_SRC.replace("{w}", "20.0"), encoding="utf-8")
    (tmp_parts / "bad.py").write_text("def oops(:\n", encoding="utf-8")
    with pytest.warns(UserWarning, match="bad.py"):
        userparts.load()
    assert "bad.py" in userparts.errors() and "SyntaxError" in userparts.errors()["bad.py"]
    assert "test_block" in REGISTRY  # ほかのファイルは読み込まれる


def test_user_part_cannot_override_builtin(tmp_parts):
    (tmp_parts / "dup.py").write_text(PART_SRC.replace("test_block", "panel").replace("{w}", "20.0"), encoding="utf-8")
    with pytest.warns(UserWarning, match="すでに使われています"):
        userparts.load()
    assert REGISTRY["panel"].source == ""


def test_underscore_files_are_ignored(tmp_parts):
    (tmp_parts / "_draft.py").write_text(PART_SRC.replace("{w}", "20.0"), encoding="utf-8")
    userparts.load()
    assert "test_block" not in REGISTRY


def test_user_part_in_assembly_json(tmp_parts, tmp_path):
    (tmp_parts / "block.py").write_text(PART_SRC.replace("{w}", "20.0"), encoding="utf-8")
    userparts.load()
    asm = Assembly("a", [make("test_block", w=12).named("b1")])
    back = Assembly.load(asm.save(tmp_path / "a.json"))
    assert back["b1"].params["w"] == 12
