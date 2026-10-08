"""BOOTH の商品画像（サムネイル）を dist/ の販売ファイルから自動で作る。

usage: python tools/thumbnails.py   → content/booth/img/*.png（1200×1200）
- 計算ツールキット: 販売する xlsx を pycel で計算させ、その値で「電圧降下」シートの見本表を描く
- 複線図ドリル: 販売する PDF の解答ページをそのまま切り出して載せる
価格は画像に入れない（オーナーが出品時に決めるため）。
"""
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont
from pycel import ExcelCompiler

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
OUT = ROOT / "content" / "booth" / "img"
FONT = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"
SIZE = 1200
NAVY, ACCENT, GRAY, LIGHT = (24, 39, 66), (240, 180, 40), (90, 90, 90), (244, 246, 250)


def font(px):
    return ImageFont.truetype(FONT, px)


def base(title, sub, bullets, lite):
    img = Image.new("RGB", (SIZE, SIZE), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, SIZE, 300], fill=NAVY)
    d.text((60, 55), sub, font=font(40), fill=(200, 210, 230))
    d.text((60, 120), title, font=font(78), fill="white")
    if lite:
        d.rounded_rectangle([SIZE - 300, 40, SIZE - 50, 120], 18, fill=ACCENT)
        d.text((SIZE - 268, 55), "無料版", font=font(50), fill=NAVY)
    y = 335
    for b in bullets:
        d.ellipse([62, y + 14, 82, y + 34], fill=ACCENT)
        d.text((100, y), b, font=font(42), fill=NAVY)
        y += 66
    return img, d, y + 20


def calc_kit(lite):
    name = "denki-calc-kit-lite.xlsx" if lite else "denki-calc-kit.xlsx"
    xl = ExcelCompiler(filename=str(DIST / name))
    ev = lambda r: xl.evaluate(f"電圧降下!{r}")
    bullets = (["電圧降下・降下率をすぐ計算", "許容降下率でOK/NGを色分け", "推奨サイズ（mm²）まで自動表示"] if lite else
               ["電圧降下・許容電流（7捨8入まで自動）", "材料拾い → 材料費 → 見積書が連動", "インボイス登録番号欄つき・マクロ不使用"])
    img, d, y = base("現場計算ツールキット", "電気工事の計算を Excel で", bullets, lite)
    # 見本表（販売ファイルを計算させた値）
    heads = ["回路", "方式", "電流", "こう長", "断面積", "降下率", "判定", "推奨"]
    row = [ev("A6"), ev("B6"), f"{ev('D6')}A", f"{ev('E6')}m", f"{ev('F6')}mm²", f"{ev('J6') * 100:.2f}%",
           ev("K6"), f"{ev('M6')}mm²"]
    widths = [190, 175, 105, 115, 145, 135, 95, 140]
    x0, y0, h = 50, y + 30, 90
    d.text((x0, y0 - 55), "電圧降下シート（入力例）", font=font(36), fill=GRAY)
    x = x0
    for w, t, v in zip(widths, heads, row):
        d.rectangle([x, y0, x + w, y0 + h], fill=NAVY, outline="white")
        d.text((x + 12, y0 + 25), t, font=font(32), fill="white")
        fill = (255, 205, 205) if v == "NG" else (230, 245, 230) if v == "OK" else (255, 250, 210) if t in heads[:5] else LIGHT
        d.rectangle([x, y0 + h, x + w, y0 + 2 * h + 30], fill=fill, outline=(200, 200, 200))
        d.text((x + 10, y0 + h + 35), str(v), font=font(28 if len(str(v)) > 6 else 32), fill=NAVY)
        x += w
    d.text((x0, y0 + 2 * h + 60), "黄色いセルに入れるだけ。NG なら赤、推奨サイズも自動。", font=font(34), fill=GRAY)
    # 下段のカード（これも販売ファイルを計算させた値）
    if lite:
        cards = [("1シートで", "20回路まで一覧"), ("配電方式", "単相2線/単相3線/三相3線")]
    else:
        amp = xl.evaluate("許容電流!I6")
        cards = [(f"許容電流 {xl.evaluate('許容電流!B6')}・{xl.evaluate('許容電流!C6')}", f"{amp}A（7捨8入）"),
                 ("見積書の合計（入力例）", f"¥{xl.evaluate('見積書!G34'):,.0f}")]
    cy = y0 + 2 * h + 140
    cw = (SIZE - 100 - 30) // 2
    for i, (label, value) in enumerate(cards):
        cx = 50 + i * (cw + 30)
        d.rounded_rectangle([cx, cy, cx + cw, cy + 170], 20, fill=LIGHT, outline=(215, 220, 230), width=2)
        d.text((cx + 28, cy + 25), label, font=font(30), fill=GRAY)
        d.text((cx + 28, cy + 80), value, font=font(44 if len(value) < 14 else 34), fill=NAVY)
    return img


def drill(lite):
    name = "fukusenzu-drill-lite.pdf" if lite else "fukusenzu-drill.pdf"
    doc = pymupdf.open(DIST / name)
    bullets = (["7ステップで複線図が書ける解説", "問題2問（問題ページ＋解答ページ）", "全問、点灯をプログラムで検証済み"] if lite else
               ["10問：3路・パイロットランプ・ボックス2個", "解説3ページ＋書き込み用の方眼", "全問、点灯をプログラムで検証済み"])
    img, d, y = base("複線図ドリル", "第二種電気工事士 技能試験", bullets, lite)
    # 解答ページを切り出して貼る（製品版: 問題9 = ボックス2個の解答 23ページ目 / 無料版: 問題1 の解答 4ページ目）
    page = doc[22 if not lite else 3]
    assert "解答" in page.get_text()
    pix = page.get_pixmap(dpi=130, clip=pymupdf.Rect(20, 195, 575, 590))
    shot = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    box_w, box_h = SIZE - 100, SIZE - y - 40
    shot.thumbnail((box_w, box_h))
    px = (SIZE - shot.width) // 2
    d.rectangle([px - 4, y - 4, px + shot.width + 4, y + shot.height + 4], outline=(210, 210, 210), width=3)
    img.paste(shot, (px, y))
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    made = []
    for lite in (False, True):
        for fn, stem in ((calc_kit, "denki-calc-kit"), (drill, "fukusenzu-drill")):
            path = OUT / f"{stem}{'-lite' if lite else ''}.png"
            fn(lite).save(path)
            made.append(path)
    return made


if __name__ == "__main__":
    for p in main():
        print(p)
