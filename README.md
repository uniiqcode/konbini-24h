# コンビニ24H（KONBINI 24H）｜日本のコンビニの人気ショート動画

日本のコンビニを紹介している YouTube ショートを集めて紹介するページ（アプリ）。「業スー酒場」（`uniiqcode/gyosu-sakaba`）と同じ「紹介している動画を紹介する」形。

> 仕様は `docs/spec.md`。経緯は `STATUS.md`。
>
> - リポジトリ: `uniiqcode/konbini-24h`（2026-11-07 に `convini-shorts` から名前を変えた）
> - ページの URL（公開後）: `https://uniiqcode.com/konbini-24h/`（2026-11-08 に uniiqcode の GitHub Pages が独自ドメイン uniiqcode.com になったため。`uniiqcode.github.io/konbini-24h/` からも転送される）

## 方針（今のところ）

| 項目 | 内容 |
|------|------|
| 目的 | バズっている日本のコンビニのショートを、日本を含む世界の人に紹介する |
| 対象の店 | セブン-イレブン・ファミリーマート・ローソン |
| 言語 | 日本語・韓国語・繁体字（台湾）・英語（それ以外）。スマホの言語で切り替え |
| 載せる動画 | 3分以下・投稿90日以内・再生30万回以上・食品だけ・公式チャンネルを除く・1チャンネル5本まで |
| 分類 | 店（3社＋全店）× 食品（6分類＋いろいろ）。タイトルの言葉から中身のタグ（視聴者の言語で表示） |
| 並べ替え | 新しい順・再生数の多い順 |
| 情報源 | YouTube のみ（TikTok は外す）。YouTube Data API v3 |
| 判定 | キーワード（無料。AI の API は使わない） |
| 場所 | GitHub。ページは GitHub Pages、毎日の更新は GitHub Actions（業スー酒場と同じ） |

## 最初の調査（2026-11-07）

言語別の規模感と、再生数の多いショート上位100本の言語の内訳 → `docs/survey-2026-11-07.md`

## ファイル

| 場所 | 中身 |
|---|---|
| `docs/spec.md` | 仕様 |
| `config/rules.toml` | バズの基準と、判定・分類のキーワード |
| `config/sources.toml` | YouTube の検索語 |
| `config/tags.toml` | 中身のタグの辞書（4言語のラベル） |
| `scripts/collect.py` | 集めて `data/videos.json` を作り直す（共通部分は `scripts/convini.py`） |
| `data/videos.json` | ページに載せる動画 |
| `data/exclude.txt` | 人が外した動画の ID |
| `data/candidates.json` | 最後の検索で見つけた動画の ID（`--rejudge` で使う） |
| `tests/` | 判定・分類のテスト（ネットにつながない）。`python3 -m unittest discover -s tests` |
| `scripts/survey_language.py` | 12の言語で「日本のコンビニ」を検索し、本数・ショートの数・音声の言語を集計 |
| `scripts/survey_top100.py` | 再生数の多い順で取り足して、上位100本を言語別に分ける |
| `data/survey/videos.json` | 集めた動画（タイトル・チャンネル・再生数・長さ・音声の言語） |
| `data/survey/top100.json` | 再生数の多いショート上位100本 |
| `docs/` | 調査のまとめ・決めたこと |

## API キー

- キーはコミットしない。Claude Code のクラウド環境では、環境のネットワークシークレット（`www.googleapis.com` / `X-Goog-Api-Key`）からプロキシが自動で入れる
- GitHub Actions で動かす時は Secrets の `YOUTUBE_API_KEY` に入れる（スクリプトは環境変数があればヘッダーに入れる）
- キーは Google Cloud のプロジェクト `convini-shorts` のもの（2026-11-07 に作成。業スー酒場とは無料枠が別）
