"""プロト・sea：海を印刷した紙のループを、2本のローラーで横に回して見せる箱（紙芝居＋走馬灯のような仕組み）。

構成（sea_box キットの中身）
- 2020 フレームの箱（脚4本、上下の横桟 各4本）
- 天板・底板（sea_plate、レーザー）。ローラーの軸を通す穴と、フレームに留める穴
- ローラー2本：軸（Ø8 シャフト）＋ 3Dプリントの筒（sea_roller、両端に紙ずれ止めの縁と、軸に止めネジで留めるハブ）。片方の軸を天板の上に出して、つまみかモーターで回す
- 紙のループ（sea_paper）：2本のローラーに掛けた輪。前側の直線部分が窓から見える
- 前の窓板（sea_window、レーザー）：紙の前に開けた四角い窓

座標: X が幅（左右）、Y が奥行き（-Y が前＝見る側）、Z が上。原点は底面の中心。
"""

import math

from build123d import Align, Circle, Cone, Cylinder, Pos, Rot, Rectangle, RectangleRounded, SlotCenterToCenter, extrude

from alucad import flat, frame, materials, profiles
from alucad.mounting import frame_holes
from alucad.part import make
from alucad.printed import FILAMENT
from alucad.registry import REGISTRY, Anchor, Geometry, Param, component

CENTER_Z0 = (Align.CENTER, Align.CENTER, Align.MIN)
PAPER_T = 0.3  # 紙の厚み（表示用）
AXLE = 8.0  # ローラーの軸の直径
LIP_FLAT = 1.0  # ローラーの縁（つば）のまっすぐな部分の厚み
PAPER_GAP = 1.0  # 紙の端と縁のすき間（片側）
TAP_DRILL = {"M3": 2.5, "M4": 3.3}  # 止めネジの下穴（あとでタップを立てる）
# 脚と横桟の角に付けるミスミのブラケット（フレーム断面ごとの型番）。STEP が parts/vendor/ にあるときだけ使える
BRACKET = {"2020": "HBLFSN5", "3030": "HBLFSN6-5"}
_MB = REGISTRY.get("misumi_bracket")
BRACKET_MODELS = tuple(_MB.params[0].choices) if _MB else ()


@component(
    "sea_roller",
    label="sea ローラー",
    category="print",
    params=[
        Param("dia", float, 20.0, min=12, max=60, label="直径"),
        Param("length", float, 140.0, min=20, max=180, label="長さ"),
        Param("bore", float, AXLE, min=3, max=20, label="軸の直径"),
        Param("clearance", float, 0.2, min=0, max=1, label="軸とのすき間（片側）"),
        Param("lip", float, 2.0, min=0, max=10, label="両端の縁の段差（0で縁なし）"),
        Param("hub_dia", float, 16.0, min=8, max=60, label="ハブの直径"),
        Param("hub_len", float, 8.0, min=0, max=30, label="ハブの長さ（片側、0でハブなし）"),
        Param("set_screw", str, "M3", unit="", choices=tuple(TAP_DRILL), label="止めネジ"),
        FILAMENT,
    ],
)
def build_roller(dia, length, bore, clearance, lip, hub_dia, hub_len, set_screw, filament) -> Geometry:
    """紙を掛ける筒。軸に通して使う。原点は下のハブの端面の中心、z=0 がベッド側（立てて刷る）。

    両端に縁（つば）を付けて、紙が上下にずれないようにする。縁の内側は 45° の斜面なので、
    紙の端が当たると真ん中へ戻り、立てて刷ってもオーバーハングにならない。紙が掛かる部分の長さは length - 2×(lip+1)。
    縁のさらに外側にハブ（細い出っ張り）を出し、軸に直角な止めネジの下穴を開ける（+X 向き、ハブの長さの真ん中）。
    全長は length + 2×hub_len。
    """
    if dia < bore + 2 * clearance + 3:
        raise ValueError("sea_roller: 直径は 軸＋3mm 以上にしてください")
    if hub_len > 0 and hub_dia < bore + 2 * clearance + 6:
        raise ValueError("sea_roller: ハブの直径は 軸＋6mm 以上にしてください（止めネジのねじ山が切れません）")
    lip_t = lip + LIP_FLAT if lip > 0 else 0
    if length - 2 * lip_t < 10:
        raise ValueError("sea_roller: 長さが足りません（縁の間を 10mm 以上にしてください）")
    r, rf = dia / 2, dia / 2 + lip
    solid = Cylinder(r, length, align=CENTER_Z0)
    if lip > 0:
        for z0, z_cone, (r0, r1) in ((0, LIP_FLAT, (rf, r)), (length - LIP_FLAT, length - lip_t, (r, rf))):
            solid += Pos(0, 0, z0) * Cylinder(rf, LIP_FLAT, align=CENTER_Z0)
            solid += Pos(0, 0, z_cone) * Cone(r0, r1, lip, align=CENTER_Z0)
    if hub_len > 0:
        solid = Pos(0, 0, hub_len) * solid
        for z0 in (0, hub_len + length):
            solid += Pos(0, 0, z0) * Cylinder(hub_dia / 2, hub_len, align=CENTER_Z0)
            # 止めネジの下穴：中心から +X へ、ハブの外まで
            solid -= Pos(0, 0, z0 + hub_len / 2) * Rot(0, 90, 0) * Cylinder(TAP_DRILL[set_screw] / 2, hub_dia, align=CENTER_Z0)
    solid -= Cylinder(bore / 2 + clearance, length + 2 * hub_len, align=CENTER_Z0)
    return Geometry(solid=solid, anchors=[Anchor("bottom", (0, 0, 0), (0, 0, -1), "face")])


@component(
    "sea_paper",
    label="sea 紙のループ",
    category="paper",  # 表示用。買う部品ではないので部品表には出さない
    params=[
        Param("span", float, 214.0, min=10, label="ローラーの中心間の距離"),
        Param("roller_dia", float, 20.0, min=5, label="ローラーの直径"),
        Param("h", float, 130.0, min=10, label="紙の高さ"),
    ],
)
def build_paper(span, roller_dia, h) -> Geometry:
    """2本のローラーに掛けた紙の輪（表示用）。原点は下の縁の中心、ローラーは x=±span/2。"""
    r = roller_dia / 2
    band = SlotCenterToCenter(span, 2 * (r + PAPER_T)) - SlotCenterToCenter(span, 2 * r)
    return Geometry(solid=extrude(band, h))


def paper_length(span: float, roller_dia: float) -> float:
    """紙のループ1周の長さ（印刷するときの紙の長さ）。"""
    return 2 * span + math.pi * (roller_dia + PAPER_T)


@component(
    "sea_window",
    label="sea 窓板",
    category="plate",
    params=[
        Param("w", float, 290.0, min=20, label="幅"),
        Param("h", float, 200.0, min=20, label="高さ"),
        Param("win_w", float, 194.0, min=5, label="窓の幅"),
        Param("win_h", float, 110.0, min=5, label="窓の高さ"),
        Param("win_r", float, 3.0, min=0, label="窓の角R"),
        flat.MAT,
        Param("holes", list, [], unit="", label="穴 [[x, y, サイズ], ...]"),
    ],
)
def build_window(w, h, win_w, win_h, win_r, mat, holes) -> Geometry:
    """前に付ける板。真ん中に四角い窓。原点は板の中心・下面（フレーム側）。"""
    if win_w >= w or win_h >= h:
        raise ValueError("sea_window: 窓は板より小さくしてください")
    window = RectangleRounded(win_w, win_h, win_r) if win_r > 0 else Rectangle(win_w, win_h)
    return flat.flat_geometry(Rectangle(w, h) - window, mat, holes, name="sea_window")


@component(
    "sea_plate",
    label="sea 天板・底板",
    category="plate",
    params=[
        Param("w", float, 290.0, min=20, label="幅"),
        Param("d", float, 120.0, min=20, label="奥行き"),
        Param("r", float, 4.0, min=0, label="角R"),
        Param("span", float, 214.0, min=0, label="軸の穴の間隔"),
        Param("axle_hole", float, AXLE + 1, min=1, label="軸の穴の直径"),
        flat.MAT,
        Param("holes", list, [], unit="", label="ネジ穴 [[x, y, サイズ], ...]"),
    ],
)
def build_plate(w, d, r, span, axle_hole, mat, holes) -> Geometry:
    """ローラーの軸を通す穴が2つある板。軸の穴はネジ穴ではないので部品表に数えない。原点は板の中心・下面。"""
    outline = RectangleRounded(w, d, r) if r > 0 else Rectangle(w, d)
    for sx in (-1, 1):
        outline -= Pos(sx * span / 2, 0) * Circle(axle_hole / 2)
    return flat.flat_geometry(outline, mat, holes, name="sea_plate")


@component(
    "sea_box",
    label="sea 本体",
    category="kit",
    params=[
        Param("w", float, 290.0, min=120, max=2000, label="幅（外寸）"),
        Param("d", float, 120.0, min=80, max=2000, label="奥行き（外寸）"),
        Param("h", float, 200.0, min=80, max=2000, label="高さ（フレーム）"),
        Param("profile", str, "2020", unit="", choices=tuple(profiles.PROFILES), label="フレーム断面"),
        Param("roller_dia", float, 20.0, min=12, max=60, label="ローラーの直径"),
        Param("paper_h", float, 130.0, min=20, label="紙の高さ"),
        Param("margin", float, 10.0, min=0, label="窓の縁（紙の端から）"),
        Param("plate_mat", str, "mdf3", unit="", choices=flat.MAT.choices, label="天板・底板の材料"),
        Param("window_mat", str, "mdf3", unit="", choices=flat.MAT.choices, label="窓板の材料"),
        Param("paper", bool, True, unit="", label="紙を表示する"),
        Param("brackets", bool, bool(BRACKET_MODELS), unit="", label="側面の下の角にブラケット"),
    ],
)
def build_box(w, d, h, profile, roller_dia, paper_h, margin, plate_mat, window_mat, paper, brackets) -> Geometry:
    """原点は底面（フレームの下面）の中心。-Y が前（窓）。"""
    s = profiles.get(profile).size
    r = roller_dia / 2
    xr = w / 2 - s - r - 8  # ローラーの中心（横桟の内側から 8mm あける）
    zc = h / 2
    if paper_h > h - 2 * s - 10:
        raise ValueError(f"sea_box: 紙の高さは {h - 2 * s - 10:.0f}mm 以下にしてください（上下の横桟の間）")
    if xr < r + margin:
        raise ValueError("sea_box: 幅が足りません（ローラーが入りません）")

    cx, cy = w / 2 - s / 2, d / 2 - s / 2
    frames = [
        frame(profile, h, axis="z").at(sx * cx, sy * cy, 0).named(f"leg_{tag}")
        for sx, sy, tag in ((-1, -1, "fl"), (1, -1, "fr"), (1, 1, "br"), (-1, 1, "bl"))
    ]
    for z, tag in ((s / 2, "low"), (h - s / 2, "up")):
        frames += [
            frame(profile, w - 2 * s, axis="x").at(-(w / 2 - s), -cy, z).named(f"rail_{tag}_front"),
            frame(profile, w - 2 * s, axis="x").at(-(w / 2 - s), cy, z).named(f"rail_{tag}_back"),
            frame(profile, d - 2 * s, axis="y").at(-cx, -(d / 2 - s), z).named(f"rail_{tag}_left"),
            frame(profile, d - 2 * s, axis="y").at(cx, -(d / 2 - s), z).named(f"rail_{tag}_right"),
        ]

    top = make("sea_plate", w=w, d=d, span=2 * xr, mat=plate_mat).at(0, 0, h).named("top")
    top = top.with_params(holes=frame_holes(top, frames))
    # 底板は天板と同じ穴で、裏返して（上面をフレーム側に）下に付ける
    bottom = top.with_params().at(0, 0, 0).rot(180, 0, 0).named("bottom")

    tp = materials.get(plate_mat).t
    lip = 2.0  # ローラー両端の縁の段差（sea_roller の既定値）
    rl = paper_h + 2 * PAPER_GAP + 2 * (lip + LIP_FLAT)
    hub = 8.0  # ローラー両端のハブ（止めネジで軸に留める）の長さ
    parts = frames + [top, bottom]
    for sx, tag in ((-1, "l"), (1, "r")):
        # 右の軸だけ天板の上に 25mm 出す（つまみ・モーター用）
        top_extra = 25 if sx > 0 else 2
        parts.append(make("shaft", dia=AXLE, length=h + 2 * tp + 2 + top_extra).at(sx * xr, 0, -tp - 2).named(f"axle_{tag}"))
        parts.append(make("sea_roller", dia=roller_dia, length=rl, lip=lip, hub_len=hub).at(sx * xr, 0, zc - rl / 2 - hub).named(f"roller_{tag}"))
    if paper:
        parts.append(make("sea_paper", span=2 * xr, roller_dia=roller_dia, h=paper_h).at(0, 0, zc - paper_h / 2).named("paper"))

    # 窓板：前の面（y=-d/2）に貼る。板のローカル Y を上（Z）、下面（ローカル z=0）をフレーム側に向ける
    win = make("sea_window", w=w, h=h, win_w=2 * xr - 2 * margin, win_h=paper_h - 2 * margin, mat=window_mat)
    win = win.at(0, -d / 2, zc).rot(90, 0, 0).named("window")
    # 留めるのは4つ角だけ（脚と上下の横桟が交わるところ。Tナットは脚の前の溝に入れる）
    win = win.with_params(holes=[[sx * cx, sz * (h / 2 - s / 2), "M5"] for sx in (-1, 1) for sz in (-1, 1)])
    parts.append(win)

    # 前後の揺れ止め：左右の側面で、脚の下端と下の横桟の内側の角にブラケットを1個ずつ（計4個）。
    # 左右の揺れは前の窓板、上の角は天板が押さえるので、これが最低限
    if brackets:
        model = BRACKET.get(profile)
        if model not in BRACKET_MODELS:
            raise ValueError(f"sea_box: ブラケット {model} の STEP がありません（parts/vendor/ に置くか、ブラケットを外してください）")
        for sx, xt in ((-1, "l"), (1, "r")):
            for sy, yt in ((-1, "f"), (1, "b")):
                # ブラケットの床側の腕（+X）を脚から離れる向き（-sy）へ、壁側（+Z）を上へ
                b = make("misumi_bracket", model=model).at(sx * cx, sy * (d / 2 - s), s).rot(0, 0, -sy * 90)
                parts.append(b.named(f"bracket_{yt}{xt}"))

    return Geometry.kit(parts, anchors=[Anchor("top", (0, 0, h + tp), (0, 0, 1), "face")])
