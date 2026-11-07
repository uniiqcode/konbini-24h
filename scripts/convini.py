"""convini-shorts の共通部分: 設定とデータの読み書き、キーワードによる判定・分類。"""
import datetime
import json
import pathlib
import re
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
VIDEOS = ROOT / "data/videos.json"     # ページに載せる動画（毎日入れ替わる）
EXCLUDE = ROOT / "data/exclude.txt"    # 人が外したい動画の ID（1行に1つ）

UNSORTED = "unsorted"
MIXED = "mixed"


def load_toml(name):
    with open(CONFIG / name, "rb") as f:
        return tomllib.load(f)


def load_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def load_exclude():
    if not EXCLUDE.exists():
        return set()
    return {line.split("#")[0].strip() for line in EXCLUDE.read_text(encoding="utf-8").splitlines()} - {""}


def now():
    return datetime.datetime.now(datetime.timezone.utc)


# ---- キーワード ----

def _pattern(word):
    """英数字だけの言葉は単語の境目で（複数形の s・es も当てる）、それ以外（かな・漢字・ハングルなど）は部分一致で探す。"""
    w = re.escape(word.lower())
    if re.fullmatch(r"[a-z0-9 .\-/']+", word.lower()):
        return rf"(?<![a-z0-9]){w}(?:s|es)?(?![a-z0-9])"
    return w


class Words:
    def __init__(self, words):
        self.words = list(words)
        self.re = re.compile("|".join(_pattern(w) for w in self.words)) if self.words else None

    def hit(self, text):
        return bool(self.re and self.re.search(text.lower()))

    def found(self, text):
        return [m.group(0) for m in self.re.finditer(text.lower())] if self.re else []


KANA = re.compile(r"[぀-ヿ]")


def detect_lang(title, audio=""):
    """タイトルの文字で言語を決める。ラテン文字だけなら音声言語の設定、それもなければ英語。"""
    t = title.split("#")[0] or title
    for text in (t, title):
        if KANA.search(text):
            return "ja"
        if re.search(r"[가-힯]", text):
            return "ko"
        if re.search(r"[฀-๿]", text):
            return "th"
        if re.search(r"[ăđơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]", text, re.I):
            return "vi"
        if re.search(r"[一-鿿]", text):
            return "zh"
    a = (audio or "").split("-")[0].lower()
    return a if a and a not in ("zxx", "und") else "en"


class Rules:
    def __init__(self, cfg=None):
        cfg = cfg or load_toml("rules.toml")
        self.buzz = cfg["buzz"]
        self.stores = {k: Words(v["words"]) for k, v in cfg["stores"].items() if k != "any"}
        self.any_store = Words(cfg["stores"]["any"]["words"])
        self.japan = Words(cfg["japan"]["words"])
        self.other_stores = Words(cfg["exclude"]["other_stores"])
        self.exclude = Words(cfg["exclude"]["words"])
        self.categories = [(c["key"], c["group"], Words(c["words"])) for c in cfg["categories"]]
        self.mixed = Words(cfg["mixed"]["words"])
        self.groups = {c["key"]: c["group"] for c in cfg["categories"]}
        self.groups[MIXED] = cfg["mixed"]["group"]

    def store(self, title, desc=""):
        """seven / familymart / lawson / all。コンビニの動画でなければ None。
        店名はタイトル（ハッシュタグを含む）だけで見る。概要欄にだけ店名がある動画は、関係ないものが多かったため。"""
        hits = [k for k, w in self.stores.items() if w.hit(title)]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1 or self.any_store.hit(title):
            return "all"
        return None

    def is_japan(self, title, desc=""):
        return bool(KANA.search(title)) or self.japan.hit(title + "\n" + desc)

    def category(self, title, desc=""):
        for text in (title, desc):
            hits = [k for k, _, w in self.categories if w.hit(text)]
            if len(hits) == 1:
                return hits[0]
            if len(hits) > 1:
                return MIXED
        if self.mixed.hit(title):
            return MIXED
        return UNSORTED

    def judge(self, v):
        """v: title, desc, seconds, views, published(ISO)。載せるなら分類を足した dict、外すなら理由の文字列。"""
        title, desc = v["title"], v.get("desc", "")
        b = self.buzz
        if v.get("seconds") is None or v["seconds"] > b["max_seconds"]:
            return "長い"
        published = datetime.datetime.fromisoformat(v["published"].replace("Z", "+00:00"))
        if now() - published > datetime.timedelta(days=b["days"]):
            return "古い"
        if v.get("views", 0) < b["min_views"]:
            return "再生数が少ない"
        store = self.store(title, desc)
        if store is None:
            return "コンビニの動画ではない"
        if not self.is_japan(title, desc):
            return "日本の話か分からない"
        if self.other_stores.hit(title) and not any(w.hit(title) for w in self.stores.values()):
            return "ほかの店"
        if self.exclude.hit(title):
            return "除外の言葉"
        cat = self.category(title, desc)
        return dict(store=store, category=cat, group=self.groups.get(cat, ""), lang=detect_lang(title, v.get("audio")))


def parse_duration(iso):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return None
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s
