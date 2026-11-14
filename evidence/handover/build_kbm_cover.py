#!/usr/bin/env python3
"""KBM cover for serial 1: Bab 1 cinematic sample art + title typography.
Base art: instagram_ilustrasi_contoh sample (1280x1920, owner-approved style).
Text is composited with PIL so every letter is exact (no generator text)."""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE = os.path.expanduser("~/workspace/ace-omega/handover/instagram_ilustrasi_contoh/media-generation-ig01-ilustrasi-bab1-contoh-0-162d25c1-70d2-407b-a144-aa7eccf139cc.webp")
OUT_JPG = os.path.expanduser("~/workspace/ace-omega/handover/KBM_COVER_SERIAL1.jpg")
OUT_PNG = os.path.expanduser("~/workspace/ace-omega/handover/KBM_COVER_SERIAL1.png")

NOTO = "/usr/share/fonts/truetype/noto"
DISPLAY_BLACK = os.path.join(NOTO, "NotoSerifDisplay-Black.ttf")
SERIF_BOLD = os.path.join(NOTO, "NotoSerif-Bold.ttf")

CREAM = (245, 239, 226)
GOLD = (232, 179, 75)

im = Image.open(BASE).convert("RGB")
W, H = im.size  # 1280 x 1920

# --- gradient scrims: top for the title, bottom for the author line ---
def scrim(height, max_alpha, from_top=True):
    g = Image.new("L", (1, height))
    for y in range(height):
        t = y / max(1, height - 1)
        a = int(max_alpha * (1 - t) if from_top else max_alpha * t)
        g.putpixel((0, y), a)
    g = g.resize((W, height))
    black = Image.new("RGB", (W, height), (0, 0, 0))
    return black, g

top_black, top_mask = scrim(760, 165, from_top=True)
im.paste(top_black, (0, 0), top_mask)
bot_black, bot_mask = scrim(360, 150, from_top=False)
im.paste(bot_black, (0, H - 360), bot_mask)

d = ImageDraw.Draw(im)

def fit_font(path, text, start_size, max_w, min_size=40):
    s = start_size
    while s > min_size:
        f = ImageFont.truetype(path, s)
        if d.textlength(text, font=f) <= max_w:
            return f
        s -= 4
    return ImageFont.truetype(path, min_size)

def centered(text, font, y, fill, shadow=(0, 0, 0), dy=3):
    w = d.textlength(text, font=font)
    x = (W - w) / 2
    d.text((x + 2, y + dy), text, font=font, fill=shadow)
    d.text((x, y), text, font=font, fill=fill)
    return font.size + 14

MAXW = W - 140
y = 88
y += centered("SETELAH DIUSIR,", fit_font(DISPLAY_BLACK, "SETELAH DIUSIR,", 96, MAXW), y, CREAM)
y += 6
y += centered("AKU PULANG", fit_font(DISPLAY_BLACK, "AKU PULANG", 128, MAXW), y, CREAM)
y += 2
y += centered("SEBAGAI", fit_font(SERIF_BOLD, "S E B A G A I", 54, MAXW), y, GOLD)
y += 4
y += centered("PEMILIKNYA", fit_font(DISPLAY_BLACK, "PEMILIKNYA", 132, MAXW), y, GOLD)

# --- author line at the bottom: gold rule + letterspaced IANILA ---
ay = H - 150
rule_w = 120
d.line([(W / 2 - rule_w, ay), (W / 2 + rule_w, ay)], fill=GOLD, width=3)
author = "I A N I L A"
af = ImageFont.truetype(SERIF_BOLD, 52)
aw = d.textlength(author, font=af)
d.text(((W - aw) / 2 + 2, ay + 26 + 2), author, font=af, fill=(0, 0, 0))
d.text(((W - aw) / 2, ay + 26), author, font=af, fill=CREAM)

im.save(OUT_JPG, quality=92)
im.save(OUT_PNG)
print("saved", OUT_JPG, im.size)
