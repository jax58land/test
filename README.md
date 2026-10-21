# 電気工事 × AI デジタル商品ラボ

電気工事の現場知識をExcelツール・PDF教材にして note / BOOTH で販売する。毎日の自動PDCAで商品を作り、改善する。

## いまの状況（オーナー向け）

**次にやること（1つだけ）: `LAUNCH-QUICK.md` の5ステップで、複線図ドリルを出品（約15分）**
下期の技能試験は2026年12月12日・13日。11月上旬までの出品が目安です。出品したら `pdca/inbox.md` にURLを1行。

| 商品 | 価格（案） | 状態 | 販売ファイル | 出品文 | 商品画像 |
|---|---|---|---|---|---|
| 第二種電気工事士 複線図ドリル（PDF・10問） | ¥980／無料版¥0 | ✅ 出品準備完了・**最優先** | `dist/fukusenzu-drill.pdf`／`-lite.pdf` | `content/booth/fukusenzu-drill.md` | `content/booth/img/fukusenzu-drill*.png` |
| 電気工事 現場計算ツールキット（Excel） | ¥1,480／無料版¥0 | ✅ 出品準備完了 | `dist/denki-calc-kit.xlsx`／`-lite.xlsx` | `content/booth/denki-calc-kit.md` | `content/booth/img/denki-calc-kit*.png` |
| 見積書・請求書（Excel・インボイス対応） | ¥980 | ✅ 出品準備完了（上の2つの後でOK） | `dist/denki-estimate-invoice.xlsx` | `content/booth/denki-estimate-invoice.md` | `content/booth/img/denki-estimate-invoice.png` |

note記事（無料4本・有料1本）とX投稿ネタ30本も用意済み（`content/note/`、`content/x/posts.md`）。
記事のURL欄は、出品URLを `pdca/inbox.md` に書けば自動で差し替えます。

## フォルダ
| 場所 | 中身 |
|---|---|
| `LAUNCH-QUICK.md` | **最短の出品手順（複線図ドリルだけ・15分）** |
| `LAUNCH.md` | 全商品・note記事の出品手順 |
| `dist/` | 販売ファイル（Excel・PDF） |
| `content/` | 出品文・商品画像・note記事・X投稿ネタ |
| `products/` | 商品の生成スクリプトと検証テスト |
| `tools/` | 一括テスト・商品画像生成・URL差し替え |
| `pdca/` | 連絡箱（inbox）・バックログ・数値・学び・日次ログ |
| `docs/` | 事業戦略・調査メモ |
| `CLAUDE.md` | 自動PDCAの運用ルール |

## 品質チェック（開発用）
```bash
pip install openpyxl pycel reportlab pymupdf pillow
python tools/check_all.py   # 全商品のテスト＋記事・出品文の数字と商品の一致
```
