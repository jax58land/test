"""記事・投稿の【URL:商品名】を content/urls.json の URL に差し替えて content/ready/ に書き出す。

usage: python tools/apply_urls.py
- 元の原稿（content/note, content/x/posts.md）は書き換えない（URL が変わっても何度でも作り直せる）
- URL が空のキーは差し替えずに残し、残った場所を一覧で表示する
- urls.json にない名前の【URL:…】があればエラー（書き間違いの検出）
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = re.compile(r"【URL:([^】]+)】")
SOURCES = sorted((ROOT / "content" / "note").glob("*.md")) + [ROOT / "content" / "x" / "posts.md"]


def apply(urls, sources=SOURCES, out_dir=ROOT / "content" / "ready", root=ROOT / "content"):
    keys = {k for k in urls if not k.startswith("_")}
    remaining = []
    for src in sources:
        text = src.read_text(encoding="utf-8")
        unknown = set(PLACEHOLDER.findall(text)) - keys
        if unknown:
            raise ValueError(f"{src.name}: urls.json にない名前 {sorted(unknown)}")

        def fill(m):
            url = urls.get(m.group(1), "").strip()
            if not url:
                remaining.append((src.name, m.group(1)))
                return m.group(0)
            if not url.startswith("https://"):
                raise ValueError(f"{m.group(1)}: https:// で始まる URL を入れてください（{url}）")
            return url

        dst = out_dir / src.relative_to(root)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(PLACEHOLDER.sub(fill, text), encoding="utf-8")
    return remaining


def main():
    urls = json.loads((ROOT / "content" / "urls.json").read_text(encoding="utf-8"))
    remaining = apply(urls)
    print(f"content/ready/ に書き出しました。未入力のまま残った場所: {len(remaining)}")
    for name, key in remaining:
        print(f"  - {name}: 【URL:{key}】")
    return 0


if __name__ == "__main__":
    sys.exit(main())
