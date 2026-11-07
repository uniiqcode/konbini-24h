"""YouTube で「日本のコンビニ」を紹介する短尺動画の規模感を、言語別に数える。

API キー: 環境変数 YOUTUBE_API_KEY があればヘッダー X-Goog-Api-Key に入れる。
Claude Code のクラウド環境では、ネットワークシークレットがプロキシで自動的に入るので不要。
使い方: python3 scripts/survey_language.py [1検索語あたりのページ数(既定1)]
クォータ: search.list 100 ユニット/回, videos.list 1 ユニット/回。既定（1ページ）で約 1,900 ユニット。

出力:
  - estimate: search.list の pageInfo.totalResults（YouTube の概算値。粗いが規模感の目安）
  - sampled:  実際に取得できた動画数（search は 1 クエリ最大 ~500 件まで）
  - shorts:   そのうち 60 秒以下（Shorts とみなす）の本数
  - audio_lang: 取得した動画の defaultAudioLanguage の内訳（実際の使用言語の目安）
"""
import json, os, re, sys, urllib.parse, urllib.request
from collections import Counter

API = "https://www.googleapis.com/youtube/v3/"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "survey", "videos.json")
PAGES = int(sys.argv[1]) if len(sys.argv) > 1 else 1  # 1 クエリあたり 50 件 × PAGES

# 言語ごとの検索語（「日本のコンビニ」を各言語で）。relevanceLanguage で寄せる。
QUERIES = {
    "ja": ["コンビニ 新商品", "コンビニ スイーツ", "セブンイレブン 新作"],
    "en": ["japanese konbini", "japan convenience store", "7-eleven japan"],
    "zh-Hans": ["日本便利店"],
    "zh-Hant": ["日本便利商店"],
    "ko": ["일본 편의점"],
    "th": ["ร้านสะดวกซื้อญี่ปุ่น"],
    "vi": ["cửa hàng tiện lợi Nhật Bản"],
    "id": ["minimarket jepang"],
    "es": ["konbini japón", "tienda de conveniencia japón"],
    "pt": ["loja de conveniência japão"],
    "fr": ["konbini japon", "supérette japon"],
    "de": ["japanischer konbini"],
}


def get(endpoint, **params):
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    headers = {"X-Goog-Api-Key": os.environ["YOUTUBE_API_KEY"]} if os.environ.get("YOUTUBE_API_KEY") else {}
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        return json.load(r)


def seconds(iso):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return None
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def run():
    rows, all_videos = [], {}
    for lang, qs in QUERIES.items():
        for q in qs:
            ids, estimate, token = [], None, None
            for _ in range(PAGES):
                p = dict(part="id", type="video", q=q, videoDuration="short",
                         relevanceLanguage=lang, maxResults=50)
                if token:
                    p["pageToken"] = token
                res = get("search", **p)
                estimate = estimate or res.get("pageInfo", {}).get("totalResults")
                ids += [i["id"]["videoId"] for i in res.get("items", [])]
                token = res.get("nextPageToken")
                if not token:
                    break
            rows.append(dict(lang=lang, q=q, estimate=estimate, ids=ids))
            print(f"{lang:8} {q:32} estimate={estimate} got={len(ids)}", file=sys.stderr)

    need = {i for r in rows for i in r["ids"]}
    need = list(need)
    for k in range(0, len(need), 50):
        res = get("videos", part="snippet,contentDetails,statistics", id=",".join(need[k:k + 50]))
        for v in res.get("items", []):
            all_videos[v["id"]] = dict(
                sec=seconds(v["contentDetails"].get("duration")),
                audio=(v["snippet"].get("defaultAudioLanguage") or "unknown").split("-")[0],
                views=int(v.get("statistics", {}).get("viewCount", 0)),
                title=v["snippet"]["title"],
                channel=v["snippet"]["channelTitle"],
            )

    out = []
    for r in rows:
        vids = [all_videos[i] for i in r["ids"] if i in all_videos]
        shorts = [v for v in vids if v["sec"] is not None and v["sec"] <= 60]
        out.append(dict(
            lang=r["lang"], q=r["q"], estimate=r["estimate"], sampled=len(vids),
            shorts=len(shorts),
            audio_lang=dict(Counter(v["audio"] for v in vids).most_common(5)),
            median_views=sorted(v["views"] for v in vids)[len(vids) // 2] if vids else 0,
        ))

    uniq = list(all_videos.values())
    summary = dict(
        unique_videos=len(uniq),
        unique_shorts_60s=sum(1 for v in uniq if v["sec"] is not None and v["sec"] <= 60),
        audio_lang_all=dict(Counter(v["audio"] for v in uniq).most_common()),
    )
    json.dump(dict(by_query=out, summary=summary, videos=all_videos),
              open(OUT, "w"), ensure_ascii=False, indent=1)
    for o in out:
        print(json.dumps(o, ensure_ascii=False))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    run()
