# 調査メモ（2026-10-10）：下期技能試験の日程／リングスリーブの組合せ

## 1. 令和8年度 第二種電気工事士 下期 技能試験の日程
- 結果: **2026年12月12日（土）または12月13日（日）**（試験地ごとにどちらか）
- 根拠:
  - 電気技術者試験センター公式サイト内の検索結果（shiken.or.jp ドメインに限定した検索の要約）: 「技能試験 2026年12月12日（土曜日）または2026年12月13日（日曜日）」。下期の申込は9月3日で締切済み
  - 民間（ユーキャンのコラム、2026/02/12更新）も同じ日付
- 確度: 中〜高。公式PDF（`shiken.or.jp/construction/upload/R08denkounittei2.pdf`）は、この作業環境からは名前解決できず原文を直接読めていない
- 使い方: 商品の本文には日付を書かない（年度で変わるため）。出品・記事公開のタイミングの判断にだけ使う
  → **11月中に出品できれば、試験の約1か月前から練習に使ってもらえる**

## 2. リングスリーブ（E形）の大きさと圧着マーク
- 検索で得た組合せ（メーカー資料の要約と JIS C 2806 の正誤票の要約。一次資料の原文は未確認）:

| 電線 | スリーブ | 圧着マーク |
|---|---|---|
| 1.6mm × 2本 | 小 | ○ |
| 1.6mm × 3〜4本 | 小 | 小 |
| 2.0mm × 2本 | 小 | 小 |
| 2.0mm × 1本 ＋ 1.6mm × 1〜2本 | 小 | 小 |
| 1.6mm × 5〜6本 | 中 | 中 |
| 2.0mm × 3〜4本 | 中 | 中 |
| 2.6mm × 2本 | 中 | 中 |
| 1.6mm × 7本 | 大 | 大 |

- 注意: 正誤票の要約では「1.6×2 は ○小（φ1.6を2本圧着）」とされ、表記（○ と ○小）に揺れがある
- 確度: 中。**商品にはまだ載せない**（品質ルール「自信のない基準値は入れない」）
- 次: 一次資料（JIS C 2806 の付表、試験センターの公表資料、メーカーのカタログ）で原文を確認できたら、
  `products/fukusenzu-drill/circuits.py` の `SHOW_SLEEVE` を True にして解答ページの接続点の表に載せる

## 参照した URL（この環境からは本文を直接取得できなかったものを含む）
- https://www.shiken.or.jp/construction/second/
- https://www.shiken.or.jp/construction/upload/R08denkounittei2.pdf
- https://www.u-can.co.jp/第二種電気工事士/column/column06.html
- https://www2.panasonic.biz/jp/terasu/skill/dictionary/crimpingmark.html
- https://www2.panasonic.biz/jp/terasu/skill/dictionary/ringsleeve.html
- https://webdesk.jsa.or.jp/pdf/errata/jis_c_02806_000_000_2003_cor_1_200310_j_ch.pdf
