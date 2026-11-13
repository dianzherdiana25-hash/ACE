#!/usr/bin/env python3
"""Kartu teaser ilustrasi Bab 10-12 (penutup busur) (BANK, TAK-TERBIT). Helper sama dengan tranche Bab 2-3."""
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
 "b10_kotak": "media-generation-bab10-kotak-tertukar-0-203f618e-789d-4723-8a5a-935022da9b64.webp",
 "b10_telpon": "media-generation-bab10-telepon-jujur-0-e5756232-3da0-4e68-b977-d6f2748a670f.webp",
 "b10_sopir": "media-generation-bab10-sopir-mengaku-0-d7858358-6024-42ee-93ed-cdc01ed189c2.webp",
 "b10_buku": "media-generation-bab10-buku-lama-0-36af7c9d-c1ae-47cc-9cfb-f403ad962192.webp",
 "b11_map": "media-generation-bab11-map-arman-v2-0-2e3241d9-9612-446a-84cf-8b7dcdcec133.webp",
 "b11_sarto": "media-generation-bab11-sarto-telepon-0-28639fb4-bb1d-4a6b-b987-530695168530.webp",
 "b11_dita": "media-generation-bab11-dita-pintu-0-6553af58-e1d6-4503-b50f-07e5f59b3cb9.webp",
 "b11_pesan": "media-generation-bab11-pesan-pagi-0-75c04ab2-ddb7-40e0-a261-469b7ab74ef7.webp",
 "b12_papan": "media-generation-bab12-papan-nama-0-c1e787e9-0654-4458-a2aa-289fa139662e.webp",
 "b12_cincin": "media-generation-bab12-cincin-surat-0-23eebc9e-2191-43fa-a934-5f57118ee74c.webp",
 "b12_jabat": "media-generation-bab12-jabat-berdiri-0-0920a727-eab4-4c76-a05b-c35f2b5bf1a8.webp",
 "b12_board": "media-generation-bab12-papan-pesanan-0-aee04db1-f0c3-46e8-a81c-545c4c624a30.webp",
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



# ===== BAB 10 =====
make("bab10_kartu1_sampul.png", "b10_kotak", 10, 1, [
    ("BAB 10", SANS_B(30), GOLD, 18),
    ("Pengiriman yang Dirusak di Perjalanan", SERIF_B(52), Q, 26),
    ("Segelnya utuh. Tandanya utuh. Isinya bukan miliknya.", SERIF(40), Q, 0),
], scrim_top=500)
make("bab10_kartu2_telepon.png", "b10_telpon", 10, 2, [
    ("“Saya tidak mau Ibu tahu dari tamu.”", SERIF_B(44), Q, 20),
    ("— Kirana, menelepon klien sebelum acara dimulai", SERIF(32), GOLD, 0),
], scrim_top=620)
make("bab10_kartu3_sopir.png", "b10_sopir", 10, 3, [
    ("“Saya cuma berhenti sekali, Bu. Di warung kopi pertengahan jalan.”", SERIF(40), Q, 20),
    ("— sopir pengganti", SERIF(34), GOLD, 0),
], scrim_top=620)
make("bab10_kartu4_tutup.png", "b10_buku", 10, 4, [
    ("Dari catatan Kirana, tiga tahun lalu:", SERIF(36), Q, 16),
    ("“Yang mengatur kendaraan waktu itu bukan Mas Arman.”", SERIF_B(42), Q, 26),
    (FOOT, SANS_B(25), GOLD, 0),
], scrim_top=580)

# ===== BAB 11 =====
make("bab11_kartu1_sampul.png", "b11_map", 11, 1, [
    ("BAB 11", SANS_B(30), GOLD, 18),
    ("Bukti yang Diserahkan Arman", SERIF_B(56), Q, 26),
    ("“Kalau ada yang harus dituduh, rumah ini tahu siapa yang paling tidak akan dibela siapa-siapa.”", SERIF(36), Q, 16),
    ("— pesan Laras, malam sebelum malam syukuran", SERIF(32), GOLD, 0),
], scrim_top=480)
make("bab11_kartu2_sarto.png", "b11_sarto", 11, 2, [
    ("“Saya memang menyuruh berhenti. Saya disuruh.”", SERIF_B(42), Q, 20),
    ("— Sarto, membuka catatan panggilannya", SERIF(32), GOLD, 0),
], scrim_top=620)
make("bab11_kartu3_dita.png", "b11_dita", 11, 3, [
    ("“Dari awal aku ini bukan pelanggan. Aku ini pintu.”", SERIF_B(42), Q, 20),
    ("— Dita", SERIF(34), GOLD, 0),
], scrim_top=620)
make("bab11_kartu4_tutup.png", "b11_pesan", 11, 4, [
    ("“Suruh dia datang. Berdua saja. Ada satu hal yang belum Ibu kembalikan ke kamu.”", SERIF(38), Q, 26),
    (FOOT, SANS_B(25), GOLD, 0),
], scrim_top=580)

# ===== BAB 12 =====
make("bab12_kartu1_sampul.png", "b12_papan", 12, 1, [
    ("BAB 12", SANS_B(30), GOLD, 18),
    ("Namaku di Papan Ruko Itu", SERIF_B(56), Q, 26),
    ("DAPUR SALMA & KIRANA — penanggung jawab: Kirana Ayu Lestari.", SERIF_B(38), Q, 0),
], scrim_top=500)
make("bab12_kartu2_cincin.png", "b12_cincin", 12, 2, [
    ("“Bukan cincinnya. Nama kamu, yang Ibu ambil di ruangan ini. Ibu kembalikan di ruangan ini juga.”", SERIF(38), Q, 20),
    ("— Laras", SERIF(34), GOLD, 0),
], scrim_top=620)
make("bab12_kartu3_jabat.png", "b12_jabat", 12, 3, [
    ("“Aku dengar, Mas. Terima kasih sudah berdiri.”", SERIF_B(42), Q, 20),
    ("— Kirana", SERIF(34), GOLD, 0),
], scrim_top=620)
make("bab12_kartu4_tutup.png", "b12_board", 12, 4, [
    ("Sebuah pintu yang dibiarkan terbuka dengan jujur, untuk musim yang belum tentu datang.", SERIF(38), Q, 20),
    ("TAMAT — busur pertama", SANS_B(30), GOLD, 26),
    (FOOT, SANS_B(25), GOLD, 0),
], scrim_top=580)
print("done")
