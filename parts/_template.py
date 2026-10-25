"""自作部品のひな形。コピーして名前を変えて使う（「_」で始まるファイルは読み込まれない）。

  cp parts/_template.py parts/my_part.py

決まりごと（詳しくは CLAUDE.md）:
  - 単位は mm、Z が上
  - 関数の引数と params の Param を、同じ名前・同じ順番でそろえる
  - パラメータは JSON にできる値だけ（数値・文字列・true/false・リスト）
  - 3Dプリント部品は category="print"、z=0 がベッドに乗る面、filament パラメータを持つ
  - レーザーで切る板は category="plate" にして alucad.flat.flat_geometry() で作る
  - 寸法がおかしいときは ValueError を日本語のメッセージで投げる（GUI の入力欄の下に出る）
"""

from build123d import Align, Box

from alucad.printed import FILAMENT
from alucad.registry import Anchor, Geometry, Param, component


@component(
    "my_part",  # 部品の種類名（JSON の "type"）。ほかと重ならない英数字
    label="自作部品",  # パレットに出る名前
    category="print",  # frame / plate / print / kit
    params=[
        Param("w", float, 40.0, min=1, max=250, label="幅"),
        Param("d", float, 20.0, min=1, max=250, label="奥行き"),
        Param("h", float, 10.0, min=1, max=250, label="高さ"),
        FILAMENT,
    ],
)
def build(w, d, h, filament) -> Geometry:
    """部品の説明（パレットにマウスを乗せると出る）。原点は底面の中心。"""
    solid = Box(w, d, h, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return Geometry(solid=solid, anchors=[Anchor("top", (0, 0, h), (0, 0, 1), "face")])
