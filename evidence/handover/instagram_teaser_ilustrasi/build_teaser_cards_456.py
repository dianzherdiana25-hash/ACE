#!/usr/bin/env python3
"""Kartu teaser ilustrasi Bab 4-6 (BANK, TAK-TERBIT). Helper sama dengan tranche Bab 2-3."""
import importlib.util, os
spec = importlib.util.spec_from_file_location("b23", os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_teaser_cards.py"))
# build_teaser_cards.py mengeksekusi pembuatan kartu saat diimpor; salin helper manual di sini sebagai gantinya.
from PIL import Image, ImageDraw, ImageFont

D = os.path.dirname(os.path.abspath(__file__))
W, H = 1080, 1350
FD = "/usr/share/fonts/truetype/dejavu"
def F(n, s): return ImageFont.truetype(os.path.join(FD, n), s)
SERIF_B = lambda s: F("DejaVuSerif-Bold.ttf", s)
SERIF   = lambda s: F("DejaVuSerif.ttf", s)
SANS_B  = lambda s: F("DejaVuSans-Bold.ttf", s)
SANS    = lambda s: F("DejaVuSans.ttf", s)

IMG = {
 "b4_teras": "media-generation-bab4-teras-0-de77c0a5-cc1f-4d50-a8d5-44d69f9c36d6.webp",
 "b4_toko": "media-generation-bab4-toko-gadai-0-9af89fb5-ff13-4ae6-8840-1dfae0c28d8f.webp",
 "b4_buku": "media-generation-bab4-kos-buku-0-3d70b0ee-53d0-40e2-88a9-f87880c31c63.webp",
 "b4_lipatan": "media-generation-bab4-kos-lipatan-0-f036be0a-a734-46c3-a031-f4dc4a8dafc9.webp",
 "b5_papan": "media-generation-bab5-papan300-v3-0-14465bab-ba6e-4334-808b-aefbc902b58d.webp",
 "b5_tamu": "media-generation-bab5-ruang-tamu-0-1ea2e204-1ecc-4231-b2bc-645f155234cd.webp",
 "b5_pasar": "media-generation-bab5-pasar-dita-0-2fb4e58f-9646-4643-a1ca-5ba0bb284b51.webp",
 "b5_telp": "media-generation-bab5-telepon-batal-0-f2861c6f-b2f1-46f8-b593-08a76b39b914.webp",
 "b6_truk": "media-generation-bab6-truk-subuh-0-039708e8-389c-4b02-9134-93af691759be.webp",
 "b6_panggung": "media-generation-bab6-panggung-0-6b9f7192-14aa-48c3-b976-3abbc7ec59a2.webp",
 "b6_samping": "media-generation-bab6-berdampingan-0-7ddee61e-917d-46a5-aa73-fe652e9a4774.webp",
 "b6_mobil": "media-generation-bab6-mobil-malam-0-ecac9389-8cb0-4039-86e9-b531216e9411.webp",
}

def cover_fit(im):
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
    total = 0; rendered = []
    for text, font, fill, gap in items:
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

def header(d, bab, idx, total=4):
    d.text((56, 48), "SETELAH DIUSIR, AKU PULANG SEBAGAI PEMILIKNYA", font=SANS_B(24), fill=(255, 244, 214))
    t = f"BAB {bab}"
    d.text((W - 56 - d.textlength(t, font=SANS_B(24)), 48), t, font=SANS_B(24), fill=(255, 244, 214))
    pg = f"{idx} / {total}"
    d.text((W - 56 - d.textlength(pg, font=SANS(24)), H - 52), pg, font=SANS(24), fill=(230, 225, 210))

def make(name, key, bab, idx, items, scrim_top=580):
    im = cover_fit(Image.open(os.path.join(D, IMG[key])))
    im = scrim(im, scrim_top)
    d = ImageDraw.Draw(im)
    header(d, bab, idx)
    block_bottom(d, items, H - 84)
    p = os.path.join(D, name); im.save(p); print("saved", p)

Q = (250, 246, 236); GOLD = (232, 197, 128)
FOOT = "SETELAH DIUSIR, AKU PULANG SEBAGAI PEMILIKNYA · IANILA"

# ===== BAB 4 =====
make("bab4_kartu1_sampul.png", "b4_teras", 4, 1, [
    ("BAB 4", SANS_B(30), GOLD, 18),
    ("Kuitansi dengan Nama yang Kusembunyikan", SERIF_B(56), Q, 26),
    ("“Perhiasan Ibu tidak dicuri, Bu. Perhiasan Ibu digadai.”", SERIF(42), Q, 0),
], scrim_top=520)
make("bab4_kartu2_toko.png", "b4_toko", 4, 2, [
    ("“Kalau kamu mau tahu, buka sendiri. Kalau tidak mau tahu, kertas ini tetap bicara tanpa nama.”", SERIF(40), Q, 20),
    ("— pemilik toko emas", SERIF(34), GOLD, 0),
], scrim_top=620)
make("bab4_kartu3_buku.png", "b4_buku", 4, 3, [
    ("Dari buku catatan Kirana:", SERIF(36), Q, 16),
    ("“Perhiasan Ibu dipoles, utuh: kalung + gelang, kotak merah, laci 2.”", SERIF_B(42), Q, 0),
], scrim_top=620)
make("bab4_kartu4_tutup.png", "b4_lipatan", 4, 4, [
    ("Kalau Laras sudah tahu, kenapa malam itu ia membiarkan ruang tamunya menuduh orang yang salah?", SERIF(38), Q, 22),
    ("Kirana membuka lipatan itu.", SERIF_B(46), Q, 26),
    (FOOT, SANS_B(25), GOLD, 0),
], scrim_top=580)

# ===== BAB 5 =====
make("bab5_kartu1_sampul.png", "b5_papan", 5, 1, [
    ("BAB 5", SANS_B(30), GOLD, 18),
    ("Pesanan Tiga Ratus Tamu", SERIF_B(58), Q, 26),
    ("“Rasa berubah kalau tangan berubah.”", SERIF(42), Q, 0),
], scrim_top=520)
make("bab5_kartu2_tamu.png", "b5_tamu", 5, 2, [
    ("“Saya sudah tahu rasanya dihancurkan oleh orang yang tidak mau bertanya dulu. Saya tidak mau jadi orang itu.”", SERIF(40), Q, 20),
    ("— Kirana", SERIF(34), GOLD, 0),
], scrim_top=620)
make("bab5_kartu3_pasar.png", "b5_pasar", 5, 3, [
    ("“Pulanglah, sudah mau Magrib. Hati-hati di jalan. Kalau ada apa-apa… kamu tahu Mbak di mana.”", SERIF(40), Q, 20),
    ("— Kirana, kepada Dita", SERIF(34), GOLD, 0),
], scrim_top=620)
make("bab5_kartu4_tutup.png", "b5_telp", 5, 4, [
    ("“Ayam dan daging untuk pernikahan itu… mereka batalkan. Sepihak.”", SERIF(38), Q, 20),
    ("“Katanya, pesanan pernikahan itu tidak boleh jadi.”", SERIF_B(42), Q, 26),
    (FOOT, SANS_B(25), GOLD, 0),
], scrim_top=580)

# ===== BAB 6 =====
make("bab6_kartu1_sampul.png", "b6_truk", 6, 1, [
    ("BAB 6", SANS_B(30), GOLD, 18),
    ("Namaku Disebut di Atas Panggung", SERIF_B(58), Q, 26),
    ("“Yang hilang nama yang baru kemarin Ibu tulis besar-besar di papan itu.”", SERIF(40), Q, 0),
], scrim_top=520)
make("bab6_kartu2_panggung.png", "b6_panggung", 6, 2, [
    ("“…dan untuk hidangan yang luar biasa malam ini, terima kasih kepada Dapur Salma — ditangani oleh Ibu Kirana!”", SERIF(40), Q, 20),
    ("— pembawa acara, dari atas panggung", SERIF(34), GOLD, 0),
], scrim_top=620)
make("bab6_kartu3_samping.png", "b6_samping", 6, 3, [
    ("“Sudah dengar, kan. Bukan ‘dapur sebelah’. Bukan ‘yang masak’. Namamu.”", SERIF(42), Q, 20),
    ("— Bu Salma", SERIF(34), GOLD, 0),
], scrim_top=620)
make("bab6_kartu4_tutup.png", "b6_mobil", 6, 4, [
    ("Di perjalanan pulang malam itu, untuk pertama kalinya sejak malam syukuran, ia mengucapkan nama itu keras-keras di dalam mobil yang kosong:", SERIF(36), Q, 22),
    ("“Kirana.”", SERIF_B(64), Q, 26),
    (FOOT, SANS_B(25), GOLD, 0),
], scrim_top=580)
print("done")
