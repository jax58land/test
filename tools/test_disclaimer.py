"""免責文（最終判断は有資格者／税務は税理士・税務署）が、すべての商品・記事に入っているか確かめる。

usage: python tools/test_disclaimer.py
CLAUDE.md「免責文（最終判断は有資格者）を全商品・記事に入れる」の自動チェック。
- note記事: 本文に免責文
- 出品文: BOOTHに貼る「コピペ用の枠（```）」の中に免責文（枠の外だけでは出品ページに載らない）
- 販売ファイル: Excel はシートのどこか、PDF は全ページ（PDFの全ページは test_build でも確認）
"""
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = re.compile(r"有資格者|税理士")


def test_note_articles():
    for f in sorted((ROOT / "content" / "note").glob("*.md")):
        assert KEY.search(f.read_text(encoding="utf-8")), f"{f.name}: 免責文がない"


def test_booth_copy_block():
    for f in sorted((ROOT / "content" / "booth").glob("*.md")):
        blocks = re.findall(r"```\n(.*?)```", f.read_text(encoding="utf-8"), re.S)
        assert blocks, f"{f.name}: コピペ用の枠がない"
        assert any(KEY.search(b) for b in blocks), f"{f.name}: コピペ用の枠の中に免責文がない"


def test_dist_files():
    for f in sorted((ROOT / "dist").glob("*.xlsx")):
        with zipfile.ZipFile(f) as z:
            text = "".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist() if n.endswith(".xml"))
        assert KEY.search(text), f"{f.name}: 免責文がない"
    import pymupdf
    for f in sorted((ROOT / "dist").glob("*.pdf")):
        for i, page in enumerate(pymupdf.open(f)):
            assert KEY.search(page.get_text()), f"{f.name} {i + 1}ページ目: 免責文がない"


if __name__ == "__main__":
    test_note_articles()
    test_booth_copy_block()
    test_dist_files()
    print("ALL PASSED")
