"""判定・分類の確かめ。ネットにはつながない。

使い方: python3 -m unittest discover -s tests
"""
import datetime
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import collect  # noqa: E402
import convini  # noqa: E402

R = convini.Rules()


def video(title, desc="", views=500000, days_ago=10, seconds=40, audio=""):
    published = (convini.now() - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return dict(id="x", title=title, desc=desc, views=views, published=published, seconds=seconds, audio=audio)


class Store(unittest.TestCase):
    def test_one_store(self):
        self.assertEqual(R.store("What 7-ELEVEN in JAPAN is REALLY LIKE"), "seven")
        self.assertEqual(R.store("ファミチキの新作がうますぎた【ファミマ新商品】"), "familymart")
        self.assertEqual(R.store("일본 로손 디저트 추천"), "lawson")
        self.assertEqual(R.store("日本全家必買"), "familymart")

    def test_many_or_generic_is_all(self):
        self.assertEqual(R.store("セブンとローソンのプリン比較"), "all")
        self.assertEqual(R.store("Weirdest things at Japanese convenience stores"), "all")
        self.assertEqual(R.store("일본 편의점 꿀조합"), "all")

    def test_not_konbini(self):
        self.assertIsNone(R.store("Tokyo street food tour"))

    def test_word_boundary(self):
        self.assertIsNone(R.store("Top 7110 facts"))


class Judge(unittest.TestCase):
    def test_accepts(self):
        r = R.judge(video("There are two types of rice balls in Japanese convenience stores 🍙"))
        self.assertEqual((r["store"], r["category"], r["group"], r["lang"]), ("all", "rice", "food", "en"))

    def test_buzz_rules(self):
        self.assertEqual(R.judge(video("7-Eleven Japan sandwich", views=5000)), "再生数が少ない")
        self.assertEqual(R.judge(video("7-Eleven Japan sandwich", days_ago=200)), "古い")
        self.assertEqual(R.judge(video("7-Eleven Japan sandwich", seconds=600)), "長い")

    def test_needs_japan(self):
        self.assertEqual(R.judge(video("7-Eleven Thailand toast")), "日本の話か分からない")
        self.assertIsInstance(R.judge(video("セブンの新作スイーツ")), dict)

    def test_other_stores(self):
        self.assertEqual(R.judge(video("일본 편의점 바짝 긴장시킨 GS25 신상품")), "ほかの店")

    def test_categories(self):
        c = lambda t: R.category(t)
        self.assertEqual(c("must try Japanese konbini ice cream"), "sweets")
        self.assertEqual(c("일본 편의점 오뎅 먹어야하는 이유"), "hotsnack")
        self.assertEqual(c("Buying a WHOLE outfit from convenience stores in Japan"), "goods")
        self.assertEqual(c("Japan VS Korean convenience stores"), "culture")
        self.assertEqual(c("Everything I ate at 7-Eleven in Japan!"), "mixed")
        self.assertEqual(c("onigiri and fried chicken"), "mixed")
        self.assertEqual(c("7-Eleven Japan"), "unsorted")


class Tight(unittest.TestCase):
    def test_food_only(self):
        self.assertEqual(R.judge(video("Buying a WHOLE outfit from convenience stores in Japan")), "食品ではない")
        self.assertEqual(R.judge(video("7-Eleven Japan")), "未分類")

    def test_official_channel(self):
        self.assertEqual(R.judge(dict(video("【ローソン】からあげクン"), channel="ローソン（LAWSON)")), "公式チャンネル")

    def test_per_channel_cap(self):
        vids = {str(i): dict(video("セブンの新作アイス", views=400000 + i), id=str(i), channel="同じ", channel_id="") for i in range(7)}
        keep, dropped = collect.build(vids, R, set())
        self.assertEqual(len(keep), R.per_channel)
        self.assertEqual(dropped["同じチャンネルの上限"], 7 - R.per_channel)


    def test_ads_are_excluded(self):
        self.assertEqual(R.judge(video("#PR #ローソン #超ハッピーすぎチャレンジ 弁当")), "除外の言葉")
        self.assertIsInstance(R.judge(video("ローソンのプリンがうまい")), dict)

    def test_description_with_many_categories_is_unsorted(self):
        self.assertEqual(R.category("Could YOU Break STEEL in Japan's Convenience store?", "ramen onigiri ice cream coffee"), "unsorted")
        self.assertEqual(R.category("ローソンの新しいやつ", "ガトーショコラを食べた"), "sweets")


class Fresh(unittest.TestCase):
    def test_new_video_with_momentum_is_accepted(self):
        # 投稿3日で12万回（1日4万回）なら、30万回に届かなくても載せる
        self.assertIsInstance(R.judge(video("セブンの新作アイス", views=120000, days_ago=3)), dict)

    def test_new_video_without_momentum_is_rejected(self):
        self.assertEqual(R.judge(video("セブンの新作アイス", views=50000, days_ago=3)), "再生数が少ない")

    def test_older_video_needs_min_views(self):
        # 投稿20日なら、1日あたりが多くても30万回が必要
        self.assertEqual(R.judge(video("セブンの新作アイス", views=290000, days_ago=20)), "再生数が少ない")


class Tags(unittest.TestCase):
    def test_items_and_format(self):
        self.assertEqual(R.tags("【セブン】SNSで話題の新作アイス食べてみた正直な感想🍫"), ["icecream", "controversy"])
        self.assertEqual(R.tags("Can you finish this MASSIVE pasta from Japanese 7-Eleven?"), ["pasta", "bigeat"])
        self.assertEqual(R.tags("일본 편의점에서 발견한 말차 치즈케이크"), ["cake", "matcha"])

    def test_japan_is_not_bread(self):
        self.assertNotIn("bread", R.tags("セブン-イレブン・ジャパンの新商品"))


class Lang(unittest.TestCase):
    def test_detect(self):
        self.assertEqual(convini.detect_lang("セブンの新作"), "ja")
        self.assertEqual(convini.detect_lang("일본 편의점"), "ko")
        self.assertEqual(convini.detect_lang("日本超商必買"), "zh")
        self.assertEqual(convini.detect_lang("Thiết kế tiện lợi ở Nhật"), "vi")
        self.assertEqual(convini.detect_lang("Les konbinis au Japon", "fr"), "fr")
        self.assertEqual(convini.detect_lang("7-Eleven in Japan"), "en")


class Build(unittest.TestCase):
    def test_exclude_and_sort(self):
        a = dict(video("7-Eleven Japan ice cream", views=300000), id="a", channel="c", channel_id="")
        b = dict(video("ローソンのからあげクン", views=900000), id="b", channel="c", channel_id="")
        c = dict(video("FamilyMart Japan coffee"), id="c", channel="c", channel_id="")
        keep, dropped = collect.build({"a": a, "b": b, "c": c}, R, {"c"})
        self.assertEqual([v["id"] for v in keep], ["b", "a"])
        self.assertEqual(dropped["人が外した"], 1)


if __name__ == "__main__":
    unittest.main()
