#!/usr/bin/env python3
"""Render IG-03 carousel (Bab 3) — same system as IG-01, 1080x1350 x5.
Text EXACTLY the IG-03 draft in INSTAGRAM_BASELINE_PERAN.md. Unpublished draft."""
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
OUT = "/home/hatch/workspace/ace-omega/handover/instagram_ig03"

SERIF_B = "/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf"
SANS_B = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
SANS = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"

CREAM = (247, 239, 227)
INK = (43, 33, 24)
MAROON = (74, 31, 31)
GOLD = (178, 124, 44)
SOFT = (112, 94, 74)

SERIES = "SETELAH DIUSIR, AKU PULANG SEBAGAI PEMILIKNYA"
CHAPTER = "BAB 3 \u2014 NAMA YANG TAK PERNAH DISEBUT"

CARDS = [
    ("1", "Pelanggan lama mencarinya \u2014 bukan karena namanya. Karena rasanya.", "magnifier"),
    ("2", "\u2018Ayamnya persis seperti yang biasa kami pesan dulu.\u2019 Padahal dapurnya sudah pindah.", "quote"),
    ("3", "Delapan puluh porsi. Ayam kurang sepertiga, kelapa asam. Ia buang kelapa itu: \u2018Urap basi membunuh pelanggan lebih cepat daripada rugi kelapa.\u2019", "pot"),
    ("4", "Namanya naik papan: PENANGGUNG JAWAB PESANAN BESAR \u2014 KIRANA.", "board"),
    ("5", "Lalu pelanggan terakhir hari itu berdiri membaca papan itu lama sekali. Suaminya. \u2018Selamat sore,\u2019 kata Kirana. \u2018Mau pesan berapa porsi?\u2019 \u2014 Bab 3 di KBM.", "door"),
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
    lw = 7
    if kind == "magnifier":
        draw.ellipse([cx - 75, cy - 105, cx + 45, cy + 15], outline=MAROON, width=lw)
        draw.line([cx + 30, cy + 2, cx + 95, cy + 70], fill=MAROON, width=10)
    elif kind == "quote":
        fnt = font(SERIF_B, 260)
        draw.text((cx, cy), "\u201c", font=fnt, fill=GOLD, anchor="mm")
    elif kind == "pot":
        # stacked meal boxes (the 80 portions) — clean geometry, no arcs
        for i, dy in enumerate((95, 25, -45)):
            x0 = cx - 110 + (18 if i == 1 else 0)
            draw.rounded_rectangle([x0, cy + dy - 30, x0 + 220, cy + dy + 30], radius=10, outline=MAROON, width=lw)
            draw.line([x0, cy + dy, x0 + 220, cy + dy], fill=GOLD, width=4)
    elif kind == "board":
        draw.rounded_rectangle([cx - 215, cy - 100, cx + 215, cy + 100], radius=12, fill=(255, 253, 247), outline=MAROON, width=lw)
        bf = font(SANS_B, 34)
        draw.text((cx, cy - 38), "PAPAN PESANAN", font=bf, fill=SOFT, anchor="mm")
        nf = font(SERIF_B, 64)
        draw.text((cx, cy + 38), "KIRANA", font=nf, fill=MAROON, anchor="mm")
    elif kind == "door":
        draw.rounded_rectangle([cx - 80, cy - 30, cx + 80, cy + 140], radius=6, outline=MAROON, width=lw)
        draw.line([cx - 80, cy - 30, cx, cy - 105, cx + 80, cy - 30], fill=MAROON, width=lw)
        draw.ellipse([cx + 34, cy + 42, cx + 56, cy + 64], fill=GOLD)


for num, text, kind in CARDS:
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([36, 36, W - 36, H - 36], radius=24, outline=GOLD, width=3)
    hf = font(SANS_B, 30)
    d.text((W // 2, 108), SERIES, font=hf, fill=MAROON, anchor="mm")
    cf = font(SANS, 27)
    d.text((W // 2, 152), CHAPTER, font=cf, fill=SOFT, anchor="mm")
    d.line([240, 196, W - 240, 196], fill=GOLD, width=3)
    motif(d, kind, W // 2, 330)
    fnt, lines, lh = fit_text(d, text, 880, 620)
    y = 520
    for ln in lines:
        d.text((W // 2, y), ln, font=fnt, fill=INK, anchor="ma")
        y += lh
    ff = font(SANS_B, 30)
    d.text((90, H - 110), f"{num} / 5", font=ff, fill=SOFT, anchor="lm")
    if num != "5":
        d.text((W - 130, H - 110), "GESER", font=ff, fill=MAROON, anchor="rm")
        d.polygon([(W - 112, H - 128), (W - 112, H - 92), (W - 78, H - 110)], fill=MAROON)
    else:
        d.text((W - 90, H - 110), "BACA DI KBM", font=ff, fill=MAROON, anchor="rm")
    img.save(f"{OUT}/IG03_kartu{num}.png")
    print(f"card {num}: {len(lines)} lines, saved")

print("done")
