#!/usr/bin/env python3
"""Render static/og-<lang>.png (1200x630) link previews from content/<lang>.json.

Run once after changing hero titles:  python make_og.py
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
W, H = 1200, 630
BG, FG, MUTED, ACCENT, CARD = "#f7f6f2", "#1b1f24", "#5b6472", "#0e7490", "#ffffff"

def font(size, bold=False):
    candidates = [
        "/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        try:
            f = ImageFont.truetype(c, size)
            if "SFNS" in c:
                try: f.set_variation_by_name("Bold" if bold else "Regular")
                except Exception: pass
            return f
        except OSError:
            continue
    return ImageFont.load_default()

def wrap(draw, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=f) <= maxw: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

for lang in ("it", "en"):
    t = json.loads((ROOT / "content" / f"{lang}.json").read_text(encoding="utf-8"))
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # soft accent glow
    glow = Image.new("RGB", (W, H), BG)
    gd = ImageDraw.Draw(glow)
    gd.ellipse((700, -200, 1400, 400), fill="#dff1f5")
    img = Image.blend(img, glow, 0.9); d = ImageDraw.Draw(img)
    # brand mark
    d.rounded_rectangle((80, 72, 144, 136), 16, fill=ACCENT)
    d.rounded_rectangle((96, 88, 128, 112), 6, outline="white", width=4)
    d.text((164, 78), t["brand"]["name"], font=font(40, True), fill=FG)
    d.text((164, 124), t["brand"]["tagline"], font=font(24), fill=MUTED)
    # title
    title = f'{t["hero"]["title_a"]} {t["hero"]["title_b_prefix"]} {t["hero"]["title_words"][0]}'
    y = 220
    for i, line in enumerate(wrap(d, title, font(72, True), 1040)):
        d.text((80, y), line, font=font(72, True), fill=ACCENT if i else FG); y += 86
    # lead
    y += 16
    lines = wrap(d, t["meta"]["description"], font(28), 1040)
    if len(lines) > 3:                      # keep the card readable: 3 lines max
        lines = lines[:3]
        lines[2] = lines[2].rstrip(" ,;:") + "\u2026"
    for line in lines:
        d.text((80, y), line, font=font(28), fill=MUTED); y += 40
    # footer chips
    y = H - 84
    x = 80
    for chip in ("Moodle 4.3+", "Microsoft Teams · Copilot", "Entra ID", "MCP"):
        f = font(22, True); tw = d.textlength(chip, font=f)
        d.rounded_rectangle((x, y, x + tw + 36, y + 44), 22, fill=CARD, outline="#cfcbc2")
        d.text((x + 18, y + 9), chip, font=f, fill=FG); x += tw + 52
    out = ROOT / "static" / f"og-{lang}.png"
    img.save(out, optimize=True)
    print(out.relative_to(ROOT), img.size)
