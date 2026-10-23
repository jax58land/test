"""全商品のテストをまとめて実行する（出品前・変更後の確認用）。

usage: python tools/check_all.py
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
]


def main():
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
