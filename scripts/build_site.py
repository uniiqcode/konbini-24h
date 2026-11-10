"""data/videos.json と site/page.html から、公開するページ _site/ を作る（毎日作り直す）。

使い方: python3 scripts/build_site.py
作るもの（https://uniiqcode.com/konbini-24h/ の下）:
  index.html                      言語を選ぶページ（スマホの言語で振り分ける。検索には出さない）
  <言語>/index.html               すべての動画（言語は ja・ko・zh-tw・en）
  <言語>/<店>/index.html          店ごと（seven・familymart・lawson・multi）
  <言語>/<分類>/index.html        分類ごと（動画が config/site.toml の category_page_min 本以上ある分類だけ）
  sitemap.xml、assets/、manifest.webmanifest
検索エンジンが読めるよう、動画の一覧・タグ・構造化データ（ItemList＋VideoObject）を HTML に書き込む。
絞り込み（食べ物の種類）と並べ替えは JavaScript で行う。店はページを分ける（リンク）。
環境変数 GOATCOUNTER_TOKEN があれば、GoatCounter からページを作った時点までの訪問者数と国別の数を受け取って書く
（受け取れない時は書かずにページを作る）。
"""
import datetime
import html
import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request

import convini

BASE = "/konbini-24h/"          # ページの中のリンクとファイルの場所（uniiqcode.com でも github.io でも同じ）
OUT = convini.ROOT / "_site"
STORE_SLUG = {"seven": "seven", "familymart": "familymart", "lawson": "lawson", "all": "multi"}
STORES = ["seven", "familymart", "lawson", "all"]
CATEGORIES = ["rice", "bread", "hotsnack", "sweets", "snack", "drink", "mixed"]
LANG_ORDER = ["ja", "ko", "zh", "en"]
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
e = html.escape


def today_jst():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date()


def fmt(template, day=None, **kw):
    if day is not None:
        kw.update(m=day.month, d=day.day, month=MONTHS_EN[day.month - 1])
    return template.format(**kw)


def views_text(t, v):
    """再生数を、その言語の言い方にする（例: 570万回、5.7M views）。"""
    if t["path"] == "en":
        if v >= 1_000_000:
            return fmt(t["views_large"], v=f"{v / 1_000_000:.1f}".rstrip("0").rstrip("."))
        if v >= 1000:
            return fmt(t["views_mid"], v=round(v / 1000))
        return fmt(t["views_small"], v=f"{v:,}")
    if v >= 100_000_000:
        return fmt(t["views_large"], v=f"{v / 100_000_000:.1f}".rstrip("0").rstrip("."))
    if v >= 10_000:
        return fmt(t["views_mid"], v=round(v / 10_000))
    return fmt(t["views_small"], v=f"{v:,}")


# ---- 訪問者数（GoatCounter） ----

def goatcounter(site, token, day):
    """(合計, [(国コード, 英語の名前, 人数), ...]) を返す。受け取れなければ None。"""
    end = day.isoformat()

    def get(path, **params):
        q = urllib.parse.urlencode({"start": site["count_from"], "end": end, **params})
        req = urllib.request.Request(f'{site["goatcounter"]}/api/v0/{path}?{q}',
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)

    try:
        total = int(get("stats/total")["total"])
    except urllib.error.HTTPError as err:
        print(f"訪問者数（stats/total）を受け取れなかった: {err} {err.read()[:300].decode('utf-8', 'replace')}", file=sys.stderr)
        return None
    except Exception as err:  # noqa: BLE001  数が取れなくてもページは作る
        print(f"訪問者数（stats/total）を受け取れなかった: {err}", file=sys.stderr)
        return None
    countries = []
    try:   # 国別の数が取れなくても、合計だけは書く
        locs = get("stats/locations", limit=100).get("stats") or []
        countries = [(x.get("id") or "", x.get("name") or x.get("id") or "", int(x.get("count", 0))) for x in locs]
        countries = [c for c in countries if c[0] and c[2] > 0]
        countries.sort(key=lambda c: -c[2])
    except urllib.error.HTTPError as err:
        print(f"国別の数（stats/locations）を受け取れなかった: {err} {err.read()[:300].decode('utf-8', 'replace')}", file=sys.stderr)
    except Exception as err:  # noqa: BLE001
        print(f"国別の数（stats/locations）を受け取れなかった: {err}", file=sys.stderr)
    return total, countries


def flag(code):
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in code.upper()) if len(code) == 2 and code.isalpha() else ""


def visitors_html(t, stats, day):
    if not stats:
        return ""
    total, countries = stats
    shown = countries[:10]
    lis = "".join(f'<li data-cc="{e(c)}">{flag(c)} <span class="cn">{e(n)}</span> <b>{k:,}</b></li>' for c, n, k in shown)
    more = len(countries) - len(shown)
    others = f'<li class="others">{e(fmt(t["visitors_others"], n=more))}</li>' if more > 0 else ""
    asof = day   # ページを作った時点までの数なので、作った日の日付で書く
    ul = f'<ul class="countries">{lis}{others}</ul>' if shown else ""
    return f'<div class="visitors"><p>{e(fmt(t["visitors"], asof, n=f"{total:,}"))}</p>{ul}</div>'


# ---- ページの部品 ----

def page_url(lang_path, sub=""):
    return f'{BASE}{lang_path}/{sub + "/" if sub else ""}'


def abs_url(site, rel):
    return site["url"].rstrip("/") + rel.removeprefix("/konbini-24h")


def card(t, tags, v):
    lb = v["lang"].upper()
    tag_html = "".join(f'<span class="{"f" if k in tags["formats"] else ""}">{e(tags["labels"][k][t["key"]])}</span>'
                       for k in v.get("tags", []) if k in tags["labels"])
    vid = e(v["id"])
    return (f'<li class="card" data-k="{e(v["category"])}" data-v="{v["views"]}" data-d="{e(v["published"])}">'
            f'<a href="https://www.youtube.com/shorts/{vid}" target="_blank" rel="noopener">'
            f'<div class="thumb"><img src="https://i.ytimg.com/vi/{vid}/hqdefault.jpg" alt="" loading="lazy" width="480" height="360">'
            f'<span class="lb">{e(lb)}</span><span class="tag">{e(views_text(t, v["views"]))}</span></div>'
            f'<h3 class="title">{e(v["title"])}</h3></a>'
            f'<div class="tags">{tag_html}</div>'
            f'<div class="meta"><span>{e(t["stores"][v["store"]])}</span><span>{e(v["channel"])}</span>'
            f'<time datetime="{e(v["published"])}">{e(v["published"])}</time></div></li>')


def json_ld(site, t, page_title, rel, videos):
    items = []
    for i, v in enumerate(videos):
        items.append({"@type": "ListItem", "position": i + 1, "item": {
            "@type": "VideoObject", "name": v["title"],
            "description": f'{t["stores"][v["store"]]} / {t["categories"].get(v["category"], "")} / {v["channel"]}',
            "thumbnailUrl": f'https://i.ytimg.com/vi/{v["id"]}/hqdefault.jpg',
            "uploadDate": v["published"], "contentUrl": f'https://www.youtube.com/shorts/{v["id"]}',
            "embedUrl": f'https://www.youtube.com/embed/{v["id"]}'}})
    data = {"@context": "https://schema.org", "@type": "ItemList", "name": page_title,
            "url": abs_url(site, rel), "numberOfItems": len(items), "itemListElement": items}
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def head(site, langs, t, title, description, sub, ld):
    rel = page_url(t["path"], sub)
    alts = "".join(f'<link rel="alternate" hreflang="{langs[k]["hreflang"]}" href="{abs_url(site, page_url(langs[k]["path"], sub))}">\n'
                   for k in LANG_ORDER)
    alts += f'<link rel="alternate" hreflang="x-default" href="{abs_url(site, page_url("en", sub))}">\n'
    first = site["slides"][0]
    return f'''<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{abs_url(site, rel)}">
{alts}<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(t["site_name"])}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{abs_url(site, rel)}">
<meta property="og:image" content="{site["url"]}assets/og.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="{t["og_locale"]}">
<meta name="twitter:card" content="summary_large_image">
<link rel="preload" as="image" href="{BASE}assets/slide-{first}-768.webp" media="(max-width: 700px)">
<link rel="preload" as="image" href="{BASE}assets/slide-{first}-1536.webp" media="(min-width: 701px)">
<script type="application/ld+json">{ld}</script>'''


def hero(site, t):
    figs = []
    for i, s in enumerate(site["slides"]):
        pos = site["slide_position"].get(s, "50%")
        src = "src" if i == 0 else "data-src"
        srcset = "srcset" if i == 0 else "data-srcset"
        extra = ' fetchpriority="high"' if i == 0 else ' loading="lazy"'
        figs.append(f'<figure class="slide{" on" if i == 0 else ""}">'
                    f'<picture><source media="(max-width: 700px)" {srcset}="{BASE}assets/slide-{s}-768.webp">'
                    f'<img {src}="{BASE}assets/slide-{s}-1536.webp" alt="{e(t["slide_alt"][i])}" width="1536" height="1024" '
                    f'style="object-position:{pos} 50%"{extra}></picture>'
                    f'<figcaption>{e(t["captions"][i])}</figcaption></figure>')
    dots = "".join(f'<button type="button" aria-label="{i + 1}"{" aria-current=true" if i == 0 else ""}></button>'
                   for i in range(len(site["slides"])))
    return "".join(figs), dots


def lang_links(langs, t, sub):
    return "".join(f'<a href="{page_url(langs[k]["path"], sub)}" hreflang="{langs[k]["hreflang"]}" lang="{langs[k]["html_lang"]}"'
                   f' data-lang="{langs[k]["path"]}"{" aria-current=page" if k == t["key"] else ""}>{e(langs[k]["name"])}</a>'
                   for k in LANG_ORDER)


def store_chips(t, current):
    out = [f'<a class="chip store" href="{page_url(t["path"])}"{" aria-current=page" if current is None else ""}>{e(t["all"])}</a>']
    for s in STORES:
        out.append(f'<a class="chip store" href="{page_url(t["path"], STORE_SLUG[s])}"'
                   f'{" aria-current=page" if current == s else ""}>{e(t["stores"][s])}</a>')
    return "".join(out)


def cat_chips(t, videos):
    present = [c for c in CATEGORIES if any(v["category"] == c for v in videos)]
    out = [f'<button type="button" class="chip" data-k="" aria-pressed="true">{e(t["all"])}</button>']
    out += [f'<button type="button" class="chip" data-k="{c}" aria-pressed="false">{e(t["categories"][c])}</button>' for c in present]
    return "".join(out)


def js_strings(t):
    keys = ["views_large", "views_mid", "views_small", "ago_today", "ago_days", "count", "empty"]
    return json.dumps({"lang": t["html_lang"], "path": t["path"], **{k: t[k] for k in keys}}, ensure_ascii=False)


def render(template, site, langs, tags, t, videos, *, sub="", title, description, h1, lead, current_store=None,
           show_cats=True, cat_pages=(), visitors="", day):
    # 最初の並びは新しい順（投稿日が同じなら再生数の多い順）。JavaScript の「新しい順」と同じ
    videos = sorted(videos, key=lambda v: (v["published"], v["views"]), reverse=True)
    rel = page_url(t["path"], sub)
    figs, dots = hero(site, t)
    pages = ""
    if cat_pages:
        links = "".join(f'<li><a href="{page_url(t["path"], c)}">{e(t["categories"][c])}</a></li>' for c in cat_pages)
        pages = f'<nav class="pages"><h2>{e(t["pages_label"])}</h2><ul>{links}</ul></nav>'
    back = f'<p class="back"><a href="{page_url(t["path"])}">← {e(t["back_to_all"])}</a></p>' if sub else ""
    rep = {
        "__HTML_LANG__": t["html_lang"],
        "__HEAD__": head(site, langs, t, title, description, sub, json_ld(site, t, title, rel, videos)),
        "__BASE__": BASE,
        "__LANGS__": lang_links(langs, t, sub),
        "__LANG_LABEL__": e(t["lang_label"]),
        "__SLIDES__": figs,
        "__DOTS__": dots,
        "__SITE_NAME__": e(t["site_name"]),
        "__H1__": e(h1),
        "__LEAD__": e(lead),
        "__STORE_LABEL__": e(t["stores_label"]),
        "__STORES__": store_chips(t, current_store),
        "__CAT_LABEL__": e(t["categories_label"]),
        "__CATS__": cat_chips(t, videos) if show_cats else "",
        "__CATS_HIDDEN__": "" if show_cats else " hidden",
        "__SORT_VIEWS__": e(t["sort_views"]),
        "__SORT_NEW__": e(t["sort_new"]),
        "__COUNT__": e(fmt(t["count"], n=len(videos))),
        "__CARDS__": "\n".join(card(t, tags, v) for v in videos),
        "__EMPTY__": e(t["empty"]),
        "__BACK__": back,
        "__PAGES__": pages,
        "__UPDATED__": e(fmt(t["updated"], day)),
        "__VISITORS__": visitors,
        "__FOOTER__": "".join(f"<p>{e(x)}</p>" for x in t["footer"]),
        "__GOATCOUNTER__": site["goatcounter"],
        "__I18N__": js_strings(t),
    }
    out = template
    for k, v in rep.items():
        out = out.replace(k, v)
    return out


def root_page(site, langs):
    alts = "".join(f'<link rel="alternate" hreflang="{langs[k]["hreflang"]}" href="{abs_url(site, page_url(langs[k]["path"]))}">\n'
                   for k in LANG_ORDER)
    alts += f'<link rel="alternate" hreflang="x-default" href="{abs_url(site, page_url("en"))}">\n'
    links = "".join(f'<li><a href="{page_url(langs[k]["path"])}" lang="{langs[k]["html_lang"]}" data-lang="{langs[k]["path"]}">'
                    f'{e(langs[k]["site_name"])} — {e(langs[k]["headline"])}</a></li>' for k in LANG_ORDER)
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KONBINI 24H｜コンビニ24H</title>
<meta name="description" content="{e(langs["en"]["description"])}">
<meta name="robots" content="noindex, follow">
{alts}<link rel="icon" href="{BASE}assets/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="{BASE}assets/apple-touch-icon.png">
<script>
(function () {{
  var saved = null;
  try {{ saved = localStorage.getItem("k24-lang"); }} catch (e) {{}}
  var pick = saved;
  if (!pick) {{
    var ls = navigator.languages || [navigator.language || "en"];
    for (var i = 0; i < ls.length && !pick; i++) {{
      var l = String(ls[i]).toLowerCase();
      if (l.indexOf("ja") === 0) pick = "ja";
      else if (l.indexOf("ko") === 0) pick = "ko";
      else if (l === "zh-tw" || l === "zh-hk" || l === "zh-mo" || l.indexOf("zh-hant") === 0) pick = "zh-tw";
      else if (l.indexOf("zh") === 0) pick = "en";
    }}
  }}
  location.replace("{BASE}" + (pick || "en") + "/");
}})();
</script>
<style>body{{margin:0;font-family:system-ui,sans-serif;background:#F6F5F0;color:#1C2127;display:grid;place-items:center;min-height:100vh}}
main{{padding:24px 16px;max-width:420px;width:100%}}img{{width:240px;height:auto}}ul{{list-style:none;padding:0;display:grid;gap:10px}}
a{{display:block;padding:12px 14px;border-radius:8px;background:#fff;color:inherit;text-decoration:none;border:1px solid #DEDCD3}}</style>
</head>
<body><main><img src="{BASE}assets/logo-a.svg" alt="KONBINI 24H" width="320" height="150">
<ul>{links}</ul></main></body>
</html>
'''


def sitemap(site, langs, entries, day):
    """entries: [sub, ...]（言語ごとに同じページがある）。各 URL に全言語の xhtml:link を付ける。"""
    rows = []
    for sub in entries:
        alts = "".join(f'<xhtml:link rel="alternate" hreflang="{langs[k]["hreflang"]}" href="{abs_url(site, page_url(langs[k]["path"], sub))}"/>'
                       for k in LANG_ORDER)
        alts += f'<xhtml:link rel="alternate" hreflang="x-default" href="{abs_url(site, page_url("en", sub))}"/>'
        for k in LANG_ORDER:
            rows.append(f'  <url><loc>{abs_url(site, page_url(langs[k]["path"], sub))}</loc><lastmod>{day}</lastmod>{alts}</url>')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            + "\n".join(rows) + "\n</urlset>\n")


def manifest():
    return json.dumps({
        "name": "KONBINI 24H", "short_name": "KONBINI 24H",
        "description": "Viral Japan konbini shorts", "start_url": BASE, "scope": BASE, "display": "standalone",
        "background_color": "#F6F5F0", "theme_color": "#14202E",
        "icons": [{"src": f"{BASE}assets/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": f"{BASE}assets/icon-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": f"{BASE}assets/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
    }, ensure_ascii=False, indent=1)


def load_tags():
    cfg = convini.load_toml("tags.toml")
    labels = {t["key"]: t["label"] for t in cfg["items"] + cfg["formats"]}
    return {"labels": labels, "formats": {t["key"] for t in cfg["formats"]}}


def build(out=OUT, stats=None, day=None):
    cfg = convini.load_toml("site.toml")
    site = cfg["site"]
    langs = {k: dict(v, key=k) for k, v in cfg["lang"].items()}
    tags = load_tags()
    for k in LANG_ORDER:   # タグの名前は ja・ko・zh・en
        langs[k]["key"] = k
    videos = convini.load_json(convini.VIDEOS, {"videos": []})["videos"]
    day = day or today_jst()
    template = (convini.ROOT / "site/page.html").read_text(encoding="utf-8")
    cat_pages = [c for c in CATEGORIES if sum(v["category"] == c for v in videos) >= site["category_page_min"]]

    if out.exists():
        shutil.rmtree(out)
    (out / "assets").mkdir(parents=True)
    entries = [""]
    for k in LANG_ORDER:
        t = langs[k]
        vis = visitors_html(t, stats, day)
        common = dict(cat_pages=cat_pages, visitors=vis, day=day)
        pages = [("", render(template, site, langs, tags, t, videos, title=f'{t["site_name"]}｜{t["headline"]}',
                             description=t["description"], h1=t["headline"], lead=t["lead"], **common))]
        for s in STORES:
            name = t["stores"][s]
            vs = [v for v in videos if v["store"] == s]
            pages.append((STORE_SLUG[s], render(
                template, site, langs, tags, t, vs, sub=STORE_SLUG[s], current_store=s,
                title=f'{fmt(t["store_title"], store=name)}｜{t["site_name"]}', description=fmt(t["store_description"], store=name),
                h1=fmt(t["store_title"], store=name), lead=t["lead"], **common)))
        for c in cat_pages:
            name = t["categories"][c]
            vs = [v for v in videos if v["category"] == c]
            pages.append((c, render(
                template, site, langs, tags, t, vs, sub=c, show_cats=False,
                title=f'{fmt(t["category_title"], category=name)}｜{t["site_name"]}', description=fmt(t["category_description"], category=name),
                h1=fmt(t["category_title"], category=name), lead=t["lead"], **common)))
        for sub, page in pages:
            d = out / t["path"] / sub if sub else out / t["path"]
            d.mkdir(parents=True, exist_ok=True)
            (d / "index.html").write_text(page, encoding="utf-8")
            if k == "ja" and sub:
                entries.append(sub)
    (out / "index.html").write_text(root_page(site, langs), encoding="utf-8")
    (out / "sitemap.xml").write_text(sitemap(site, langs, entries, day.isoformat()), encoding="utf-8")
    (out / "manifest.webmanifest").write_text(manifest(), encoding="utf-8")
    for f in (convini.ROOT / "site/assets").iterdir():
        shutil.copy(f, out / "assets" / f.name)
    return {"videos": len(videos), "pages_per_lang": len(entries), "category_pages": cat_pages}


def main():
    cfg = convini.load_toml("site.toml")
    day = today_jst()
    token = os.environ.get("GOATCOUNTER_TOKEN")
    stats = goatcounter(cfg["site"], token, day) if token else None
    info = build(stats=stats, day=day)
    print(f'_site を作った: 動画 {info["videos"]}本、1言語あたり {info["pages_per_lang"]}ページ'
          f'（分類のページ: {", ".join(info["category_pages"]) or "なし"}）、訪問者数: {"あり" if stats else "なし"}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
