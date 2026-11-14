#!/usr/bin/env python3
"""Kartu teaser ilustrasi Bab 7-9 (BANK, TAK-TERBIT). Helper sama dengan tranche Bab 2-3."""
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
 "b7_datang": "media-generation-bab7-teras-datang-0-4bb8c7ad-0971-4145-b6e1-3b2fc20725b1.webp",
 "b7_latihan": "media-generation-bab7-latihan-presentasi-0-5e27dea1-10be-442e-9fe0-1911ed9aec18.webp",
 "b7_akui": "media-generation-bab7-pengakuan-0-05babe9e-34dc-493c-bdd5-66680c26b435.webp",
 "b7_sepi": "media-generation-bab7-teras-sepi-0-8fb71a55-ba75-426c-9982-74626935ec8f.webp",
 "b8_lutut": "media-generation-bab8-berlutut-0-b51dc70a-ed80-41ad-a6dd-170700d61d20.webp",
 "b8_opor": "media-generation-bab8-seleksi-opor-0-f4d00461-08c6-43dc-9850-b964b117cc35.webp",
 "b8_tangga": "media-generation-bab8-dita-tangga-0-e90de38c-4f72-4b9e-ad29-99a34cfe7832.webp",
 "b8_kuitansi": "media-generation-bab8-kuitansi-meja-0-d2c1b3cf-2683-43f4-9035-30bae32794cf.webp",
 "b9_berdiri": "media-generation-bab9-berdiri-mas-0-0e035349-7c2c-43c5-b64e-f45085908c73.webp",
 "b9_tulis": "media-generation-bab9-menulis-malam-0-8d44648e-dc97-4bf9-a0b1-1d8d2b8ff419.webp",
 "b9_baca": "media-generation-bab9-laras-membaca-0-c78fe749-2dbf-4481-ad17-122c73e4a506.webp",
 "b9_senyum": "media-generation-bab9-laras-senyum-0-25774040-3727-4900-ab5a-1b5175aacbaf.webp",
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


# ===== BAB 7 =====
make("bab7_kartu1_sampul.png", "b7_datang", 7, 1, [
    ("BAB 7", SANS_B(30), GOLD, 18),
    ("Pengakuan di Depan Pintu Kos", SERIF_B(58), Q, 26),
    ("“Dan Mbak tidak pernah membuka namamu.”", SERIF(42), Q, 0),
], scrim_top=520)
make("bab7_kartu2_latihan.png", "b7_latihan", 7, 2, [
    ("“Itu memang tantangan, Bu. Untuk mereka, dan untuk kita.”", SERIF(42), Q, 20),
    ("— Kirana", SERIF(34), GOLD, 0),
], scrim_top=620)
make("bab7_kartu3_akui.png", "b7_akui", 7, 3, [
    ("“Aku pengecut, Mbak. Aku menonton Mbak diusir dan aku diam saja karena diam adalah satu-satunya cara aku tidak ketahuan.”", SERIF(38), Q, 20),
    ("— Dita", SERIF(34), GOLD, 0),
], scrim_top=620)
make("bab7_kartu4_tutup.png", "b7_sepi", 7, 4, [
    ("Baru kepada satu orang. Di teras kos. Belum kepada dunia.", SERIF_B(44), Q, 26),
    (FOOT, SANS_B(25), GOLD, 0),
], scrim_top=580)

# ===== BAB 8 =====
make("bab8_kartu1_sampul.png", "b8_lutut", 8, 1, [
    ("BAB 8", SANS_B(30), GOLD, 18),
    ("Di Depan Semua Orang, Dia Berlutut", SERIF_B(56), Q, 26),
    ("“Malam itu aku tahu kamu tidak mencuri. Aku tahu, dan aku memilih diam karena diam lebih gampang.”", SERIF(38), Q, 0),
], scrim_top=500)
make("bab8_kartu2_opor.png", "b8_opor", 8, 2, [
    ("“Saya kenal rasa ini.”", SERIF_B(44), Q, 18),
    ("“Rasanya persis ini. Persis.”", SERIF(42), Q, 20),
    ("— panelis tertua, ruang seleksi", SERIF(34), GOLD, 0),
], scrim_top=620)
make("bab8_kartu3_tangga.png", "b8_tangga", 8, 3, [
    ("“Yang mengambil perhiasan Ibu itu aku. Aku yang menggadaikannya.”", SERIF(42), Q, 20),
    ("— Dita, di depan keluarga besar", SERIF(34), GOLD, 0),
], scrim_top=620)
make("bab8_kartu4_tutup.png", "b8_kuitansi", 8, 4, [
    ("“Tanggal. Barang. Nama.”", SERIF_B(46), Q, 20),
    ("Tiga baris yang sudah menunggu berminggu-minggu untuk dibaca oleh ruangan yang tepat.", SERIF(38), Q, 26),
    (FOOT, SANS_B(25), GOLD, 0),
], scrim_top=580)

# ===== BAB 9 =====
make("bab9_kartu1_sampul.png", "b9_berdiri", 9, 1, [
    ("BAB 9", SANS_B(30), GOLD, 18),
    ("Bukan Rujuk yang Kubawa Pulang", SERIF_B(56), Q, 26),
    ("“Berdiri, Mas.”", SERIF_B(48), Q, 18),
    ("“Aku cuma pernah minta Mas berdiri — sekali saja, malam itu, di ruangan ini juga.”", SERIF(38), Q, 0),
], scrim_top=500)
make("bab9_kartu2_hitung.png", "b9_tulis", 9, 2, [
    ("Dari perhitungan tertulis Kirana:", SERIF(36), Q, 16),
    ("“Total nilai pekerjaan yang belum dibayarkan: Rp187.650.000.”", SERIF_B(42), Q, 0),
], scrim_top=620)
make("bab9_kartu3_baca.png", "b9_baca", 9, 3, [
    ("“Angka ini Ibu terima. Bukan karena Ibu tidak bisa membantahnya — karena Ibu tahu persis buku itu tidak pernah bohong.”", SERIF(38), Q, 20),
    ("— Laras", SERIF(34), GOLD, 0),
], scrim_top=620)
make("bab9_kartu4_tutup.png", "b9_senyum", 9, 4, [
    ("“Bukannya ruko itu milik keluarga ini, Bu?”", SERIF(40), Q, 20),
    ("“Itulah yang kamu kira selama ini.”", SERIF_B(44), Q, 26),
    (FOOT, SANS_B(25), GOLD, 0),
], scrim_top=580)
print("done")
