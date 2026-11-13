#!/usr/bin/env python3
"""Render IG-02 reel draft (Bab 2) — vertical 1080x1920, 5 scenes x 5s = 25s.
On-screen text = the IG-02 narration script from INSTAGRAM_BASELINE_PERAN.md,
split sentence by sentence. v1 is SILENT (full on-screen text); no voiceover yet.
100% original typographic visuals, same system as IG-01. Unpublished draft."""
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
OUT = "/home/hatch/workspace/ace-omega/handover/instagram_ig02/scenes"

SERIF_B = "/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf"
SANS_B = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
SANS = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"

CREAM = (247, 239, 227)
INK = (43, 33, 24)
MAROON = (74, 31, 31)
GOLD = (178, 124, 44)
SOFT = (112, 94, 74)

SERIES = "SETELAH DIUSIR, AKU PULANG SEBAGAI PEMILIKNYA"
CHAPTER = "BAB 2 \u2014 KOS KECIL, DAPUR ORANG, KESEMPATAN PERTAMA"

SCENES = [
    "Pagi pertama sebagai orang yang diusir, Kirana melamar ke dapur saingan mertuanya.",
    "Ujiannya satu: hitung belanja untuk delapan puluh porsi.",
    "Ia menulis bukan cuma belanja \u2014 urutan kerjanya sekalian.",
    "Sore itu, untuk pertama kali dalam enam tahun, namanya tertulis di papan:",
    "KIRANA",
]


def font(path, size):
    return ImageFont.truetype(path, size)


def fit_single(draw, text, path, start, max_w):
    size = start
    while size > 16:
        f = font(path, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return font(path, 16)


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
    for size in range(88, 42, -4):
        fnt = font(SERIF_B, size)
        lines = wrap(draw, text, fnt, max_w)
        lh = int(size * 1.34)
        if lh * len(lines) <= max_h:
            return fnt, lines, lh
    fnt = font(SERIF_B, 42)
    return fnt, wrap(draw, text, fnt, max_w), int(42 * 1.34)


for i, text in enumerate(SCENES, start=1):
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([36, 36, W - 36, H - 36], radius=24, outline=GOLD, width=3)
    hf = fit_single(d, SERIES, SANS_B, 30, 920)
    d.text((W // 2, 120), SERIES, font=hf, fill=MAROON, anchor="mm")
    cf = fit_single(d, CHAPTER, SANS, 27, 920)
    d.text((W // 2, 168), CHAPTER, font=cf, fill=SOFT, anchor="mm")
    d.line([240, 214, W - 240, 214], fill=GOLD, width=3)

    if text == "KIRANA":
        # board motif: whiteboard rectangle with the name, as in Bab 2/3
        d.rounded_rectangle([140, 560, W - 140, 900], radius=16, fill=(255, 253, 247), outline=MAROON, width=7)
        bf = font(SANS_B, 44)
        d.text((W // 2, 640), "PAPAN JADWAL \u2014 DAPUR SALMA", font=bf, fill=SOFT, anchor="mm")
        nf = font(SERIF_B, 150)
        d.text((W // 2, 790), "KIRANA", font=nf, fill=MAROON, anchor="mm")
    else:
        fnt, lines, lh = fit_text(d, text, 880, 900)
        total = lh * len(lines)
        y = (H - total) // 2 - 40
        for ln in lines:
            d.text((W // 2, y), ln, font=fnt, fill=INK, anchor="ma")
            y += lh

    ff = font(SANS_B, 30)
    d.text((90, H - 120), f"{i} / 5", font=ff, fill=SOFT, anchor="lm")
    if i == 5:
        d.text((W - 90, H - 120), "BACA DI KBM", font=ff, fill=MAROON, anchor="rm")
    img.save(f"{OUT}/scene{i}.png")
    print(f"scene {i} saved")

print("done")
