"""ミスミのブラケット（買ってくる部品）。メーカーの STEP をそのまま形として使う。

STEP は parts/vendor/<型番>.stp に置く（メーカーの CAD データは再配布できないので git には入れない）。
型番ごとの向き・穴の位置は下の MODELS に書く。STEP がない型番は選べず、1つもなければ部品自体が出ない。
"""

from functools import lru_cache
from pathlib import Path

from build123d import Rot, import_step

from alucad.registry import Anchor, Geometry, Param, component

VENDOR = Path(__file__).parent / "vendor"

# 型番 → (STEP を置き直す回転, 穴の Anchor)
# 置き直したあとの向きは angle_bracket と同じ: 原点は外側の角、腕は +X（床側）と +Z（壁側）、幅は Y に中心振り分け。
# フレームの溝に入る突起（キー）は z<0・x<0 に少し出る（HBLFSN5・HBLFSN6-5 は 1mm、HBLFSN8 は 2mm）。
MODELS: dict[str, tuple] = {
    # HBLFSN5（-SEC の STEP）: 5シリーズ（2020）用、1スロット。腕 30mm、幅 20mm、M5 穴。
    # STEP にはボルト・ワッシャー・Tナットも入っているが、本体だけ使う
    "HBLFSN5": (
        Rot(0, 0, -90),
        [
            Anchor("hole0", (18, 0, 4.5), (0, 0, 1), "hole"),
            Anchor("hole1", (4.5, 0, 18), (1, 0, 0), "hole"),
            Anchor("floor", (15, 0, 0), (0, 0, -1), "face"),
            Anchor("wall", (0, 0, 15), (-1, 0, 0), "face"),
        ],
    ),
    # HBLFSN6-5: 6シリーズ（3030・溝幅8）用、1スロット。腕 30mm、幅 20mm、M5 穴。STEP は床側の腕が +X、壁側が +Y
    "HBLFSN6-5": (
        Rot(90, 0, 0),
        [
            Anchor("hole0", (18, 0, 4.2), (0, 0, 1), "hole"),
            Anchor("hole1", (4.5, 0, 15), (1, 0, 0), "hole"),
            Anchor("floor", (15, 0, 0), (0, 0, -1), "face"),
            Anchor("wall", (0, 0, 15), (-1, 0, 0), "face"),
        ],
    ),
    # HBLFSN8: 8シリーズ（40mm角・溝幅10）用、1スロット。腕 43mm、幅 30mm、M8 穴（Ø8.2）
    "HBLFSN8": (
        Rot(0, 0, -90),
        [
            Anchor("hole0", (20, 0, 9), (0, 0, 1), "hole"),
            Anchor("hole1", (8.2, 0, 30), (1, 0, 0), "hole"),
            Anchor("floor", (21.5, 0, 0), (0, 0, -1), "face"),
            Anchor("wall", (0, 0, 21.5), (-1, 0, 0), "face"),
        ],
    ),
}

AVAILABLE = tuple(m for m in MODELS if (VENDOR / f"{m}.stp").exists())


@lru_cache(maxsize=None)
def _load(model: str, mtime: float):
    return import_step(VENDOR / f"{model}.stp")


if AVAILABLE:

    @component(
        "misumi_bracket",
        label="ミスミ ブラケット",
        category="hardware",
        params=[
            Param("model", str, AVAILABLE[0], unit="", choices=AVAILABLE, label="型番"),
        ],
    )
    def build(model) -> Geometry:
        """ミスミのブラケット。原点は外側の角、腕は +X（床側）と +Z（壁側）、幅は Y に中心振り分け。"""
        path = VENDOR / f"{model}.stp"
        if not path.exists():
            raise ValueError(f"misumi_bracket: {path.name} を parts/vendor/ に置いてください")
        rot, anchors = MODELS[model]
        # セット品の STEP（ボルトやTナット入り）でも、いちばん大きい形＝ブラケット本体だけ使う
        body = max(_load(model, path.stat().st_mtime).solids(), key=lambda x: x.volume)
        return Geometry(solid=rot * body, anchors=anchors)
