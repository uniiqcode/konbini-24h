"""YouTube からバズっているコンビニのショートを集め、data/videos.json を作り直す。

- 新しく検索して見つけた動画と、すでに載っている動画の両方について、再生数などを取り直す
  （YouTube API の規約で、保存した統計は30日以内に取り直す）。
- 基準（config/rules.toml の [buzz]）から外れたもの・data/exclude.txt の動画は落とす。

使い方: python3 scripts/collect.py [--dry-run]
API キー: 環境変数 YOUTUBE_API_KEY があればヘッダー X-Goog-Api-Key に入れる。
Claude Code のクラウド環境では、ネットワークシークレットからプロキシが入れるので不要。
"""
import collections
import datetime
import json
import os
import sys
import urllib.parse
import urllib.request

import convini

API = "https://www.googleapis.com/youtube/v3/"


def get(endpoint, **params):
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    key = os.environ.get("YOUTUBE_API_KEY")
    headers = {"X-Goog-Api-Key": key} if key else {}
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        return json.load(r)


def search(sources, days):
    yt = sources["youtube"]
    after = (convini.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids, units = [], 0
    for group in yt["queries"]:
        for q in group["q"]:
            res = get("search", part="id", type="video", q=q, order=yt["order"], maxResults=yt["max_results"],
                      videoDuration="short", publishedAfter=after, relevanceLanguage=group["lang"])
            units += 100
            ids += [i["id"]["videoId"] for i in res.get("items", []) if i["id"].get("videoId")]
    return list(dict.fromkeys(ids)), units


def details(ids):
    out, units = {}, 0
    for i in range(0, len(ids), 50):
        res = get("videos", part="snippet,contentDetails,statistics", id=",".join(ids[i:i + 50]))
        units += 1
        for v in res.get("items", []):
            s = v["snippet"]
            out[v["id"]] = dict(
                id=v["id"], title=s["title"], desc=s.get("description", ""), channel=s.get("channelTitle", ""),
                channel_id=s.get("channelId", ""), published=s.get("publishedAt", ""),
                audio=s.get("defaultAudioLanguage") or s.get("defaultLanguage") or "",
                seconds=convini.parse_duration(v["contentDetails"].get("duration")),
                views=int(v.get("statistics", {}).get("viewCount", 0)),
            )
    return out, units


def build(found, rules, exclude):
    keep, dropped = [], collections.Counter()
    for v in found.values():
        if v["id"] in exclude:
            dropped["人が外した"] += 1
            continue
        r = rules.judge(v)
        if isinstance(r, str):
            dropped[r] += 1
            continue
        keep.append(dict(id=v["id"], title=v["title"], channel=v["channel"], published=v["published"][:10],
                         views=v["views"], seconds=v["seconds"], **r))
    keep.sort(key=lambda x: -x["views"])
    return keep, dropped


def main():
    dry = "--dry-run" in sys.argv
    rules = convini.Rules()
    sources = convini.load_toml("sources.toml")
    current = convini.load_json(convini.VIDEOS, {"videos": []})["videos"]
    new_ids, u1 = search(sources, rules.buzz["days"])
    ids = list(dict.fromkeys(new_ids + [v["id"] for v in current]))
    found, u2 = details(ids)
    keep, dropped = build(found, rules, convini.load_exclude())
    summary = dict(
        updated=convini.now().strftime("%Y-%m-%dT%H:%M:%SZ"), units=u1 + u2, searched=len(new_ids),
        checked=len(found), kept=len(keep), dropped=dict(dropped.most_common()),
        by_store=dict(collections.Counter(v["store"] for v in keep).most_common()),
        by_category=dict(collections.Counter(v["category"] for v in keep).most_common()),
        by_lang=dict(collections.Counter(v["lang"] for v in keep).most_common()),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    if not dry:
        convini.save_json(convini.VIDEOS, {"summary": summary, "videos": keep})


if __name__ == "__main__":
    main()
