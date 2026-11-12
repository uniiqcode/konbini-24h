"""ページ作り（scripts/build_site.py）の確かめ。ネットにはつながない。

使い方: python3 -m unittest discover -s tests
"""
import datetime
import json
import pathlib
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import build_site  # noqa: E402

DAY = datetime.date(2026, 11, 9)
STATS = (1234, [("JP", "Japan", 500), ("US", "United States", 200), ("KR", "South Korea", 100), ("TW", "Taiwan", 90),
                ("FR", "France", 50), ("DE", "Germany", 40), ("GB", "United Kingdom", 30), ("TH", "Thailand", 20),
                ("VN", "Vietnam", 10), ("ID", "Indonesia", 5), ("BR", "Brazil", 3), ("CA", "Canada", 2)])


class Build(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = pathlib.Path(cls.tmp.name) / "_site"
        cls.info = build_site.build(out=cls.out, stats=STATS, day=DAY)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, rel):
        return (self.out / rel).read_text(encoding="utf-8")

    def test_pages_for_every_language(self):
        for lang in ("ja", "ko", "zh-tw", "en"):
            for sub in ("", "seven/", "familymart/", "lawson/", "multi/"):
                self.assertTrue((self.out / lang / sub / "index.html").exists(), f"{lang}/{sub}")

    def test_category_pages_only_when_enough_videos(self):
        for c in self.info["category_pages"]:
            self.assertTrue((self.out / "ja" / c / "index.html").exists())
        for c in set(build_site.CATEGORIES) - set(self.info["category_pages"]):
            self.assertFalse((self.out / "ja" / c).exists())

    def test_seo_head(self):
        page = self.read("ko/seven/index.html")
        self.assertIn('<html lang="ko">', page)
        self.assertIn('<link rel="canonical" href="https://uniiqcode.com/konbini-24h/ko/seven/">', page)
        for hl, path in (("ja", "ja"), ("ko", "ko"), ("zh-Hant-TW", "zh-tw"), ("en", "en"), ("x-default", "en")):
            self.assertIn(f'hreflang="{hl}" href="https://uniiqcode.com/konbini-24h/{path}/seven/"', page)
        self.assertIn('content="https://uniiqcode.com/konbini-24h/assets/og.jpg"', page)
        self.assertNotIn("github.io", page)

    def test_cards_and_json_ld_are_in_html(self):
        page = self.read("ja/index.html")
        cards = re.findall(r'<li class="card"', page)
        self.assertEqual(len(cards), self.info["videos"])
        ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S).group(1))
        self.assertEqual(ld["@type"], "ItemList")
        self.assertEqual(ld["numberOfItems"], self.info["videos"])
        self.assertEqual(ld["itemListElement"][0]["item"]["@type"], "VideoObject")

    def test_newest_first(self):
        page = self.read("ja/index.html")
        dates = re.findall(r'<li class="card"[^>]*data-d="([0-9-]+)"', page)
        self.assertEqual(dates, sorted(dates, reverse=True))
        self.assertIn('data-s="new" aria-pressed="true"', page)

    def test_store_page_has_only_that_store(self):
        page = self.read("en/lawson/index.html")
        stores = re.findall(r'<div class="meta"><span>([^<]+)</span>', page)
        self.assertTrue(stores)
        self.assertEqual(set(stores), {"Lawson"})

    def test_root_redirects_and_is_not_indexed(self):
        page = self.read("index.html")
        self.assertIn('content="noindex, follow"', page)
        self.assertIn("location.replace", page)

    def test_sitemap(self):
        xml = self.read("sitemap.xml")
        locs = re.findall(r"<loc>([^<]+)</loc>", xml)
        self.assertEqual(len(locs), 4 * self.info["pages_per_lang"])
        self.assertIn("https://uniiqcode.com/konbini-24h/zh-tw/", locs)
        self.assertIn("<lastmod>2026-11-09</lastmod>", xml)

    def test_visitors_top10_and_others(self):
        page = self.read("ja/index.html")
        self.assertIn("これまでの訪問者 1,234人（11月9日時点）", page)
        self.assertEqual(len(re.findall(r'<li data-cc="', page)), 10)
        self.assertIn("ほか 2か国", page)

    def test_previous_visitors_keep_their_date(self):
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / "_site"
            build_site.build(out=out, stats=(50, [("JP", "Japan", 50)], datetime.date(2026, 11, 7)), day=DAY)
            self.assertIn("これまでの訪問者 50人（11月7日時点）", (out / "ja/index.html").read_text(encoding="utf-8"))

    def test_no_visitors_when_not_available(self):
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d) / "_site"
            build_site.build(out=out, stats=None, day=DAY)
            self.assertNotIn('class="visitors"', (out / "en/index.html").read_text(encoding="utf-8"))


class Format(unittest.TestCase):
    def test_views(self):
        t = {"path": "ja", "views_large": "{v}億回", "views_mid": "{v}万回", "views_small": "{v}回"}
        self.assertEqual(build_site.views_text(t, 5703015), "570万回")
        t = {"path": "en", "views_large": "{v}M views", "views_mid": "{v}K views", "views_small": "{v} views"}
        self.assertEqual(build_site.views_text(t, 5703015), "5.7M views")
        self.assertEqual(build_site.views_text(t, 330000), "330K views")

    def test_flag(self):
        self.assertEqual(build_site.flag("JP"), "🇯🇵")
        self.assertEqual(build_site.flag(""), "")


if __name__ == "__main__":
    unittest.main()
