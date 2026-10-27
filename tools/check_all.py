"""全商品のテストをまとめて実行する（出品前・変更後の確認用）。

usage: python3 tools/check_all.py
最初に必要なライブラリが「この Python で」import できるかを確かめ、だめなら直し方を1行で出して止まる。
- 計算ツールキット（dist の xlsx を pycel で検証）
- 複線図ドリル（点灯シミュレーション・誤配線検出・PDF）
- 見積書・請求書（pycel で合計・税・請求書の連動）
- X投稿ネタ（140字以内）
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = [
    ("計算ツールキット", ROOT / "products" / "denki-calc-kit", "test_build.py"),
    ("複線図ドリル", ROOT / "products" / "fukusenzu-drill", "test_build.py"),
    ("見積書・請求書", ROOT / "products" / "estimate-invoice", "test_build.py"),
    ("X投稿ネタ", ROOT / "content" / "x", "posts.py"),
    ("URL差し替え", ROOT / "tools", "test_apply_urls.py"),
    ("説明文の数字と商品の一致", ROOT / "tools", "test_claims.py"),
    ("販売ファイルが最新（作り直しと一致）", ROOT / "tools", "test_dist_fresh.py"),
    ("個人情報・作業環境の痕跡なし", ROOT / "tools", "test_privacy.py"),
    ("免責文（全商品・記事・出品文の枠内）", ROOT / "tools", "test_disclaimer.py"),
]


MODULES = {"openpyxl": "openpyxl", "pycel": "pycel", "reportlab": "reportlab", "pymupdf": "pymupdf", "PIL": "pillow"}


def missing_modules():
    """テストと同じ Python で import できないライブラリ（pip が別の Python に入れた・壊れた PIL など）。"""
    bad = []
    for mod, pkg in MODULES.items():
        r = subprocess.run([sys.executable, "-c", f"import {mod}"], capture_output=True, text=True)
        if r.returncode != 0:
            bad.append((pkg, r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "?"))
    return bad


def main():
    bad = missing_modules()
    if bad:
        for pkg, err in bad:
            print(f"NG  環境: {pkg} が使えない（{err}）")
        pkgs = " ".join(pkg for pkg, _ in bad)
        print(f"→ {sys.executable} -m pip install --ignore-installed {pkgs}  を実行してからやり直す（商品の不具合ではない）")
        return 2
    failed = []
    for name, cwd, script in CHECKS:
        r = subprocess.run([sys.executable, script], cwd=cwd, capture_output=True, text=True)
        ok = r.returncode == 0
        print(f"{'OK ' if ok else 'NG '} {name}")
        if not ok:
            failed.append(name)
            print((r.stdout + r.stderr)[-2000:])
    print("ALL PASSED" if not failed else f"FAILED: {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
