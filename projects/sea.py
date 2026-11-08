"""プロト・sea：海を印刷した紙のループを、2本のローラーで横に回して見せる箱（紙芝居＋走馬灯のような仕組み）。

構成（sea_box キットの中身）
- 2020 フレームの箱（脚4本、上下の横桟 各4本）
- 天板・底板（sea_plate、レーザー）：上下とも左右の端だけの板（計4枚、真ん中はなし）。ローラーの軸を通す穴と、フレームに留める穴
- ローラー2本：軸（Ø8 シャフト）＋ 3Dプリントの筒（sea_roller、両端に紙ずれ止めの縁と、軸に止めネジで留めるハブ）。片方の軸を天板の上に出して、つまみかモーターで回す
- 紙のループ（sea_paper）：2本のローラーに掛けた輪。前側の直線部分が窓から見える
- 前の窓板（sea_window、レーザー）：紙の前に開けた四角い窓
- モーター（parts/pkp213_motor.py、オリエンタル PKP213D05A）：天板の上に下向きに付け、左のローラーの上のハブ（カップリング）を回す

座標: X が幅（左右）、Y が奥行き（-Y が前＝見る側）、Z が上。原点は底面の中心。
"""

import math

from build123d import (
    Align,
    Box,
    Circle,
    Cone,
    Cylinder,
    Pos,
    Rectangle,
    RectangleRounded,
    Rot,
    SlotCenterToCenter,
    extrude,
)

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
FLEX_PITCH, FLEX_SLIT = 2.5, 1.0  # カップリングの切れ込みの間隔と幅（横向きの切れ込み、立てて刷ると天井は両端の支えがあるブリッジ）
# 脚と横桟の角に付けるミスミのブラケット（フレーム断面ごとの型番）。STEP が parts/vendor/ にあるときだけ使える
BRACKET = {"2020": "HBLFSN5", "3030": "HBLFSN6-5"}
_MB = REGISTRY.get("misumi_bracket")
BRACKET_MODELS = tuple(_MB.params[0].choices) if _MB else ()

# モーター：オリエンタルモーター PKP213D05A（parts/pkp213_motor.py）の寸法。STEP がないときは使えない
MOTOR_OK = "pkp213_motor" in REGISTRY
MOTOR_PILOT = 15.0  # 取り付け面のインロー（位置決めの出っ張り）の直径。高さ 1.5mm
MOTOR_SHAFT = 4.0  # 軸の直径。先の 7mm は D カット（中心から平らな面まで 1.5mm）
MOTOR_SHAFT_LEN = 10.0  # 取り付け面から軸の先まで
MOTOR_FLAT = 1.5
MOTOR_HOLES = 16.0  # 取り付けねじ穴（M2）の間隔（正方形の4隅）
MOTOR_SIZE = 20.0  # 本体の角の大きさ
PLATE_REACH = MOTOR_SIZE / 2 + 4  # 天板・底板は、ローラーの軸の中心から内側へこれだけ伸ばす（モーターが乗る幅＋4mm）


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
        Param("top_hub_len", float, 0.0, min=0, max=60, label="上のハブの長さ（0で下と同じ）"),
        Param("top_bore", float, 0.0, min=0, max=20, label="上のハブの穴の直径（0で軸と同じ）"),
        Param("top_flat", float, 0.0, min=0, max=10, label="上の穴の D カット（中心から平らな面まで、0で丸穴）"),
        Param("top_screws", int, 1, min=1, max=2, label="上のハブの止めネジの数"),
        Param("top_screw_z", float, 0.0, min=0, max=60, label="上の止めネジの位置（上の端から、0でハブの真ん中）"),
        Param("top_axle", float, 0.0, min=0, max=60, label="上のハブに軸が入る長さ（下の端から、0で入らない）"),
        Param("top_axle_screw", float, 0.0, min=0, max=60, label="その軸の止めネジの位置（上のハブの下の端から、0でなし）"),
        Param("flex_slits", int, 0, min=0, max=8, label="軸とモーター軸の間の切れ込みの数（0でなし）"),
        Param("flex_bridge", float, 3.0, min=1, max=10, label="切れ込みで両側に残す厚み（細いほどやわらかい）"),
        FILAMENT,
    ],
)
def build_roller(
    dia, length, bore, clearance, lip, hub_dia, hub_len, set_screw, top_hub_len, top_bore, top_flat, top_screws, top_screw_z,
    top_axle, top_axle_screw, flex_slits, flex_bridge, filament,
) -> Geometry:
    """紙を掛ける筒。軸に通して使う。原点は下のハブの端面の中心、z=0 がベッド側（立てて刷る）。

    両端に縁（つば）を付けて、紙が上下にずれないようにする。縁の内側は 45° の斜面なので、
    紙の端が当たると真ん中へ戻り、立てて刷ってもオーバーハングにならない。紙が掛かる部分の長さは length - 2×(lip+1)。
    縁のさらに外側にハブ（細い出っ張り）を出し、軸に直角な止めネジの下穴を開ける（+X 向き、ハブの長さの真ん中）。
    上のハブだけ長さ・穴を変えて、モーターの軸とのカップリングにできる（D カットの平らな面は -Y 側。
    止めネジが2本なら、1本は平らな面に当たる -Y 向き、もう1本は +X 向き）。
    top_axle を付けると、上のハブの下側にも下から軸（bore）が入り、+Y 向きの止めネジで軸をつかめる。
    flex_slits を付けると、軸の上の端のすぐ上（2.5mm ごと）に横向きの切れ込みを入れる。切れ込みは真ん中を帯状に切り、
    両側に厚み flex_bridge の弓形を残して、1段ごとに 90° 回す（スリット形のカップリング）。軸どうしの芯ずれやねじれを少し逃がせる。
    切れ込みの天井は両側の弓形に支えられたブリッジになるので、立てたままサポートなしで刷れる。
    全長は hub_len + length + 上のハブの長さ。
    """
    top_hub = top_hub_len or hub_len
    top_bore = top_bore or bore
    if top_flat and not 0 < top_flat < top_bore / 2:
        raise ValueError("sea_roller: D カットは穴の半径より小さくしてください")
    if top_screw_z and top_screw_z > top_hub:
        raise ValueError("sea_roller: 上の止めネジは上のハブの中に入れてください")
    if top_axle >= top_hub and top_hub > 0:
        raise ValueError("sea_roller: 上のハブに軸が入る長さは、上のハブより短くしてください")
    if top_axle_screw and top_axle_screw > top_axle:
        raise ValueError("sea_roller: 軸の止めネジは、軸が入っている範囲に入れてください")
    flex_len = flex_slits * FLEX_PITCH
    if flex_slits and top_axle + flex_len > top_hub - (top_screw_z or top_hub / 2) - TAP_DRILL[set_screw] / 2 - 1:
        raise ValueError("sea_roller: 切れ込みが上の止めネジにかかります（数を減らすか、上のハブを長くしてください）")
    if flex_slits and flex_bridge >= hub_dia / 2 - 1:
        raise ValueError("sea_roller: 切れ込みの両側に残す厚みは、ハブの半径より細くしてください")
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
    drill = TAP_DRILL[set_screw] / 2

    def screw(z, turn):
        """止めネジの下穴：中心から外へ（turn は +X から Z まわりに回す角度）"""
        return Pos(0, 0, z) * Rot(0, 0, turn) * Rot(0, 90, 0) * Cylinder(drill, hub_dia, align=CENTER_Z0)

    solid = Pos(0, 0, hub_len) * solid
    if hub_len > 0:
        solid += Cylinder(hub_dia / 2, hub_len, align=CENTER_Z0)
        solid -= screw(hub_len / 2, 0)
    top0 = hub_len + length  # 上のハブの下端
    if top_hub > 0:
        solid += Pos(0, 0, top0) * Cylinder(hub_dia / 2, top_hub, align=CENTER_Z0)
        z = top0 + top_hub - (top_screw_z or top_hub / 2)
        turns = ([-90] if top_flat else [0]) + ([0 if top_flat else 90] if top_screws > 1 else [])
        for t in turns:
            solid -= screw(z, t)
        if top_axle_screw:
            solid -= screw(top0 + top_axle_screw, 90)  # 軸をつかむ止めネジ（+Y 向き）
    solid -= Cylinder(bore / 2 + clearance, top0 + top_axle, align=CENTER_Z0)
    rb = top_bore / 2 + clearance
    hole = Circle(rb)
    if top_flat:
        f = top_flat + clearance  # -Y 側を平らに（y < -f を埋める）
        hole -= Pos(0, -f - rb) * Rectangle(2 * rb, 2 * rb)
    solid -= Pos(0, 0, top0 + top_axle) * extrude(hole, top_hub - top_axle)
    if top_hub > 0:
        for i in range(flex_slits):
            cut = Box(hub_dia - 2 * flex_bridge, hub_dia + 2, FLEX_SLIT, align=CENTER_Z0)  # X の両側に弓形を残す
            z = top0 + top_axle + (FLEX_PITCH - FLEX_SLIT) / 2 + i * FLEX_PITCH
            solid -= Pos(0, 0, z) * Rot(0, 0, 90 * (i % 2)) * cut
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
        Param("w", float, 52.0, min=20, label="幅"),
        Param("d", float, 120.0, min=20, label="奥行き"),
        Param("r", float, 4.0, min=0, label="角R"),
        Param("axle_x", float, 12.0, label="軸の穴の位置（板の中心から X）"),
        Param("axle_y", float, 0.0, label="軸の穴の位置（板の中心から Y）"),
        Param("axle_hole", float, AXLE + 1, min=1, label="軸の穴の直径（モーター側はインローが通る大きさ）"),
        flat.MAT,
        Param("holes", list, [], unit="", label="ネジ穴 [[x, y, サイズ], ...]"),
    ],
)
def build_plate(w, d, r, axle_x, axle_y, axle_hole, mat, holes) -> Geometry:
    """箱の左右どちらかの端に付ける板。ローラーの軸を通す穴が1つ。軸の穴はネジ穴ではないので部品表に数えない。
    原点は板の中心・下面。"""
    if abs(axle_x) + axle_hole / 2 >= w / 2 or abs(axle_y) + axle_hole / 2 >= d / 2:
        raise ValueError("sea_plate: 軸の穴は板の中に入れてください")
    outline = RectangleRounded(w, d, r) if r > 0 else Rectangle(w, d)
    outline -= Pos(axle_x, axle_y) * Circle(axle_hole / 2)
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
        Param("motor", bool, MOTOR_OK, unit="", label="左のローラーをモーターで回す"),
        Param("flex_slits", int, 4, min=0, max=4, label="モーター側カップリングの切れ込みの数（0でなし）"),
        Param("front_gap", float, 2.0, min=0, max=100, label="ローラーの縁と前の横桟のすき間"),
    ],
)
def build_box(w, d, h, profile, roller_dia, paper_h, margin, plate_mat, window_mat, paper, brackets, motor, flex_slits, front_gap) -> Geometry:
    """原点は底面（フレームの下面）の中心。-Y が前（窓）。"""
    s = profiles.get(profile).size
    r = roller_dia / 2
    xr = w / 2 - s - r - 8  # ローラーの中心（横桟の内側から 8mm あける）
    lip = 2.0  # ローラー両端の縁の段差（sea_roller の既定値）
    # ローラー・モーターは前に寄せる：縁（つば）の外周と前の横桟の内側の間を front_gap にする
    yr = -(d / 2 - s) + r + lip + front_gap
    if yr + r + lip > d / 2 - s:
        raise ValueError("sea_box: 前のすき間が大きすぎます（ローラーが後ろの横桟に当たります）")
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

    # 天板・底板は材料を減らすため、左右の端（脚・横の横桟と、軸・モーターが乗るところ）だけの4枚にする。
    # 前後の横桟には端の近くの穴だけで留める（真ん中は板なし）
    pw = w / 2 - xr + PLATE_REACH
    plates = []
    for sx, tag in ((-1, "l"), (1, "r")):
        xc = sx * (w / 2 - pw / 2)
        top = make("sea_plate", w=pw, d=d, axle_x=sx * xr - xc, axle_y=yr, mat=plate_mat).at(xc, 0, h)
        holes = frame_holes(top, frames)
        # 底板は天板と同じ穴で、裏返して（上面をフレーム側に）下に付ける（裏返すと Y が逆になる）
        bottom = top.with_params(holes=holes, axle_y=-yr).at(xc, 0, 0).rot(180, 0, 0)
        plates.append(bottom.named(f"bottom_{tag}"))
        if motor and sx < 0:
            # 左の天板の軸の穴はモーターのインローを通す大きさにして、まわりに M2 のねじ穴を4つ（下からモーターへ締める）
            m = MOTOR_HOLES / 2
            holes = holes + [[sx * xr - xc + mx * m, yr + my * m, "M2"] for mx in (-1, 1) for my in (-1, 1)]
            top = top.with_params(axle_hole=MOTOR_PILOT + 0.5)
        plates.append(top.with_params(holes=holes).named(f"top_{tag}"))

    tp = materials.get(plate_mat).t
    rl = paper_h + 2 * PAPER_GAP + 2 * (lip + LIP_FLAT)
    hub = 8.0  # ローラー両端のハブ（止めネジで軸に留める）の長さ
    z_roll = zc - rl / 2 - hub  # ローラーの下端
    parts = frames + plates
    for sx, tag in ((-1, "l"), (1, "r")):
        roller = make("sea_roller", dia=roller_dia, length=rl, lip=lip, hub_len=hub)
        axle_top = h + tp + 2  # 軸は天板の上に 2mm 出す
        if motor and sx < 0:
            # 左のローラーは上のハブを天板の下 0.5mm まで伸ばし、モーターの軸（D カット）を止めネジ2本でつかむ。
            # Ø8 の軸は下から上のハブの中（モーターの軸の先の 3mm 手前）まで入れ、そのすぐ下を +Y 向きの止めネジでつかむ。
            # 軸の止めネジは上の横桟より下に置く（組み立てたあと、後ろから六角レンチが届くように）
            # 軸の先とモーターの軸の先の間に切れ込み（flex_slits 段）を入れて、芯ずれ・ねじれを少し逃がす
            top0 = z_roll + hub + rl  # 上のハブの下端
            top_hub = h - 0.5 - top0
            shaft_tip = h + tp - MOTOR_SHAFT_LEN  # モーターの軸の先
            grip = h - 0.5 - shaft_tip  # モーターの軸がハブに入る長さ
            top_axle = shaft_tip - 2 - flex_slits * FLEX_PITCH - top0  # 軸の穴は切れ込みの下まで
            axle_screw = min(top_axle - 3, h - s - 2 - TAP_DRILL["M3"] / 2 - top0)
            if axle_screw < 3:
                raise ValueError("sea_box: 軸の入る長さが足りません（切れ込みの数を減らしてください）")
            roller = roller.with_params(
                top_hub_len=top_hub, top_bore=MOTOR_SHAFT, top_flat=MOTOR_FLAT, top_screws=2, top_screw_z=grip / 2,
                top_axle=top_axle, top_axle_screw=axle_screw, flex_slits=flex_slits,
            )
            axle_top = top0 + top_axle - 1
        parts.append(make("shaft", dia=AXLE, length=axle_top + tp + 2).at(sx * xr, yr, -tp - 2).named(f"axle_{tag}"))
        parts.append(roller.at(sx * xr, yr, z_roll).named(f"roller_{tag}"))
    if motor:
        if not MOTOR_OK:
            raise ValueError("sea_box: モーターの STEP がありません（PKP213D05A.stp を parts/vendor/ に置くか、モーターを外してください）")
        # 天板の上に、軸を下に向けて置く（線は後ろ側に出る）
        parts.append(make("pkp213_motor").at(-xr, yr, h + tp).rot(180, 0, 0).named("motor"))
    if paper:
        parts.append(make("sea_paper", span=2 * xr, roller_dia=roller_dia, h=paper_h).at(0, yr, zc - paper_h / 2).named("paper"))

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
