"""オリエンタルモーターのステッピングモーター PKP213D05A（20mm 角、買ってくる部品）。メーカーの STEP をそのまま形として使う。

STEP は parts/vendor/PKP213D05A.stp に置く（メーカーの CAD データは再配布できないので git には入れない）。
STEP がなければ部品自体が出ない。

寸法（STEP から読んだ値）
- 本体 20 × 20 × 30mm、取り付け面にインロー（位置決めの出っ張り）Ø15・高さ 1.5mm
- 軸 Ø4、取り付け面から 10mm。先の 7mm は D カット（中心から平らな面まで 1.5mm）
- 取り付け面の4隅に M2 のねじ穴（16mm 間隔の正方形）
"""

from functools import lru_cache
from pathlib import Path

from build123d import Rot, import_step

from alucad.registry import Anchor, Geometry, component

STEP = Path(__file__).parent / "vendor" / "PKP213D05A.stp"


@lru_cache(maxsize=None)
def _body(mtime: float):
    # STEP は取り付け面が x=0・軸が +X・線が -Y。軸を +Z に向け直す
    return Rot(0, -90, 0) * import_step(STEP).solids()[0]


if STEP.exists():

    @component("pkp213_motor", label="モーター PKP213D05A（オリエンタル）", category="hardware", params=[])
    def build() -> Geometry:
        """20mm 角ステッピングモーター。原点は取り付け面の中心、軸は +Z（Ø4、先の 7mm は D カットで平らな面が +Y）。
        取り付け面の4隅に M2 のねじ穴（16mm 間隔）。線は -Y 側に出る。"""
        return Geometry(
            solid=_body(STEP.stat().st_mtime),
            anchors=[
                Anchor("mount", (0, 0, 0), (0, 0, 1), "face"),
                Anchor("shaft", (0, 0, 10), (0, 0, 1), "end"),
            ],
        )
