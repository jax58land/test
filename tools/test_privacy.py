"""販売ファイル・出品文・記事に、個人を特定できる情報や作業環境の痕跡が混ざっていないか調べる。

usage: python tools/test_privacy.py
CLAUDE.md「オーナーの個人情報・実名を成果物に入れない（匿名ペンネーム運用）」の自動チェック。
- メールアドレス、GitHubのアカウント名・リポジトリ名、作業環境のパス、セッションURL
- Excel の作成者・最終更新者、PDF の作成者、PNG の埋め込みテキスト
"""
import re
import zipfile
from pathlib import Path

import pymupdf
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "メールアドレス"),
    (re.compile(r"jax58land|github\.com/", re.I), "GitHubのアカウント・URL"),
    (re.compile(r"/home/|/tmp/|C:\\\\Users", re.I), "作業環境のパス"),
    (re.compile(r"claude\.ai/code|session_[0-9A-Za-z]{6,}", re.I), "作業セッションのURL"),
]
ALLOWED = {"noreply@anthropic.com"}   # コミットの記名で使うもの（成果物には出てこない想定だが念のため）


def scan(text, where):
    for pat, label in PATTERNS:
        for m in pat.findall(text):
            if m not in ALLOWED:
                raise AssertionError(f"{where}: {label}らしき文字列 {m!r}")


def xlsx_text(path):
    with zipfile.ZipFile(path) as z:
        return "\n".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist() if n.endswith(".xml"))


def test_dist_files():
    for f in sorted((ROOT / "dist").iterdir()):
        if f.suffix == ".xlsx":
            text = xlsx_text(f)
            scan(text, f.name)
            creator = re.search(r"<dc:creator>(.*?)</dc:creator>", text)
            assert creator is None or creator.group(1) in ("openpyxl", ""), f"{f.name}: 作成者欄 {creator.group(1)!r}"
            assert "<cp:lastModifiedBy>" not in text or "<cp:lastModifiedBy></cp:lastModifiedBy>" in text, f"{f.name}: 最終更新者欄あり"
        elif f.suffix == ".pdf":
            doc = pymupdf.open(f)
            meta = doc.metadata
            assert meta.get("author", "") in ("", None), f"{f.name}: 作成者 {meta.get('author')!r}"
            scan(" ".join(str(v) for v in meta.values()), f"{f.name}（メタデータ）")
            for i, page in enumerate(doc):
                scan(page.get_text(), f"{f.name} {i + 1}ページ目")


def test_content_and_images():
    for f in list((ROOT / "content").rglob("*.md")) + [ROOT / "LAUNCH-QUICK.md"]:
        scan(f.read_text(encoding="utf-8"), str(f.relative_to(ROOT)))
    for f in (ROOT / "content").rglob("*.png"):
        info = Image.open(f).info
        scan(" ".join(str(v) for v in info.values() if isinstance(v, str)), str(f.relative_to(ROOT)))


if __name__ == "__main__":
    test_dist_files()
    test_content_and_images()
    print("ALL PASSED")
