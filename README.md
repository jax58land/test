# 電気工事 × AI デジタル商品ラボ

電気工事の現場知識をExcelツール・ガイドにして note / BOOTH で販売する。毎日の自動PDCAで商品を増やし改善する。

| 場所 | 中身 |
|---|---|
| `LAUNCH.md` | **オーナーの出品手順（まずここ）** |
| `docs/strategy.md` | 事業戦略・パラメータ・リスク |
| `dist/` | 販売ファイル（Excel） |
| `products/` | 商品の生成スクリプトと検証テスト |
| `content/` | BOOTH出品文・note記事原稿 |
| `pdca/` | バックログ・数値・学び・日次ログ・連絡箱 |
| `CLAUDE.md` | 自動PDCAの運用ルール |

## 商品の再生成
```bash
pip install openpyxl pycel
cd products/denki-calc-kit && python build.py && python build.py --lite && python test_build.py
```
