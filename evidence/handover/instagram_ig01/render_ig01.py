#!/usr/bin/env python3
"""Render IG-01 carousel (Bab 1) — 100% original typographic cards, 1080x1350.
Text is EXACTLY the hub-submitted IG-01 draft in INSTAGRAM_BASELINE_PERAN.md.
Unpublished draft render only."""
import textwrap
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
OUT = "/home/hatch/workspace/ace-omega/handover/instagram_ig01"

SERIF_B = "/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf"
SERIF = "/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf"
SANS_B = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
SANS = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"

CREAM = (247, 239, 227)
INK = (43, 33, 24)
MAROON = (74, 31, 31)
GOLD = (178, 124, 44)
SOFT = (112, 94, 74)

SERIES = "SETELAH DIUSIR, AKU PULANG SEBAGAI PEMILIKNYA"
CHAPTER = "BAB 1 — MALAM AKU DIUSIR DARI RUMAH ITU"

CARDS = [
    ("1", "Enam tahun memasak untuk rumah itu. Semalam, ia diusir dari rumah itu.", "door"),
    ("2", "Perhiasan mertuanya hilang. Yang terakhir masuk kamar itu: Kirana.", "box"),
    ("3", "Suaminya hanya berkata: \u2018Jangan ribut-ribut di depan keluarga.\u2019 Bukan namanya yang dibela.", "quote"),
    ("4", "Seluruh hidup enam tahun muat dalam satu tas kain. Plus satu buku bersampul batik yang tak pernah dilirik siapa pun.", "book"),
    ("5", "Di halaman terakhir buku itu ada satu angka: Rp187.650.000. Nilai enam tahun kerja \u2014 yang tak pernah ditanyakan siapa pun. Lanjutannya di KBM: Setelah Diusir, Aku Pulang Sebagai Pemiliknya.", "number"),
]


def font(path, size):
    return ImageFont.truetype(path, size)


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        trial = (cur + " " + w_).strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


def fit_text(draw, text, max_w, max_h):
    for size in range(84, 40, -4):
        fnt = font(SERIF_B, size)
        lines = wrap(draw, text, fnt, max_w)
        lh = int(size * 1.32)
        if lh * len(lines) <= max_h:
            return fnt, lines, lh
    fnt = font(SERIF_B, 40)
    return fnt, wrap(draw, text, fnt, max_w), int(40 * 1.32)


def motif(draw, kind, cx, cy):
    """Simple original line motifs drawn from scratch."""
    lw = 7
    if kind == "door":
        draw.rounded_rectangle([cx - 80, cy - 30, cx + 80, cy + 140], radius=6, outline=MAROON, width=lw)
        draw.line([cx - 80, cy - 30, cx, cy - 105, cx + 80, cy - 30], fill=MAROON, width=lw)
        draw.ellipse([cx + 34, cy + 42, cx + 56, cy + 64], fill=GOLD)
    elif kind == "box":
        draw.rounded_rectangle([cx - 150, cy - 60, cx + 150, cy + 90], radius=18, outline=MAROON, width=lw)
        draw.line([cx - 150, cy - 60, cx - 120, cy - 110, cx + 120, cy - 110, cx + 150, cy - 60], fill=MAROON, width=lw)
        draw.line([cx - 110, cy, cx + 110, cy], fill=GOLD, width=4)
    elif kind == "quote":
        fnt = font(SERIF_B, 260)
        draw.text((cx, cy), "\u201c", font=fnt, fill=GOLD, anchor="mm")
    elif kind == "book":
        draw.rounded_rectangle([cx - 130, cy - 95, cx + 130, cy + 95], radius=10, outline=MAROON, width=lw)
        draw.line([cx, cy - 95, cx, cy + 95], fill=MAROON, width=5)
        for dy in (-50, 0, 50):
            draw.line([cx - 95, cy + dy, cx - 25, cy + dy], fill=SOFT, width=4)
            draw.line([cx + 25, cy + dy, cx + 95, cy + dy], fill=SOFT, width=4)
    elif kind == "number":
        fnt = font(SERIF_B, 92)
        draw.text((cx, cy), "Rp187.650.000", font=fnt, fill=GOLD, anchor="mm")


for num, text, kind in CARDS:
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    # frame
    d.rounded_rectangle([36, 36, W - 36, H - 36], radius=24, outline=GOLD, width=3)
    # header
    hf = font(SANS_B, 30)
    d.text((W // 2, 108), SERIES, font=hf, fill=MAROON, anchor="mm")
    cf = font(SANS, 27)
    d.text((W // 2, 152), CHAPTER, font=cf, fill=SOFT, anchor="mm")
    d.line([240, 196, W - 240, 196], fill=GOLD, width=3)
    # motif
    motif(d, kind, W // 2, 330)
    # body text
    fnt, lines, lh = fit_text(d, text, 880, 620)
    y = 520
    for ln in lines:
        d.text((W // 2, y), ln, font=fnt, fill=INK, anchor="ma")
        y += lh
    # footer
    ff = font(SANS_B, 30)
    d.text((90, H - 110), f"{num} / 5", font=ff, fill=SOFT, anchor="lm")
    if num != "5":
        d.text((W - 130, H - 110), "GESER", font=ff, fill=MAROON, anchor="rm")
        d.polygon([(W - 112, H - 128), (W - 112, H - 92), (W - 78, H - 110)], fill=MAROON)
    else:
        d.text((W - 90, H - 110), "BACA DI KBM", font=ff, fill=MAROON, anchor="rm")
    img.save(f"{OUT}/IG01_kartu{num}.png")
    print(f"card {num}: {len(lines)} lines, saved")

print("done")
