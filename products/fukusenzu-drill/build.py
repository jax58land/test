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

VERSION = "0.1"
FONT = "IPAGothic"
FONT_PATH = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"
DISCLAIMER = ("※本書は練習用の教材です。回路はすべてオリジナルで、試験の正式な判定基準は"
              "試験センターの公表資料が優先します。実際の施工の最終判断は有資格者が行ってください。")
DEV_GAP = 18 * mm
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
        text(c, (x1 + x2) / 2 + 2, (y1 + y2) / 2 + 2, cb.spec, 7, (0.25, 0.25, 0.25))
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
        return x + 5 * mm, y + (2.5 if t == "L" else -2.5) * mm
    for l in p.locations:
        for i, d in enumerate(l.devices):
            if d.id == did:
                x, y = P(l)
                x += (i - (len(l.devices) - 1) / 2) * DEV_GAP
                if d.kind == "switch3":
                    return x + (-6 if t == "0" else 6) * mm, y + {"0": 0, "1": 1.3, "3": -1.3}[t] * mm
                return x + (-6 if t in ("W", "1", "a") else 6) * mm, y
    raise KeyError(term)


def net_label(net):
    """接続点の短い名前: N / L / イ（返り線）/ イ1（3路イの1端子どうし）"""
    if net.startswith("R-"):
        return net[2:]
    if net.startswith("T"):
        return net[1:-2] + net[-1]
    return net


def draw_multi(c, p, wires, ox, oy, s):
    P = lambda l: (ox + l.x * s * mm, oy + l.y * s * mm)
    joints = box_joints(p, wires)
    names = sorted(joints, key=lambda j: {"N": 0, "L": 1}.get(j.split(":")[1], 2))
    jxy = {}
    for l in p.locations:
        if l.kind == "box":
            x, y = P(l)
            c.setStrokeColorRGB(0.4, 0.4, 0.4)
            c.setDash(3, 2)
            c.circle(x, y, 13 * mm)
            c.setDash()
            mine = [j for j in names if j.startswith(l.id + ":")]
            for i, j in enumerate(mine):
                jxy[j] = (x + (i - (len(mine) - 1) / 2) * 6 * mm, y + ((i % 2) * 2 - 1) * 3 * mm)
    # 心線
    c.setLineWidth(1.4)
    for w in wires:
        x1, y1 = jxy[w.end_a]
        terms = w.end_b.split("+")
        x2, y2 = terminal_xy(p, terms[0], P)
        c.setStrokeColorRGB(*STROKE[w.color])
        c.line(x1, y1, x2, y2)
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
            c.drawCentredString(x + dx, y - 1 * mm, name + d.label)
            if d.kind == "switch3":
                for t, (tx, ty) in {"0": (-6, 0), "1": (6, 1.3), "3": (6, -1.3)}.items():
                    c.setFillColorRGB(0, 0, 0)
                    c.circle(x + dx + tx * mm, y + ty * mm, 0.6 * mm, fill=1)
                    text(c, x + dx + (tx + (1 if tx > 0 else -2.2)) * mm, y + (ty - 0.8) * mm, t, 5.5,
                         (0.3, 0.3, 0.3))
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
    for i, (j, cols) in enumerate(box_joints(p, wires).items()):
        net = j.split(":")[1]
        if net in ("N", "L"):
            name = {"N": "接地側", "L": "非接地側"}[net]
        elif net.startswith("R-"):
            name = f"返り線（{net[2:]}）"
        else:
            name = f"3路の渡り線（{net[1:-2]}・{net[-1]}端子）"
        text(c, (18 + (i // 3) * 72) * mm, (23.5 - (i % 3) * 4.5) * mm,
             f"・{name}: {len(cols)}本（{'・'.join(cols)}）", 8)
    text(c, 15 * mm, H - 30 * mm, f"【検証済み】全{cases}通りのON/OFFで点灯を検証済み", 7.5, (0.1, 0.45, 0.1))
    text(c, 15 * mm, 8 * mm, DISCLAIMER, 6.5, (0.35, 0.35, 0.35))
    c.showPage()


def cover(c):
    W, H = A4
    text(c, 20 * mm, H - 60 * mm, "第二種電気工事士 技能試験", 16)
    text(c, 20 * mm, H - 75 * mm, "複線図ドリル", 28)
    text(c, 20 * mm, H - 88 * mm, f"試作版 v{VERSION}（{len(PROBLEMS)}問）", 11, (0.4, 0.4, 0.4))
    y = H - 110 * mm
    for s in ["単線図 → 複線図を、毎回同じ7ステップで書けるようにするドリルです。",
              "解答の複線図は、プログラムでスイッチの全ON/OFFを試して点灯を確認済み。",
              "回路はすべてオリジナル（候補問題の図面の転載ではありません）。"]:
        text(c, 20 * mm, y, s, 10)
        y -= 8 * mm
    text(c, 20 * mm, 20 * mm, DISCLAIMER, 7, (0.35, 0.35, 0.35))
    c.showPage()


def main(out=None):
    out = Path(out or Path(__file__).resolve().parent / "preview.pdf")
    out.parent.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(TTFont(FONT, FONT_PATH))
    c = canvas.Canvas(str(out), pagesize=A4)
    c.setTitle("複線図ドリル（試作版）")
    c.setAuthor("")
    cover(c)
    for p in PROBLEMS:
        wires = generate(p)
        cases = verify(p, wires)
        page_problem(c, p, wires, cases)
    c.save()
    return out


if __name__ == "__main__":
    print(main(sys.argv[1] if len(sys.argv) > 1 else None))
