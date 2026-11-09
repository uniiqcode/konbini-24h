"""ロゴ・アイコン・共有用の絵・背景の絵を作る（最初に1回、またはデザインを変えた時に手で実行する）。

使い方: python3 scripts/make_assets.py <Archivo Black のフォント（.woff2/.woff/.ttf）>
  フォントは npm の @fontsource/archivo-black にある（SIL Open Font License）。文字は線（アウトライン）にして
  SVG に入れるので、ページはフォントを読み込まない。
作るもの（site/assets/）:
  logo-a.svg            ページ上部のロゴ（案A: 白い看板＋からし色の帯に 24H）
  icon.svg              アイコン（案C: からし色の正方形、KONBINI と大きな 24H）
  icon-*.png, apple-touch-icon.png, favicon-32.png, favicon.ico   アイコンの各サイズ（Playwright で描く）
  og.jpg                SNS で共有した時の絵（1200×630。東京の絵＋ロゴ）
  slide-*-1536.webp / slide-*-768.webp   背景のスライドショー（design/slide-*.webp を縮める）
"""
import io
import pathlib
import sys

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "site/assets"
MUSTARD, INK = "#E5B000", "#1C2127"
SLIDES = ["tokyo", "kyoto", "fuji", "slope"]


def text_path(font, text, x, y, size, width=None, anchor="middle"):
    """文字列を SVG の path（d）にする。x,y は基準線の位置。width を渡すとその幅に縮める。"""
    gs, cmap, hmtx = font.getGlyphSet(), font.getBestCmap(), font["hmtx"]
    upm = font["head"].unitsPerEm
    names = [cmap[ord(c)] for c in text]
    adv = sum(hmtx[n][0] for n in names)
    scale = size / upm
    sx = scale * (width / (adv * scale)) if width else scale
    total = adv * sx
    start = x - total / 2 if anchor == "middle" else x
    pen = SVGPathPen(gs)
    cur = 0
    for n in names:
        tp = TransformPen(pen, (sx, 0, 0, -scale, start + cur * sx, y))
        gs[n].draw(tp)
        cur += hmtx[n][0]
    return pen.getCommands()


def icon_small(font):
    """小さいアイコン（タブ用の32px）: KONBINI は小さすぎて読めないので 24H だけ。"""
    h = text_path(font, "24H", 256, 330, 230, width=440)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="24H">
<rect width="512" height="512" fill="{MUSTARD}"/>
<path d="{h}" fill="{INK}"/>
</svg>
'''


def logo_a(font):
    k = text_path(font, "KONBINI", 160, 64, 40, width=236)
    h = text_path(font, "24H", 160, 128, 40, width=96)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 150" role="img" aria-label="KONBINI 24H">
<rect x="10" y="10" width="300" height="130" rx="14" fill="#fff"/>
<path d="M10 86h300v40a14 14 0 0 1-14 14H24a14 14 0 0 1-14-14z" fill="{MUSTARD}"/>
<path d="{k}" fill="{INK}"/><path d="{h}" fill="{INK}"/>
</svg>
'''


def icon(font):
    k = text_path(font, "KONBINI", 256, 150, 64, width=330)
    h = text_path(font, "24H", 256, 372, 200, width=400)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="KONBINI 24H">
<rect width="512" height="512" fill="{MUSTARD}"/>
<path d="{k}" fill="{INK}"/><path d="{h}" fill="{INK}"/>
</svg>
'''


def render_pngs(icon_svg, logo_svg, small_svg):
    """アイコンと共有用の絵を、Node の Playwright（Chromium）で描いて保存する。"""
    import json
    import subprocess
    import tempfile
    tokyo = (ROOT / "design/slide-tokyo.webp").resolve().as_uri()
    jobs = []
    tmp = pathlib.Path(tempfile.mkdtemp())
    for name, size, pad in [("icon-512.png", 512, 0), ("icon-192.png", 192, 0), ("apple-touch-icon.png", 180, 0),
                            ("favicon-32.png", 32, 0), ("icon-maskable-512.png", 512, 0.1)]:
        inner = int(size * (1 - 2 * pad))
        svg = small_svg if size <= 48 else icon_svg
        html = (f'<body style="margin:0;background:{MUSTARD};display:grid;place-items:center;'
                f'width:{size}px;height:{size}px"><div style="width:{inner}px;height:{inner}px">'
                + svg.replace("<svg ", f'<svg width="{inner}" height="{inner}" ') + "</div></body>")
        f = tmp / f"{name}.html"
        f.write_text(html, encoding="utf-8")
        jobs.append({"html": str(f), "w": size, "h": size, "out": str(OUT / name), "type": "png"})
    # 共有用の絵: 東京の絵を 1200×630 に切り出し、左下にロゴ
    og = (f'<body style="margin:0;width:1200px;height:630px;overflow:hidden;position:relative;'
          f"background:#000 url('{tokyo}') center 40%/cover no-repeat\">"
          '<div style="position:absolute;inset:0;background:linear-gradient(to bottom,rgba(0,0,0,0) 45%,rgba(8,12,20,.75) 100%)"></div>'
          '<div style="position:absolute;left:56px;bottom:48px;width:360px">'
          + logo_svg.replace("<svg ", '<svg width="360" ') + "</div></body>")
    f = tmp / "og.html"
    f.write_text(og, encoding="utf-8")
    jobs.append({"html": str(f), "w": 1200, "h": 630, "out": str(OUT / "og.jpg"), "type": "jpeg"})
    js = ("const {chromium}=require('playwright');(async()=>{const jobs=" + json.dumps(jobs) + ";"
          "const b=await chromium.launch();const p=await b.newPage();"
          "for(const j of jobs){await p.setViewportSize({width:j.w,height:j.h});"
          "await p.goto('file://'+j.html);await p.waitForTimeout(300);"
          "await p.screenshot({path:j.out,type:j.type,quality:j.type==='jpeg'?86:undefined});}"
          "await b.close();})()")
    subprocess.run(["node", "-e", js], check=True)
    im = Image.open(OUT / "favicon-32.png").convert("RGBA")
    im.save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32)])


def slides():
    for s in SLIDES:
        im = Image.open(ROOT / f"design/slide-{s}.webp").convert("RGB")
        for w in (1536, 768):
            h = round(im.height * w / im.width)
            im.resize((w, h), Image.LANCZOS).save(OUT / f"slide-{s}-{w}.webp", "WEBP", quality=80 if w == 1536 else 78)


def main():
    font = TTFont(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    la, ic = logo_a(font), icon(font)
    (OUT / "logo-a.svg").write_text(la, encoding="utf-8")
    (OUT / "icon.svg").write_text(ic, encoding="utf-8")
    slides()
    render_pngs(ic, la, icon_small(font))
    for f in sorted(OUT.iterdir()):
        print(f"{f.name}\t{f.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
