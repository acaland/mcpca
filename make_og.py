#!/usr/bin/env python3
"""Render the link-preview cards (1200x630) into static/.

    python make_og.py

Writes og-<lang>.png for the home page and og-case-<lang>.png for the case
study, reading their titles and descriptions from content/<lang>.json.  Run it
again after changing any hero title, page title or meta description.
"""
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
W, H = 1200, 630
BG, FG, MUTED, ACCENT, CARD, BORDER = "#f7f6f2", "#1b1f24", "#5b6472", "#0e7490", "#ffffff", "#cfcbc2"
GLOW = "#dff1f5"
MARGIN = 80
TEXT_WIDTH = 1040


def font(size, bold=False):
    candidates = [
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        try:
            f = ImageFont.truetype(c, size)
            if "SFNS" in c:
                try:
                    f.set_variation_by_name("Bold" if bold else "Regular")
                except Exception:
                    pass
            return f
        except OSError:
            continue
    return ImageFont.load_default()


MARKS = re.compile(r"\*\*|==|`")


def plain(text):
    """Toglie i marcatori di evidenziazione: sulle card servono solo le parole."""
    return MARKS.sub("", text)


def wrap(draw, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=f) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def card(brand, tagline, title, description, chips, out, title_size=72, accent_from=1):
    """One preview card: brand lockup, headline, description, chips."""
    img = Image.new("RGB", (W, H), BG)
    glow = Image.new("RGB", (W, H), BG)
    ImageDraw.Draw(glow).ellipse((700, -200, 1400, 400), fill=GLOW)
    img = Image.blend(img, glow, 0.9)
    d = ImageDraw.Draw(img)

    # brand lockup
    d.rounded_rectangle((MARGIN, 72, MARGIN + 64, 136), 16, fill=ACCENT)
    d.rounded_rectangle((MARGIN + 16, 88, MARGIN + 48, 112), 6, outline="white", width=4)
    d.text((MARGIN + 84, 78), brand, font=font(40, True), fill=FG)
    d.text((MARGIN + 84, 124), tagline, font=font(24), fill=MUTED)

    # headline: the first line in ink, the rest in the accent colour
    title = plain(title)
    tf = font(title_size, True)
    lines = wrap(d, title, tf, TEXT_WIDTH)
    while len(lines) > 2 and title_size > 44:
        title_size -= 6
        tf = font(title_size, True)
        lines = wrap(d, title, tf, TEXT_WIDTH)
    y = 220
    for i, line in enumerate(lines[:3]):
        d.text((MARGIN, y), line, font=tf, fill=ACCENT if i >= accent_from else FG)
        y += int(title_size * 1.2)

    # description, three lines at most
    df = font(28)
    y += 16
    dl = wrap(d, plain(description), df, TEXT_WIDTH)
    if len(dl) > 3:
        dl = dl[:3]
        dl[2] = dl[2].rstrip(" ,;:") + "…"
    for line in dl:
        d.text((MARGIN, y), line, font=df, fill=MUTED)
        y += 40

    # chips along the bottom
    y = H - 84
    x = MARGIN
    cf = font(22, True)
    for chip in chips:
        tw = d.textlength(chip, font=cf)
        if x + tw + 36 > W - MARGIN:
            break
        d.rounded_rectangle((x, y, x + tw + 36, y + 44), 22, fill=CARD, outline=BORDER)
        d.text((x + 18, y + 9), chip, font=cf, fill=FG)
        x += tw + 52

    img.save(out, optimize=True)
    print(out.relative_to(ROOT), img.size)


for lang in ("it", "en"):
    t = json.loads((ROOT / "content" / f"{lang}.json").read_text(encoding="utf-8"))
    case, band = t["case"], t["case_band"]

    card(
        brand=t["brand"]["name"],
        tagline=t["brand"]["tagline"],
        title=f'{t["hero"]["title_a"]} {t["hero"]["title_b_prefix"]} {t["hero"]["title_words"][0]}',
        description=t["meta"]["description"],
        chips=["Moodle 4.3+", "Microsoft Teams · Copilot", "ChatGPT", "Claude"],
        out=ROOT / "static" / f"og-{lang}.png",
    )

    metrics = case["metrics"]["items"]
    card(
        brand=t["brand"]["name"],
        tagline=case["kicker"],
        title=band["title"],
        description=case["meta"]["description"],
        chips=[case["facts"][0]["v"]] + [f'{mtr["value"]} {mtr["label"]}' for mtr in metrics[:3]],
        out=ROOT / "static" / f"og-case-{lang}.png",
        title_size=58,
        accent_from=2,
    )
