#!/usr/bin/env python3
"""Rakit kartu teaser ilustrasi Bab 2 & Bab 3 (BANK, TAK-TERBIT).
Ilustrasi full-bleed 1080x1350; teks kartu = kutipan PERSIS naskah bab."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

D = os.path.dirname(os.path.abspath(__file__))
W, H = 1080, 1350
FD = "/usr/share/fonts/truetype/dejavu"
def F(n, s): return ImageFont.truetype(os.path.join(FD, n), s)
SERIF_B = lambda s: F("DejaVuSerif-Bold.ttf", s)
SERIF_I = lambda s: F("DejaVuSerif.ttf", s)  # italic tidak tersedia di host; serif reguler untuk kutipan
SERIF   = lambda s: F("DejaVuSerif.ttf", s)
SANS_B  = lambda s: F("DejaVuSans-Bold.ttf", s)
SANS    = lambda s: F("DejaVuSans.ttf", s)

IMG = {
 "b2_papan": "media-generation-bab2-papan-nama-0-eba20849-fa8b-43cb-8940-7b572bd2e9d4.webp",
 "b2_kos": "media-generation-bab2-kos-subuh-0-b221e350-f7cc-4a3e-839d-221fdcef9be7.webp",
 "b2_jalan": "media-generation-bab2-berhenti-di-jalan-0-098b817c-2334-4742-ae5f-82d16728d2b9.webp",
 "b3_main": "media-generation-bab3-arman-membaca-papan-0-3975c81a-7d92-47f5-9875-d55cf8d27b19.webp",
 "b3_telp": "media-generation-bab3-telepon-0-0d9e17a6-ddce-4474-bd8d-b51a8d327d45.webp",
 "b3_krisis": "media-generation-bab3-papan-krisis-v2-0-868958e6-83b6-48df-bf1e-bdc9401d8916.webp",
 "b3_temu": "media-generation-bab3-arman-di-papan-0-bd0e16df-9103-4a97-a2c7-9d0a5d97d1fd.webp",
}

def cover_fit(im, crop_box=None):
    if crop_box:
        im = im.crop(crop_box)
    im = im.convert("RGB")
    s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x = (im.width - W) // 2; y = (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))

def scrim(img, top, strength=205):
    ov = Image.new("L", (1, H), 0)
    for yy in range(H):
        a = 0 if yy < top else int(strength * ((yy - top) / (H - top)) ** 1.4)
        ov.putpixel((0, yy), a)
    ov = ov.resize((W, H))
    black = Image.new("RGB", (W, H), (5, 8, 10))
    return Image.composite(black, img, ov)

def wrap(d, text, font, maxw):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if d.textlength(t, font=font) <= maxw: cur = t
        else:
            if cur: lines.append(cur)
            cur = w_
    if cur: lines.append(cur)
    return lines

def block_bottom(d, items, bottom):
    """items: list of (text, font, fill, gap_after, align) drawn upward from bottom."""
    total = 0
    rendered = []
    for text, font, fill, gap, italic in items:
        ls = wrap(d, text, font, W - 150)
        rendered.append((ls, font, fill, gap))
        total += len(ls) * (font.size + 12) + gap
    y = bottom - total
    for ls, font, fill, gap in rendered:
        for ln in ls:
            w_ = d.textlength(ln, font=font)
            d.text(((W - w_) / 2, y), ln, font=font, fill=fill)
            y += font.size + 12
        y += gap
    return y

def header(d, bab, idx, total=4):
    d.text((56, 48), "SETELAH DIUSIR, AKU PULANG SEBAGAI PEMILIKNYA", font=SANS_B(24), fill=(255, 244, 214))
    t = f"BAB {bab}"
    d.text((W - 56 - d.textlength(t, font=SANS_B(24)), 48), t, font=SANS_B(24), fill=(255, 244, 214))
    pg = f"{idx} / {total}"
    d.text((W - 56 - d.textlength(pg, font=SANS(24)), H - 52), pg, font=SANS(24), fill=(230, 225, 210))

def make(name, img_key, bab, idx, items, scrim_top=560, crop_box=None, crop_frac=None):
    im = Image.open(os.path.join(D, IMG[img_key]))
    if crop_frac:
        cw, ch = im.width, im.height
        box = (int(cw * crop_frac[0]), int(ch * crop_frac[1]), int(cw * crop_frac[2]), int(ch * crop_frac[3]))
        im = cover_fit(im, box)
    else:
        im = cover_fit(im)
    im = scrim(im, scrim_top)
    d = ImageDraw.Draw(im)
    header(d, bab, idx)
    block_bottom(d, items, H - 84)
    p = os.path.join(D, name)
    im.save(p); print("saved", p)

Q = (250, 246, 236); GOLD = (232, 197, 128)

# ===== BAB 2 =====
make("bab2_kartu1_sampul.png", "b2_papan", 2, 1, [
    ("BAB 2", SANS_B(30), GOLD, 18, False),
    ("Kos Kecil, Dapur Orang, Kesempatan Pertama", SERIF_B(58), Q, 26, False),
    ("“Enam tahun, namanya tidak pernah tertulis di dapur mana pun.”", SERIF_I(40), Q, 0, True),
], scrim_top=520)
make("bab2_kartu2_kos.png", "b2_kos", 2, 2, [
    ("“Pukul empat pagi, mata Kirana terbuka sendiri.”", SERIF_B(44), Q, 20, False),
    ("Hanya ada kamar kos berukuran tiga kali empat meter, kipas angin yang berderak pelan, dan tas kainnya yang masih tergeletak di sudut, belum dibongkar.", SERIF(36), Q, 0, False),
], scrim_top=640)
make("bab2_kartu3_jalan.png", "b2_jalan", 2, 3, [
    ("Catatan di kertas pesanan itu:", SERIF(36), Q, 16, False),
    ("“Minta tolong rasa ayamnya seperti yang biasa kami pesan, yang bumbunya meresap itu.”", SERIF_I(42), Q, 20, True),
    ("Kirana berhenti berjalan.", SERIF_B(42), Q, 0, False),
], scrim_top=600)
make("bab2_kartu4_tutup.png", "b2_papan", 2, 4, [
    ("“Di sini tidak ada kerja yang dibayar dengan kata ‘nanti’.”", SERIF_I(44), Q, 22, True),
    ("— Bu Salma", SERIF(34), GOLD, 26, False),
    ("SETELAH DIUSIR, AKU PULANG SEBAGAI PEMILIKNYA · IANILA", SANS_B(25), GOLD, 0, False),
], scrim_top=600, crop_frac=(0.0, 0.0, 0.62, 1.0))

# ===== BAB 3 =====
make("bab3_kartu1_sampul.png", "b3_main", 3, 1, [
    ("BAB 3", SANS_B(30), GOLD, 18, False),
    ("Nama yang Tak Pernah Disebut", SERIF_B(58), Q, 26, False),
    ("“Enam tahun ia tidak pernah perlu membaca namanya di mana pun, karena Kirana selalu ada sebelum namanya sempat dicari.”", SERIF_I(38), Q, 0, True),
], scrim_top=500)
make("bab3_kartu2_telepon.png", "b3_telp", 3, 2, [
    ("“Lidah orang tidak bisa dibohongi, Kirana. Tangan bisa disembunyikan enam tahun, rasa tidak.”", SERIF_I(42), Q, 20, True),
    ("— Bu Salma", SERIF(34), GOLD, 0, False),
], scrim_top=620)
make("bab3_kartu3_krisis.png", "b3_krisis", 3, 3, [
    ("“Urap basi membunuh pelanggan lebih cepat daripada rugi kelapa. Kita jualan bertahun-tahun, bukan berjualan sekali.”", SERIF_I(40), Q, 20, True),
    ("— Kirana", SERIF(34), GOLD, 0, False),
], scrim_top=620)
make("bab3_kartu4_tutup.png", "b3_temu", 3, 4, [
    ("“Selamat sore,” katanya, dengan nada yang sama rata seperti yang ia pakai untuk semua pelanggan. “Mau pesan berapa porsi?”", SERIF_I(40), Q, 26, True),
    ("SETELAH DIUSIR, AKU PULANG SEBAGAI PEMILIKNYA · IANILA", SANS_B(25), GOLD, 0, False),
], scrim_top=600)
print("done")
