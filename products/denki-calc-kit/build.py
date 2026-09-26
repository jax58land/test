"""電気工事 現場計算ツールキット（Excel）を生成する。

usage: python build.py [--lite]
  --lite  無料配布版（電圧降下シートのみ）を生成
出力先: リポジトリ直下の dist/
"""
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

VERSION = "1.0"
FONT = "Meiryo UI"
DIST = Path(__file__).resolve().parents[2] / "dist"

F_BASE = Font(name=FONT, size=10)
F_INPUT = Font(name=FONT, size=10, color="0000FF")
F_BOLD = Font(name=FONT, size=10, bold=True)
F_TITLE = Font(name=FONT, size=14, bold=True)
F_HEAD = Font(name=FONT, size=10, bold=True, color="FFFFFF")
F_NOTE = Font(name=FONT, size=9, color="666666")
FILL_INPUT = PatternFill("solid", fgColor="FFF9C4")
FILL_HEAD = PatternFill("solid", fgColor="37474F")
FILL_OUT = PatternFill("solid", fgColor="E3F2FD")
FILL_NG = PatternFill("solid", fgColor="FFCDD2")
FILL_OK = PatternFill("solid", fgColor="C8E6C9")
THIN = Side(style="thin", color="B0BEC5")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
WRAP = Alignment(vertical="top", wrap_text=True)

DISCLAIMER = (
    "【免責】本ツールは設計・積算の補助を目的とした概算ツールです。最終判断は最新の電気設備技術基準・"
    "同解釈・内線規程・メーカー資料・所轄電力会社の規定に基づき、有資格者が行ってください。"
)


def cell(ws, ref, value=None, font=F_BASE, fill=None, fmt=None, align=None, border=False):
    c = ws[ref]
    if value is not None:
        c.value = value
    c.font = font
    if fill:
        c.fill = fill
    if fmt:
        c.number_format = fmt
    if align:
        c.alignment = align
    if border:
        c.border = BORDER
    return c


def header_row(ws, row, headers, widths=None):
    for i, h in enumerate(headers):
        col = chr(ord("A") + i)
        cell(ws, f"{col}{row}", h, F_HEAD, FILL_HEAD, align=CENTER, border=True)
        if widths:
            ws.column_dimensions[col].width = widths[i]
    ws.row_dimensions[row].height = 32


def legend(ws, ref):
    cell(ws, ref, "凡例: 黄色セル（青字）＝入力欄 ／ 水色セル＝自動計算 ／ それ以外は触らないでください", F_NOTE)


# ---------------------------------------------------------------- 参照表
SIZES_SQ = [2, 3.5, 5.5, 8, 14, 22, 38, 60, 100, 150, 200, 250, 325]

# 電技解釈 第146条 表146-1（軟銅線・周囲温度30℃以下・絶縁物許容温度60℃相当の基準値）
AMPACITY = [
    ("単線 1.6mm", 27), ("単線 2.0mm", 35), ("単線 2.6mm", 48), ("単線 3.2mm", 62),
    ("より線 2mm²", 27), ("より線 3.5mm²", 37), ("より線 5.5mm²", 49), ("より線 8mm²", 61),
    ("より線 14mm²", 88), ("より線 22mm²", 115), ("より線 38mm²", 162),
    ("より線 60mm²", 217), ("より線 100mm²", 298),
]
# 電技解釈 表146-3 電流減少係数（同一管内の電線数）
REDUCTION = [
    ("管に収めない（がいし引き等）", 1.00), ("3本以下", 0.70), ("4本", 0.63), ("5〜6本", 0.56),
    ("7〜15本", 0.49), ("16〜40本", 0.43), ("41〜60本", 0.39), ("61本以上", 0.34),
]
# 電技解釈 第149条 分岐回路の電線太さ・コンセント
BRANCH = [
    ("15A", "直径1.6mm以上", "15A以下"),
    ("20A（配線用遮断器）", "直径1.6mm以上", "20A以下"),
    ("20A（ヒューズ）", "直径2.0mm以上", "20A"),
    ("30A", "直径2.6mm（5.5mm²）以上", "20A以上30A以下"),
    ("40A", "8mm²以上", "30A以上40A以下"),
    ("50A", "14mm²以上", "40A以上50A以下"),
]
# 内線規程 1310-1 幹線・分岐回路の電圧降下（こう長別の目安）
VDROP_LIMIT = [
    ("60m以下", 0.02, 0.03), ("120m以下", 0.04, 0.05),
    ("200m以下", 0.05, 0.06), ("200m超過", 0.06, 0.07),
]
METHODS = [("単相2線式", 35.6), ("単相3線式", 17.8), ("三相3線式", 30.8)]


def build_ref(wb):
    ws = wb.create_sheet("参照表")
    ws.column_dimensions["A"].width = 30
    for col in "BCDEFG":
        ws.column_dimensions[col].width = 16
    cell(ws, "A1", "参照表（計算シートから参照しています。数値を変える場合は最新の基準で確認のうえ）", F_TITLE)

    cell(ws, "A3", "① 配電方式と電圧降下の係数K（e = K×L×I ÷ (1000×A)）", F_BOLD)
    header_row(ws, 4, ["配電方式", "係数K"])
    for i, (m, k) in enumerate(METHODS):
        r = 5 + i
        cell(ws, f"A{r}", m, border=True)
        cell(ws, f"B{r}", k, border=True, fmt="0.0")
    cell(ws, "C5", "単相3線式は中性線と外線の間の降下（平衡負荷）", F_NOTE)

    cell(ws, "A10", "② 標準電線断面積（mm²）", F_BOLD)
    header_row(ws, 11, ["断面積mm²"])
    for i, s in enumerate(SIZES_SQ):
        cell(ws, f"A{12 + i}", s, border=True)
    cell(ws, "B12", "単線の断面積: 1.6mm=2.0 / 2.0mm=3.14 / 2.6mm=5.31 / 3.2mm=8.04 mm²", F_NOTE)

    cell(ws, "A27", "③ 許容電流（電技解釈 表146-1 基準値・周囲温度30℃）", F_BOLD)
    header_row(ws, 28, ["電線", "許容電流A"])
    for i, (n, a) in enumerate(AMPACITY):
        cell(ws, f"A{29 + i}", n, border=True)
        cell(ws, f"B{29 + i}", a, border=True)

    cell(ws, "A44", "④ 電流減少係数（電技解釈 表146-3）", F_BOLD)
    header_row(ws, 45, ["同一管内の電線数", "係数"])
    for i, (n, k) in enumerate(REDUCTION):
        cell(ws, f"A{46 + i}", n, border=True)
        cell(ws, f"B{46 + i}", k, border=True, fmt="0.00")

    cell(ws, "A56", "⑤ 分岐回路（電技解釈 第149条）", F_BOLD)
    header_row(ws, 57, ["過電流遮断器の定格", "電線の太さ", "コンセント定格"])
    for i, row in enumerate(BRANCH):
        for j, v in enumerate(row):
            cell(ws, f"{'ABC'[j]}{58 + i}", v, border=True)

    cell(ws, "A66", "⑥ 電圧降下の目安（内線規程 1310-1）", F_BOLD)
    header_row(ws, 67, ["こう長", "低圧で受電", "変圧器から供給"])
    for i, (l, a, b) in enumerate(VDROP_LIMIT):
        cell(ws, f"A{68 + i}", l, border=True)
        cell(ws, f"B{68 + i}", a, border=True, fmt="0%")
        cell(ws, f"C{68 + i}", b, border=True, fmt="0%")
    cell(ws, "A73", "※こう長は供給点から最遠端の負荷までの電線のこう長。版により改定があるため最新版で確認してください。", F_NOTE)
    return ws


# ---------------------------------------------------------------- 電圧降下
def build_vdrop(wb, rows=20):
    ws = wb.create_sheet("電圧降下")
    cell(ws, "A1", "電圧降下・電線サイズ計算", F_TITLE)
    legend(ws, "A2")
    cell(ws, "A3", "e = K×L×I ÷ (1000×A)　K: 単相2線35.6／単相3線17.8／三相3線30.8（内線規程の簡易式・銅線）", F_NOTE)
    headers = ["回路名", "配電方式", "基準電圧\nV", "電流\nA", "こう長\nm", "電線断面積\nmm²",
               "許容降下率", "係数K", "電圧降下\nV", "降下率", "判定", "必要断面積\nmm²", "推奨サイズ\nmm²"]
    header_row(ws, 5, headers, [18, 13, 9, 9, 9, 11, 10, 8, 10, 9, 8, 11, 11])
    ws.freeze_panes = "B6"

    dv = DataValidation(type="list", formula1="=参照表!$A$5:$A$7", allow_blank=True)
    ws.add_data_validation(dv)
    example = ["例）1F照明", "単相2線式", 100, 12, 35, 3.5, 0.02]
    for r in range(6, 6 + rows):
        for j, col in enumerate("ABCDEFG"):
            c = cell(ws, f"{col}{r}", example[j] if r == 6 else None, F_INPUT, FILL_INPUT, border=True)
            if col == "G":
                c.number_format = "0.0%"
        dv.add(f"B{r}")
        blank = f'OR(B{r}="",D{r}="",E{r}="",F{r}="")'
        cell(ws, f"H{r}", f'=IFERROR(INDEX(参照表!$B$5:$B$7,MATCH(B{r},参照表!$A$5:$A$7,0)),"")',
             fill=FILL_OUT, border=True, fmt="0.0")
        cell(ws, f"I{r}", f'=IF({blank},"",H{r}*E{r}*D{r}/(1000*F{r}))', fill=FILL_OUT, border=True, fmt="0.00")
        cell(ws, f"J{r}", f'=IF(OR(I{r}="",C{r}=""),"",I{r}/C{r})', fill=FILL_OUT, border=True, fmt="0.00%")
        cell(ws, f"K{r}", f'=IF(OR(J{r}="",G{r}=""),"",IF(J{r}<=G{r},"OK","NG"))', fill=FILL_OUT,
             border=True, align=CENTER)
        cell(ws, f"L{r}", f'=IF(OR(H{r}="",D{r}="",E{r}="",C{r}="",G{r}=""),"",H{r}*E{r}*D{r}/(1000*C{r}*G{r}))',
             fill=FILL_OUT, border=True, fmt="0.00")
        cell(ws, f"M{r}", f'=IF(L{r}="","",IF(L{r}>MAX(参照表!$A$12:$A$24),"要検討",'
                          f'INDEX(参照表!$A$12:$A$24,COUNTIF(参照表!$A$12:$A$24,"<"&L{r})+1)))',
             fill=FILL_OUT, border=True, align=CENTER)
    rng = f"K6:K{5 + rows}"
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"NG"'], fill=FILL_NG))
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"OK"'], fill=FILL_OK))
    ws["C5"].comment = Comment("単相3線式は中性線との間の電圧（100V）を入力", "tool")
    ws["G5"].comment = Comment("参照表⑥の内線規程の目安を参考に入力（例: 2%）", "tool")
    ws["M5"].comment = Comment("許容降下率を満たす最小の標準断面積。許容電流の確認は別途「許容電流」シートで。", "tool")
    cell(ws, f"A{7 + rows}", DISCLAIMER, F_NOTE)
    return ws


# ---------------------------------------------------------------- 許容電流
def build_ampacity(wb, rows=15):
    ws = wb.create_sheet("許容電流")
    cell(ws, "A1", "許容電流（電流減少係数・周囲温度補正）", F_TITLE)
    legend(ws, "A2")
    cell(ws, "A3", "許容電流 = 基準値 × 電流減少係数 × 温度補正係数√((60-θ)/30)　（小数点以下1位を7捨8入／ビニル絶縁60℃）", F_NOTE)
    headers = ["回路名", "電線", "同一管内の電線数", "周囲温度\n℃", "負荷電流\nA",
               "基準値\nA", "減少係数", "温度補正", "許容電流\nA", "判定"]
    header_row(ws, 5, headers, [18, 16, 24, 9, 10, 9, 9, 9, 10, 8])
    ws.freeze_panes = "B6"
    dv_w = DataValidation(type="list", formula1="=参照表!$A$29:$A$41", allow_blank=True)
    dv_n = DataValidation(type="list", formula1="=参照表!$A$46:$A$53", allow_blank=True)
    ws.add_data_validation(dv_w)
    ws.add_data_validation(dv_n)
    example = ["例）エアコン回路", "単線 2.0mm", "3本以下", 30, 16]
    for r in range(6, 6 + rows):
        for j, col in enumerate("ABCDE"):
            cell(ws, f"{col}{r}", example[j] if r == 6 else None, F_INPUT, FILL_INPUT, border=True)
        dv_w.add(f"B{r}")
        dv_n.add(f"C{r}")
        cell(ws, f"F{r}", f'=IFERROR(INDEX(参照表!$B$29:$B$41,MATCH(B{r},参照表!$A$29:$A$41,0)),"")',
             fill=FILL_OUT, border=True)
        cell(ws, f"G{r}", f'=IFERROR(INDEX(参照表!$B$46:$B$53,MATCH(C{r},参照表!$A$46:$A$53,0)),"")',
             fill=FILL_OUT, border=True, fmt="0.00")
        cell(ws, f"H{r}", f'=IF(D{r}="",1,IF(D{r}>=60,0,SQRT((60-MAX(D{r},30))/30)))',
             fill=FILL_OUT, border=True, fmt="0.00")
        cell(ws, f"I{r}", f'=IF(OR(F{r}="",G{r}=""),"",INT(ROUNDDOWN(ROUND(F{r}*G{r}*H{r},6),1)+0.2+1E-9))', fill=FILL_OUT, border=True)
        cell(ws, f"J{r}", f'=IF(OR(I{r}="",E{r}=""),"",IF(E{r}<=I{r},"OK","NG"))', fill=FILL_OUT,
             border=True, align=CENTER)
    rng = f"J6:J{5 + rows}"
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"NG"'], fill=FILL_NG))
    ws.conditional_formatting.add(rng, CellIsRule(operator="equal", formula=['"OK"'], fill=FILL_OK))
    ws["C5"].comment = Comment("VVF等ケーブルは内線規程・メーカーの許容電流表を優先してください", "tool")
    cell(ws, f"A{7 + rows}", "※7捨8入: 小数点以下1位が7以下は切り捨て、8以上は切り上げ（例 27×0.70=18.9→19A）", F_NOTE)
    cell(ws, f"A{8 + rows}", DISCLAIMER, F_NOTE)
    return ws


# ---------------------------------------------------------------- 材料拾い
def build_takeoff(wb, items=30, zones=8):
    ws = wb.create_sheet("材料拾い")
    cell(ws, "A1", "材料拾い出し表（部屋・回路ごとに数量を入れると合計と材料費が出ます）", F_TITLE)
    legend(ws, "A2")
    zone_cols = [chr(ord("E") + i) for i in range(zones)]
    total_col = chr(ord(zone_cols[-1]) + 1)
    price_col = chr(ord(total_col) + 1)
    amount_col = chr(ord(price_col) + 1)
    headers = ["品名", "規格", "単位", "ロス率"] + [f"区画{i + 1}" for i in range(zones)] + ["合計数量", "単価\n円", "金額\n円"]
    header_row(ws, 5, headers, [22, 18, 6, 8] + [8] * zones + [10, 10, 12])
    for i in range(zones):
        cell(ws, f"{zone_cols[i]}5", ["1F LDK", "1F 水回り", "2F 洋室", "屋外"][i] if i < 4 else f"区画{i + 1}",
             F_INPUT, FILL_INPUT, align=CENTER, border=True)
    ws.freeze_panes = "E6"
    examples = [
        ("VVFケーブル", "2.0-3C", "m", 0.1, [18, 6, 22, 5]),
        ("VVFケーブル", "1.6-2C", "m", 0.1, [30, 12, 25, 0]),
        ("埋込スイッチ", "片切", "個", 0, [2, 1, 2, 0]),
        ("埋込コンセント", "2口 接地付", "個", 0, [4, 2, 3, 1]),
        ("PF管", "16", "m", 0.05, [0, 0, 0, 8]),
    ]
    prices = [185, 95, 180, 420, 60]
    last = 5 + items
    for r in range(6, last + 1):
        ex = examples[r - 6] if r - 6 < len(examples) else None
        for j, col in enumerate("ABCD"):
            c = cell(ws, f"{col}{r}", ex[j] if ex else None, F_INPUT, FILL_INPUT, border=True)
            if col == "D":
                c.number_format = "0%"
        for i, zc in enumerate(zone_cols):
            v = ex[4][i] if ex and i < len(ex[4]) else None
            cell(ws, f"{zc}{r}", v, F_INPUT, FILL_INPUT, border=True)
        cell(ws, f"{price_col}{r}", prices[r - 6] if ex else None, F_INPUT, FILL_INPUT, border=True, fmt="#,##0")
        zr = f"{zone_cols[0]}{r}:{zone_cols[-1]}{r}"
        cell(ws, f"{total_col}{r}", f'=IF(COUNT({zr})=0,"",ROUNDUP(ROUND(SUM({zr})*(1+N(D{r})),6),0))',
             fill=FILL_OUT, border=True, fmt="#,##0")
        cell(ws, f"{amount_col}{r}", f'=IF(OR({total_col}{r}="",{price_col}{r}=""),"",{total_col}{r}*{price_col}{r})',
             fill=FILL_OUT, border=True, fmt="#,##0")
    cell(ws, f"{price_col}{last + 1}", "材料費計", F_BOLD, align=CENTER, border=True)
    cell(ws, f"{amount_col}{last + 1}", f"=SUM({amount_col}6:{amount_col}{last})", F_BOLD, FILL_OUT, "#,##0", border=True)
    cell(ws, f"A{last + 3}", "※例の単価はダミーです。仕入れ値に置き換えてください。ロス率は切断・端末処理分の割増し。", F_NOTE)
    return ws, f"{amount_col}{last + 1}"


# ---------------------------------------------------------------- 見積書
def build_estimate(wb, takeoff_total_ref, lines=20):
    ws = wb.create_sheet("見積書")
    for col, w in zip("ABCDEFG", [5, 30, 16, 8, 6, 12, 14]):
        ws.column_dimensions[col].width = w
    ws.merge_cells("A1:G1")
    cell(ws, "A1", "御 見 積 書", Font(name=FONT, size=18, bold=True), align=CENTER)
    cell(ws, "A3", "宛先")
    cell(ws, "B3", "○○ 様", F_INPUT, FILL_INPUT)
    cell(ws, "E3", "見積日")
    cell(ws, "F3", None, F_INPUT, FILL_INPUT, fmt="yyyy/mm/dd")
    ws["F3"].value = "=TODAY()"
    cell(ws, "A4", "件名")
    cell(ws, "B4", "○○邸 電気設備工事", F_INPUT, FILL_INPUT)
    cell(ws, "E4", "有効期限")
    cell(ws, "F4", "発行日より30日", F_INPUT, FILL_INPUT)
    cell(ws, "E6", "会社名")
    cell(ws, "F6", "○○電設", F_INPUT, FILL_INPUT)
    cell(ws, "E7", "登録番号")
    cell(ws, "F7", "T0000000000000", F_INPUT, FILL_INPUT)
    ws["E7"].comment = Comment("インボイス（適格請求書発行事業者）の登録番号", "tool")
    cell(ws, "E8", "連絡先")
    cell(ws, "F8", "000-0000-0000", F_INPUT, FILL_INPUT)

    cell(ws, "A6", "御見積金額（税込）", F_BOLD)
    first, last = 12, 12 + lines - 1
    sub_r, tax_r, tot_r = last + 1, last + 2, last + 3
    cell(ws, "B7", f"=G{tot_r}", Font(name=FONT, size=16, bold=True), fmt='"¥"#,##0"-"')

    header_row(ws, 11, ["No", "品名・工事内容", "規格", "数量", "単位", "単価", "金額"])
    ex = [
        ("材料費一式（材料拾い表より）", "", 1, "式", f"=材料拾い!{takeoff_total_ref}"),
        ("配線工事（労務費）", "電工", 2.5, "人工", 25000),
        ("器具取付費", "", 12, "箇所", 1500),
        ("諸経費", "", 1, "式", 8000),
    ]
    for i, r in enumerate(range(first, last + 1)):
        cell(ws, f"A{r}", i + 1, border=True, align=CENTER)
        e = ex[i] if i < len(ex) else None
        cell(ws, f"B{r}", e[0] if e else None, F_INPUT, FILL_INPUT, border=True)
        cell(ws, f"C{r}", e[1] if e else None, F_INPUT, FILL_INPUT, border=True)
        cell(ws, f"D{r}", e[2] if e else None, F_INPUT, FILL_INPUT, border=True)
        cell(ws, f"E{r}", e[3] if e else None, F_INPUT, FILL_INPUT, border=True, align=CENTER)
        cell(ws, f"F{r}", e[4] if e else None, F_INPUT, FILL_INPUT, border=True, fmt="#,##0")
        cell(ws, f"G{r}", f'=IF(OR(D{r}="",F{r}=""),"",ROUND(D{r}*F{r},0))', fill=FILL_OUT, border=True, fmt="#,##0")
    cell(ws, f"F{sub_r}", "小計", F_BOLD, border=True, align=CENTER)
    cell(ws, f"G{sub_r}", f"=SUM(G{first}:G{last})", F_BOLD, FILL_OUT, "#,##0", border=True)
    cell(ws, f"E{tax_r}", 0.1, F_INPUT, FILL_INPUT, "0%", border=True)
    cell(ws, f"F{tax_r}", "消費税", F_BOLD, border=True, align=CENTER)
    cell(ws, f"G{tax_r}", f"=ROUNDDOWN(G{sub_r}*E{tax_r},0)", F_BOLD, FILL_OUT, "#,##0", border=True)
    cell(ws, f"F{tot_r}", "合計", F_BOLD, border=True, align=CENTER)
    cell(ws, f"G{tot_r}", f"=G{sub_r}+G{tax_r}", F_BOLD, FILL_OUT, "#,##0", border=True)
    cell(ws, f"A{tot_r + 2}", "備考", F_BOLD)
    ws.merge_cells(f"B{tot_r + 2}:G{tot_r + 4}")
    cell(ws, f"B{tot_r + 2}", "・既設配線の不良等、追加工事が必要な場合は別途お見積りいたします。", F_INPUT, FILL_INPUT, align=WRAP)
    ws.print_area = f"A1:G{tot_r + 4}"
    ws.page_setup.fitToWidth = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    return ws


# ---------------------------------------------------------------- 使い方
def build_guide(ws, lite):
    ws.title = "使い方"
    ws.column_dimensions["A"].width = 110
    title = "電気工事 現場計算ツールキット" + ("（無料版）" if lite else "")
    cell(ws, "A1", f"{title}  v{VERSION}", F_TITLE)
    lines = [
        "■ 使い方",
        "・黄色セル（青字）に入力すると、水色セルが自動計算されます。1行目の「例）」行は上書きしてOKです。",
        "・プルダウンのあるセルはリストから選んでください。",
        "",
        "■ シート構成",
        "・電圧降下 …… 配電方式・電流・こう長・断面積から電圧降下/降下率を計算し、許容値を満たす推奨サイズを表示",
    ]
    if not lite:
        lines += [
            "・許容電流 …… 電線の許容電流を電流減少係数・周囲温度で補正し、負荷電流とOK/NG判定",
            "・材料拾い …… 部屋/区画ごとの数量からロス率込みの合計数量と材料費を集計",
            "・見積書 …… 材料拾いの材料費を自動で取り込み、税込金額まで計算（インボイス登録番号欄あり）。印刷範囲設定済み",
        ]
    lines += [
        "・参照表 …… 計算に使う係数・基準値の一覧（出典つき）",
        "",
        "■ 計算の根拠",
        "・電圧降下: 内線規程の簡易式 e = K×L×I ÷ (1000×A)（銅線・力率1・平衡負荷を想定）",
    ]
    if not lite:
        lines += ["・許容電流: 電気設備技術基準の解釈 第146条（表146-1, 146-3）、分岐回路: 同 第149条"]
    else:
        lines += [
            "",
            "■ 製品版（有料）にはこちらも入っています",
            "・許容電流の自動判定（電流減少係数・周囲温度補正）",
            "・材料拾い出し表 → 見積書まで自動連動（インボイス対応）",
            "・分岐回路の電線太さ・コンセント定格の早見表",
        ]
    lines += ["", DISCLAIMER]
    for i, t in enumerate(lines):
        cell(ws, f"A{3 + i}", t, F_BOLD if t.startswith("■") else F_BASE, align=WRAP)


def main():
    lite = "--lite" in sys.argv
    wb = Workbook()
    build_guide(wb.active, lite)
    build_vdrop(wb)
    if not lite:
        build_ampacity(wb)
        _, total_ref = build_takeoff(wb)
        build_estimate(wb, total_ref)
    build_ref(wb)
    wb.calculation.fullCalcOnLoad = True  # キャッシュ値なしで保存するため、開いた時に再計算させる
    DIST.mkdir(exist_ok=True)
    name = "denki-calc-kit-lite.xlsx" if lite else "denki-calc-kit.xlsx"
    out = DIST / name
    wb.save(out)
    print(out)


if __name__ == "__main__":
    main()
