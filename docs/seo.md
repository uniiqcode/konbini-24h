# 検索対策（SEO）と公開

2026-11-09。`uniiqcode/claude-skills` の `seo-uniiqcode` スキルの手順に沿って入れた。正式な URL は **https://uniiqcode.com/konbini-24h/**。

## 入れたもの

| スキルの手順 | 中身 | 場所 |
|---|---|---|
| 1. 正式な URL | `https://uniiqcode.com/konbini-24h/`。canonical・hreflang・OGP・サイトマップ・構造化データはすべてこれ | `config/site.toml` の `url` |
| 2. 中身を HTML に | 動画の一覧（タイトル・リンク・サムネイル・再生数・タグ・店・チャンネル・投稿日）を、ページを作る時に HTML に書き込む。食べ物の種類の絞り込みと並べ替えは JavaScript で出し入れする | `scripts/build_site.py`、`site/page.html` |
| 3. 基本の META | 言語ごとの title・description、canonical、`<html lang>`、h1（絵の上に見える形）、絵の alt・大きさ | `config/site.toml`、`site/page.html` |
| 4. 共有した時の表示 | OGP と X のカード。絵は東京の絵＋ロゴの 1200×630（`assets/og.jpg`） | `scripts/make_assets.py` |
| 5. サイトマップ | `sitemap.xml`。全言語・全ページ、各 URL に全言語の `xhtml:link`、日付は作った日 | `scripts/build_site.py` の `sitemap` |
| 6. 構造化データ | `ItemList` の中に `VideoObject`（名前・説明・サムネイル・投稿日・`contentUrl`・`embedUrl`） | `scripts/build_site.py` の `json_ld` |
| 7. 速さ | 背景の絵は WebP（スマホ用 768px・パソコン用 1536px）。1枚目だけ `preload`、2枚目からは表示する直前に読む。サムネイルは `loading="lazy"`。ロゴは線にした SVG で、ページはフォントを読み込まない | `site/assets/`、`site/page.html` |
| 9. 多言語 | `/ja/`・`/ko/`・`/zh-tw/`・`/en/`。各ページに自分を含む全言語の `hreflang` と `x-default`（英語）。スマホの言語での振り分けは一番上の `/` だけ（`/` は `noindex, follow`）。選んだ言語はそのスマホに覚えさせる | `scripts/build_site.py` の `root_page` |

ページの種類（1言語あたり）: すべての動画、店ごと4つ（`seven`・`familymart`・`lawson`・`multi`）、分類ごと（動画が10本以上ある分類だけ。2026-11-09 は `rice`・`mixed`）。

## 毎朝の更新（`.github/workflows/daily.yml`）

1. 5:40（日本時間）に YouTube から集め直す（約2,400ユニット）。集めた結果は `data` ブランチに記録する（main には PR を作らない）
2. GoatCounter から、数え始めた日からページを作った時点までの訪問者数と国別の数を受け取る（受け取れない日は書かない）
3. ページを作って GitHub Pages に公開する

main のページ・設定・スクリプトが変わった時は、集め直さずにページだけ作り直す（`data` ブランチの結果を使う）。

## 公開する日に人がすること

1. リポジトリを **public** にする（Settings → General の一番下 → Change visibility）
2. Settings → **Pages** の「Build and deployment」の Source を **GitHub Actions** にする
3. Actions → 「毎日の更新と公開」→ **Run workflow** で1回動かす。終わったら https://uniiqcode.com/konbini-24h/ を開いて確かめる
4. ドメイン全体の robots.txt（`uniiqcode/uniiqcode.github.io` の `robots.txt`）に `Sitemap: https://uniiqcode.com/konbini-24h/sitemap.xml` を1行足し、uniiqcode.com のトップの一覧と JSON-LD にもコンビニ24H を足す（スキルの記録5。別のセッションで頼んでよい）
5. **Google Search Console**（`uniiqcode.com` のドメインプロパティは登録済み）で `https://uniiqcode.com/konbini-24h/sitemap.xml` を送信し、「URL 検査」で `https://uniiqcode.com/konbini-24h/ja/` などの登録をリクエストする
6. **Bing Webmaster Tools** は Search Console から取り込む。韓国向けに **Naver Search Advisor**（https://searchadvisor.naver.com/ ）にもサイトを登録し、サイトマップを送る

## 確かめ方

- X の投稿画面や LINE に URL を貼り、東京の絵とロゴ、タイトルが出る
- Google の「リッチリザルト テスト」に `https://uniiqcode.com/konbini-24h/ja/` を入れてエラーがない
- PageSpeed Insights でスマホの LCP が 2.5 秒以内
