"""apply_urls.py のテスト（一時フォルダで実行）。usage: python tools/test_apply_urls.py"""
import json
import tempfile
from pathlib import Path

from apply_urls import ROOT, SOURCES, apply


def test_all_placeholders_known_and_filled():
    urls = json.loads((ROOT / "content" / "urls.json").read_text(encoding="utf-8"))
    full = {k: f"https://example.booth.pm/items/{i}" for i, k in enumerate(urls) if not k.startswith("_")}
    with tempfile.TemporaryDirectory() as d:
        remaining = apply(full, out_dir=Path(d))
        assert remaining == []
        for src in SOURCES:
            out = (Path(d) / src.relative_to(ROOT / "content")).read_text(encoding="utf-8")
            assert "【URL:" not in out, src.name
        drill = (Path(d) / "note" / "04-free-fukusenzu.md").read_text(encoding="utf-8")
        assert full["複線図ドリル製品版"] in drill and full["複線図ドリル無料版"] in drill
        assert full["計算ツールキット製品版"] not in drill          # ドリルの記事に計算ツールキットのURLが入らない


def test_partial_and_validation():
    urls = json.loads((ROOT / "content" / "urls.json").read_text(encoding="utf-8"))
    part = {k: "" for k in urls}
    part["複線図ドリル製品版"] = "https://a.booth.pm/items/1"
    with tempfile.TemporaryDirectory() as d:
        remaining = apply(part, out_dir=Path(d))
        assert remaining and all(k != "複線図ドリル製品版" for _, k in remaining)
        try:
            apply({**part, "複線図ドリル製品版": "http://bad"}, out_dir=Path(d))
        except ValueError:
            pass
        else:
            raise AssertionError("http:// を検出できない")
        # 元の原稿は書き換えない
        assert "【URL:複線図ドリル製品版】" in (ROOT / "content" / "note" / "04-free-fukusenzu.md").read_text(encoding="utf-8")


if __name__ == "__main__":
    test_all_placeholders_known_and_filled()
    test_partial_and_validation()
    print("ALL PASSED")
