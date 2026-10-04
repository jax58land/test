"""複線図ドリル（PDF）を生成する。

usage: python build.py [出力パス]   既定: ./preview.pdf（試作中は dist/ に置かない）
各問題は circuits.py で自動生成 → verify() で点灯シミュレーションを通したものだけを描く。
"""
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from circuits import PROBLEMS, box_joints, generate, verify

VERSION = "0.7"
FONT = "IPAGothic"
FONT_PATH = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"
DISCLAIMER = ("※本書は練習用の教材です。回路はすべてオリジナルで、試験の正式な判定基準は"
              "試験センターの公表資料が優先します。実際の施工の最終判断は有資格者が行ってください。")
DEV_GAP = 18 * mm
SW3_TERMS = {"0": (-6, 0), "1": (3.8, 0), "3": (6, 0)}   # 3路スイッチの端子位置（器具中心から mm）
STROKE = {"黒": (0, 0, 0), "白": (0.62, 0.62, 0.62), "赤": (0.85, 0.1, 0.1)}
STEPS = [
    "① 電源・器具・ボックスを単線図と同じ位置に描く",
    "② 接地側（白）: 電源 → ボックス → 電灯とコンセントのW端子すべて",
    "③ 非接地側（黒）: 電源 → ボックス → スイッチとコンセント",
    "④ 返り線: スイッチ → 同じ記号の電灯（イはイへ）。3路は1・3端子どうしを結ぶ。PLは常時=L-N／同時=返り線-N／異時=スイッチと並列",
    "⑤ 色を決める: 白は接地側、スイッチ行きの黒は電源、残りを返り線に",
    "⑥ ボックス内の接続点ごとに本数を数える（スリーブ/コネクタ選定の準備）",
    "⑦ 見直し: スイッチを1個ずつON/OFFして、正しい電灯だけが点くか指でなぞる",
]


def text(c, x, y, s, size=9, color=(0, 0, 0)):
    c.setFillColorRGB(*color)
    c.setFont(FONT, size)
    c.drawString(x, y, s)


def symbol(c, kind, x, y, label, r=3.2 * mm):
    """単線図の記号（簡略）。lamp: ○に×、switch: ●、outlet: ○に2本線、box: 破線の○。"""
    c.setStrokeColorRGB(0, 0, 0)
    c.setFillColorRGB(1, 1, 1)
    if kind == "lamp":
        c.circle(x, y, r, fill=1)
        c.line(x - r * .7, y - r * .7, x + r * .7, y + r * .7)
        c.line(x - r * .7, y + r * .7, x + r * .7, y - r * .7)
    elif kind == "switch":
        c.setFillColorRGB(0, 0, 0)
        c.circle(x, y, r * .45, fill=1)
    elif kind == "switch3":
        c.setFillColorRGB(0, 0, 0)
        c.circle(x, y, r * .45, fill=1)
        text(c, x + r * .5, y - r * 1.3, "3", 7)
    elif kind == "pilot":
        c.circle(x, y, r * .6, fill=1)
        c.setFillColorRGB(0, 0, 0)
        c.circle(x, y, r * .2, fill=1)
        text(c, x - r * .9, y - r * 1.6, "PL", 6.5)
    elif kind == "outlet":
        c.circle(x, y, r, fill=1)
        c.line(x - r * .35, y - r * .5, x - r * .35, y + r * .5)
        c.line(x + r * .35, y - r * .5, x + r * .35, y + r * .5)
    elif kind == "box":
        c.setDash(2, 2)
        c.circle(x, y, r * 1.3, fill=1)
        c.setDash()
    elif kind == "source":
        c.rect(x - r, y - r * .7, r * 2, r * 1.4, fill=1)
    if label:
        text(c, x + r + 1.5, y + r * .2, label, 9)


def draw_single(c, p, ox, oy, s):
    P = lambda l: (ox + l.x * s * mm, oy + l.y * s * mm)
    c.setLineWidth(0.9)
    for cb in p.cables:
        (x1, y1), (x2, y2) = P(p.loc(cb.a)), P(p.loc(cb.b))
        c.setStrokeColorRGB(0, 0, 0)
        c.line(x1, y1, x2, y2)
        c.setFillColorRGB(0.25, 0.25, 0.25)
        c.setFont(FONT, 6)
        if abs(y1 - y2) < 1:      # 横向きのケーブルは線の上に中央寄せ、縦向きは線の右
            c.drawCentredString((x1 + x2) / 2, y1 + 1.5 * mm, cb.spec)
        else:
            c.drawString((x1 + x2) / 2 + 1.5 * mm, (y1 + y2) / 2, cb.spec)
    for l in p.locations:
        x, y = P(l)
        if l.kind in ("source", "box"):
            symbol(c, l.kind, x, y, "")
            if l.kind == "source":
                text(c, x - 5 * mm, y - 7 * mm, "電源 1φ2W 100V", 7.5)
        else:
            for i, d in enumerate(l.devices):
                dx = (i - (len(l.devices) - 1) / 2) * 9 * mm
                symbol(c, d.kind, x + dx, y, d.label)


def terminal_xy(p, term, P):
    """器具端子の座標。W/1 は左、L/2 は右（3路は 0 が左、1・3 が右の上下）。同じ場所の器具は横に並べる。"""
    did, t = term.split(":")
    if did == "電源":
        x, y = P(p.loc("電源"))
        return (x + 5 * mm, y + 2.5 * mm) if t == "L" else (x + 8 * mm, y - 2.5 * mm)
    for l in p.locations:
        for i, d in enumerate(l.devices):
            if d.id == did:
                x, y = P(l)
                x += (i - (len(l.devices) - 1) / 2) * DEV_GAP
                if d.kind == "switch3":
                    return x + SW3_TERMS[t][0] * mm, y + SW3_TERMS[t][1] * mm
                return x + (-6 if t in ("W", "1", "a") else 6) * mm, y
    raise KeyError(term)


def net_label(net):
    """接続点の短い名前: N / L / イ（返り線）/ イ1（3路イの1端子どうし）"""
    if net.startswith("R-"):
        return net[2:]
    if net.startswith("T"):
        return net[1:-2] + net[-1]
    return net


H_LANES = [4, -4, 6.5, -6.5, 9, -9, 11.5, -11.5, 14, -14]   # 横方向の配線レーン（ボックスの高さからのずれ mm）


def junction_xy(p, wires, P):
    """ボックス内の接続点を横一列に並べる。戻り値: ({接続点: (x, y)}, {ボックス: 半径})"""
    names = sorted(box_joints(p, wires), key=lambda j: {"N": 0, "L": 1}.get(j.split(":")[1], 2))
    jxy, radius = {}, {}
    for l in p.locations:
        if l.kind == "box":
            x, y = P(l)
            mine = [j for j in names if j.startswith(l.id + ":")]
            radius[l.id] = max(13, len(mine) * 2.5 + 4) * mm
            for i, j in enumerate(mine):
                jxy[j] = (x + (i - (len(mine) - 1) / 2) * 5 * mm, y)
    return jxy, radius


def route_wires(p, wires, P, jxy, radius):
    """心線を直角に引き回す。[(wire, [(x, y), ...])] を返す。
    上下の器具へは「接続点から縦 → 心線ごとのレーンで横 → 端子へ縦」、
    左右（電源・コンセント・隣のボックス）へは「縦 → 横レーン → 縦」。レーンは心線ごとに別なので、色の違う線が重ならない。"""
    boxes = {l.id: P(l) for l in p.locations if l.kind == "box"}
    items = []
    for w in wires:
        bid = w.end_a.split(":")[0]
        bx, by = boxes[bid]
        x1, y1 = jxy[w.end_a]
        t0 = w.end_b.split("+")[0]
        x2, y2 = jxy[t0] if t0 in jxy else terminal_xy(p, t0, P)
        items.append((w, bid, x1, y1, x2, y2, abs(y2 - by) > abs(x2 - bx)))
    items.sort(key=lambda it: (it[1], it[4]))
    vcount, hi, out = {}, 0, []
    for w, bid, x1, y1, x2, y2, vertical in items:
        by = boxes[bid][1]
        if vertical:
            d = 1 if y2 > by else -1
            k = vcount.get((bid, d), 0)
            vcount[(bid, d)] = k + 1
            lane = by + d * (radius[bid] + (3 + k * 2.2) * mm)
        else:
            assert hi < len(H_LANES), f"問題{p.no}: 横方向の配線レーンが足りない"
            lane = by + H_LANES[hi] * mm
            hi += 1
        out.append((w, [(x1, y1), (x1, lane), (x2, lane), (x2, y2)]))
    return out


def draw_multi(c, p, wires, ox, oy, s):
    P = lambda l: (ox + l.x * s * mm, oy + l.y * s * mm)
    jxy, radius = junction_xy(p, wires, P)
    for l in p.locations:
        if l.kind == "box":
            x, y = P(l)
            c.setStrokeColorRGB(0.4, 0.4, 0.4)
            c.setDash(3, 2)
            c.circle(x, y, radius[l.id])
            c.setDash()
    # 心線
    c.setLineWidth(1.4)
    for w, pts in route_wires(p, wires, P, jxy, radius):
        c.setStrokeColorRGB(*STROKE[w.color])
        path = c.beginPath()
        path.moveTo(*pts[0])
        for pt in pts[1:]:
            path.lineTo(*pt)
        c.drawPath(path, stroke=1, fill=0)
        terms = w.end_b.split("+")
        x2, y2 = pts[-1]
        # 渡り線（器具側で共通）。左側の端子どうしは下、右側の端子どうしは上に回して重ならないようにする
        off = (-2.5 if terms[0].split(":")[1] in ("W", "1", "a", "0") else 2.5) * mm
        for t in terms[1:]:
            x3, y3 = terminal_xy(p, t, P)
            c.setDash(1.5, 1.2)
            c.line(x2, y2 + off, x3, y3 + off)
            c.line(x2, y2, x2, y2 + off)
            c.line(x3, y3, x3, y3 + off)
            c.setDash()
    # 接続点
    for j, (x, y) in jxy.items():
        c.setFillColorRGB(0, 0, 0)
        c.circle(x, y, 1.1 * mm, fill=1)
        net = j.split(":")[1]
        text(c, x + 1.3 * mm, y + 1.3 * mm, net_label(net), 6, (0.1, 0.3, 0.7))
    # 器具
    for l in p.locations:
        x, y = P(l)
        if l.kind == "source":
            symbol(c, "source", x, y, "")
            text(c, x - 6 * mm, y + 6 * mm, "電源", 8)
            text(c, x + 6 * mm, y + 2 * mm, "L", 7)
            text(c, x + 6 * mm, y - 4 * mm, "N", 7)
        for i, d in enumerate(l.devices):
            dx = (i - (len(l.devices) - 1) / 2) * DEV_GAP
            c.setStrokeColorRGB(0, 0, 0)
            c.setFillColorRGB(1, 1, 1)
            c.setLineWidth(0.8)
            c.roundRect(x + dx - 7 * mm, y - 2.2 * mm, 14 * mm, 4.4 * mm, 1 * mm, fill=1)
            name = {"lamp": "電灯", "switch": "SW", "switch3": "3路", "outlet": "コンセント", "pilot": "PL"}[d.kind]
            c.setFont(FONT, 6)
            c.setFillColorRGB(0, 0, 0)
            c.drawCentredString(x + dx - (1.2 * mm if d.kind == "switch3" else 0), y - 1 * mm, name + d.label)
            if d.kind == "switch3":
                for t, (tx, ty) in SW3_TERMS.items():
                    c.setFillColorRGB(0, 0, 0)
                    c.circle(x + dx + tx * mm, y + ty * mm, 0.6 * mm, fill=1)
                    text(c, x + dx + (tx - 0.8) * mm, y - 4.6 * mm, t, 5.5, (0.3, 0.3, 0.3))
            else:
                for side in (-6, 6):
                    c.setFillColorRGB(0, 0, 0)
                    c.circle(x + dx + side * mm, y, 0.7 * mm, fill=1)
            if d.kind not in ("switch", "switch3", "pilot"):
                text(c, x + dx - 7 * mm, y + 2.8 * mm, "W", 6, (0.3, 0.3, 0.3))
    c.setLineWidth(1)


def legend(c, x, y):
    for i, col in enumerate(["黒", "白", "赤"]):
        c.setStrokeColorRGB(*STROKE[col])
        c.setLineWidth(1.6)
        c.line(x + i * 22 * mm, y + 1 * mm, x + i * 22 * mm + 8 * mm, y + 1 * mm)
        text(c, x + i * 22 * mm + 10 * mm, y, col, 8)
    c.setStrokeColorRGB(0, 0, 0)
    c.setDash(1.5, 1.2)
    c.line(x + 66 * mm, y + 1 * mm, x + 74 * mm, y + 1 * mm)
    c.setDash()
    text(c, x + 76 * mm, y, "渡り線", 8)
    c.setLineWidth(1)


def page_problem(c, p, wires, cases):
    W, H = A4
    text(c, 15 * mm, H - 18 * mm, f"問題 {p.no}　{p.title}", 14)
    text(c, 15 * mm, H - 25 * mm, p.note, 8.5, (0.3, 0.3, 0.3))
    text(c, 15 * mm, H - 35 * mm, "【単線図】 これを複線図にしてみよう", 10)
    draw_single(c, p, 15 * mm, H - 135 * mm, 0.5)
    text(c, 115 * mm, H - 35 * mm, "【手順】", 10)
    y = H - 42 * mm
    for s in STEPS:       # 1行30字で折り返す
        for k in range(0, len(s), 30):
            text(c, (115 if k == 0 else 119) * mm, y, s[k:k + 30], 7.5)
            y -= 3.3 * mm
        y -= 1.5 * mm
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.line(15 * mm, H - 128 * mm, W - 15 * mm, H - 128 * mm)
    text(c, 15 * mm, H - 136 * mm, "【解答の複線図】", 10)
    legend(c, 60 * mm, H - 136 * mm)
    draw_multi(c, p, wires, 18 * mm, 0, 0.88)
    # 接続点の表
    text(c, 15 * mm, 28 * mm, "ボックス内の接続点", 9)
    joints = box_joints(p, wires)
    multi = len({j.split(":")[0] for j in joints}) > 1
    for i, (j, cols) in enumerate(joints.items()):
        box, net = j.split(":")
        if net in ("N", "L"):
            name = {"N": "接地側", "L": "非接地側"}[net]
        elif net.startswith("R-"):
            name = f"返り線（{net[2:]}）"
        else:
            name = f"3路の渡り線（{net[1:-2]}・{net[-1]}端子）"
        rows = 4 if multi else 3
        text(c, (18 + (i // rows) * 90) * mm, (23.5 - (i % rows) * 3.8) * mm,
             f"・{box + ' ' if multi else ''}{name}: {len(cols)}本（{'・'.join(cols)}）", 7.5)
    text(c, 15 * mm, H - 30 * mm, f"【検証済み】全{cases}通りのON/OFFで点灯を検証済み", 7.5, (0.1, 0.45, 0.1))
    text(c, 15 * mm, 8 * mm, DISCLAIMER, 6.5, (0.35, 0.35, 0.35))
    c.showPage()


def para(c, x, y, s, size=9.5, width=56, gap=5.2, color=(0, 0, 0)):
    """width 字で折り返して書き、次の y を返す。"""
    for k in range(0, len(s), width):
        text(c, x, y, s[k:k + width], size, color)
        y -= gap * mm
    return y


def heading(c, s, sub=""):
    W, H = A4
    text(c, 15 * mm, H - 20 * mm, s, 15)
    if sub:
        text(c, 15 * mm, H - 28 * mm, sub, 9, (0.3, 0.3, 0.3))
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.line(15 * mm, H - 32 * mm, W - 15 * mm, H - 32 * mm)


def footer(c):
    text(c, 15 * mm, 8 * mm, DISCLAIMER, 6.5, (0.35, 0.35, 0.35))
    c.showPage()


def cover(c, problems, lite):
    W, H = A4
    text(c, 20 * mm, H - 60 * mm, "第二種電気工事士 技能試験", 16)
    text(c, 20 * mm, H - 75 * mm, "複線図ドリル" + ("（無料版）" if lite else ""), 28)
    text(c, 20 * mm, H - 88 * mm, f"v{VERSION}　全{len(problems)}問", 11, (0.4, 0.4, 0.4))
    y = H - 110 * mm
    for s in ["単線図 → 複線図を、毎回同じ7ステップで書けるようにするドリルです。",
              "解答の複線図は、プログラムでスイッチの全ON/OFFを試して点灯を確認済み。",
              "回路はすべてオリジナル（候補問題の図面の転載ではありません）。"]:
        text(c, 20 * mm, y, s, 10)
        y -= 8 * mm
    footer(c)


def page_contents(c, problems):
    W, H = A4
    heading(c, "目次", "解説を読んでから、問題ページの単線図を自分で複線図にしてみてください。")
    y = H - 45 * mm
    rows = [("解説1", "複線図の7ステップと色のルール"), ("解説2", "ボックス間に何本通すか"),
            ("解説3", "パイロットランプ3種の違い")] + [(f"問題 {p.no}", p.title) for p in problems]
    for a, s in rows:
        text(c, 25 * mm, y, a, 10.5)
        text(c, 50 * mm, y, s, 10.5)
        y -= 8 * mm
    footer(c)


def page_steps(c):
    W, H = A4
    heading(c, "解説1　複線図の7ステップと色のルール", "どの問題も、この順番で1本ずつ書き足せば迷いません。")
    y = H - 45 * mm
    for s in STEPS:
        y = para(c, 20 * mm, y, s, 10.5, 52, 6) - 2 * mm
    y -= 4 * mm
    text(c, 20 * mm, y, "色のルール（このドリルの解答で使っている決め方）", 11)
    y -= 8 * mm
    for s in ["・接地側（電源のN）は白。電灯・コンセントのW端子（接地側極）には必ず白をつなぐ",
              "・スイッチへ行く非接地側（電源のL）は黒",
              "・返り線・3路の渡り線は、そのケーブルで余った色（白・赤）を使う",
              "・白を接地側以外に使うのは、スイッチ行きのケーブルの中だけ"]:
        y = para(c, 22 * mm, y, s, 9.5, 56, 5.5) - 1 * mm
    y -= 4 * mm
    y = para(c, 20 * mm, y, "※色や接続の正式な判定基準は、試験センターの公表資料（欠陥の判断基準など）で必ず確認してください。",
             8.5, 62, 5, (0.35, 0.35, 0.35))
    footer(c)


def page_boxes(c, problems):
    W, H = A4
    heading(c, "解説2　ボックス間に何本通すか", "いちばん迷うところ。ルールは1行だけです。")
    y = H - 47 * mm
    text(c, 20 * mm, y, "その線を使う器具が、ボックスの「こちら側」と「向こう側」の両方にあるときだけ通す。", 11)
    y -= 12 * mm
    y = para(c, 20 * mm, y, "接地側（白）は電灯やコンセントがあれば必ず通ります。非接地側（黒）は、向こう側にスイッチや"
             "コンセントがなければ通りません。返り線は、スイッチと電灯がボックスをはさんで別々にあるときだけ通ります。",
             9.5, 56, 5.5)
    y -= 6 * mm
    text(c, 20 * mm, y, "このドリルの問題で確かめる", 11)
    y -= 8 * mm
    names = {"N": "接地側", "L": "非接地側"}
    for p in problems:
        if sum(l.kind == "box" for l in p.locations) < 2:
            continue
        w = generate(p)
        cross = [x for x in w if p.loc(p.cables[x.cable].b).kind == "box"]
        parts = []
        for x in cross:
            n = names.get(x.net) or (f"返り線（{x.net[2:]}）" if x.net.startswith("R-") else f"3路の渡り線（{x.net[-1]}端子）")
            parts.append(f"{n}={x.color}")
        text(c, 22 * mm, y, f"問題{p.no}：{len(cross)}本", 10)
        y = para(c, 45 * mm, y, "、".join(parts), 9.5, 46, 5.5) - 3 * mm
    footer(c)


def page_pilots(c, problems):
    W, H = A4
    heading(c, "解説3　パイロットランプ3種の違い", "つなぐ場所が違うだけ。スイッチ行きの心数で見分けられます。")
    y = H - 47 * mm
    cols = [20, 48, 108, 140]
    for x, s in zip(cols, ["種類", "つなぐ場所", "スイッチ行き", "点き方"]):
        text(c, x * mm, y, s, 10)
    y -= 3 * mm
    c.setStrokeColorRGB(0.6, 0.6, 0.6)
    c.line(20 * mm, y, W - 15 * mm, y)
    y -= 7 * mm
    info = {"always": ("常時点灯", "非接地側と接地側の間", "いつも点く"),
            "same": ("同時点滅", "返り線と接地側の間（電灯と並列）", "電灯と同時に点く"),
            "diff": ("異時点滅", "スイッチと並列（非接地側と返り線）", "電灯が消えているときだけ点く")}
    for mode in ("always", "same", "diff"):
        p = next(p for p in problems if any(d.kind == "pilot" and d.mode == mode for d in p.devices()))
        loc = next(l for l in p.locations if any(d.kind == "pilot" for d in l.devices))
        cores = next(cb.cores for cb in p.cables if cb.b == loc.id)
        name, where, how = info[mode]
        text(c, 20 * mm, y, name, 10)
        text(c, 48 * mm, y, where, 8.5)
        text(c, 108 * mm, y, f"{cores}心（問題{p.no}）", 9)
        text(c, 140 * mm, y, how, 8.5)
        y -= 9 * mm
    y -= 4 * mm
    y = para(c, 20 * mm, y, "異時点滅のしくみ：スイッチが切れているとき、電流は「非接地側 → パイロットランプ → 電灯 → 接地側」と"
             "直列に流れます。パイロットランプはほとんど電流を流さないので、電灯は点かずにパイロットランプだけが点きます。"
             "スイッチを入れるとパイロットランプの両端が同じ線になり、消えます。", 9.5, 56, 5.5)
    y -= 3 * mm
    para(c, 20 * mm, y, "同時点滅と常時点灯は、スイッチの場所まで接地側（白）を持っていく必要があるので3心になります。",
         9.5, 56, 5.5)
    footer(c)


def page_next(c):
    W, H = A4
    heading(c, "続きは製品版で", "")
    y = H - 50 * mm
    for s in ["製品版（全10問）では、さらに次の問題を収録しています。",
              "・3路スイッチ（2か所から点滅）",
              "・パイロットランプ3種（異時点滅・同時点滅・常時点灯）",
              "・ボックス2個（ボックス間に何本・何色を通すか）",
              "・総合問題",
              "どの解答も、スイッチの全ON/OFFを試して点灯を確認済みです。"]:
        text(c, 20 * mm, y, s, 10.5)
        y -= 8 * mm
    footer(c)


def main(out=None, lite=False):
    name = "preview-lite.pdf" if lite else "preview.pdf"
    out = Path(out or Path(__file__).resolve().parent / name)
    out.parent.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(TTFont(FONT, FONT_PATH))
    problems = PROBLEMS[:2] if lite else PROBLEMS
    c = canvas.Canvas(str(out), pagesize=A4)
    c.setTitle("複線図ドリル" + ("（無料版）" if lite else ""))
    c.setAuthor("")
    cover(c, problems, lite)
    if not lite:
        page_contents(c, problems)
    page_steps(c)
    if not lite:
        page_boxes(c, problems)
        page_pilots(c, problems)
    for p in problems:
        wires = generate(p)
        cases = verify(p, wires)
        page_problem(c, p, wires, cases)
    if lite:
        page_next(c)
    c.save()
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--lite"]
    print(main(args[0] if args else None, lite="--lite" in sys.argv))
