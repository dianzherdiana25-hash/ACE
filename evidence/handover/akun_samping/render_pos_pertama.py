#!/usr/bin/env python3
"""Pos pertama (DRAF TAK-TERBIT) untuk akun samping ACE:
- @mellowdymusik: carousel playlist "Pulang Malam" (5 kartu, 1080x1350, tema gelap musik)
- @jejaktaaruf: carousel edukasi "5 Tanda Siap Taaruf" (5 kartu, 1080x1350, tema ivory/hijau)
Semua motif digambar prosedural (orisinal). Hanya judul lagu + nama artis yang disebut (tanpa lirik).
"""
from PIL import Image, ImageDraw, ImageFont
import math, os

W, H = 1080, 1350
OUT = os.path.dirname(os.path.abspath(__file__))

FD = "/usr/share/fonts/truetype/dejavu"
def F(name, size):
    return ImageFont.truetype(os.path.join(FD, name), size)
SERIF_B  = lambda s: F("DejaVuSerif-Bold.ttf", s)
SERIF    = lambda s: F("DejaVuSerif.ttf", s)
SANS_B   = lambda s: F("DejaVuSans-Bold.ttf", s)
SANS     = lambda s: F("DejaVuSans.ttf", s)

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

def centered(d, cx, y, text, font, fill, spacing=14):
    for ln in wrap(d, text, font, W - 220):
        w_ = d.textlength(ln, font=font)
        d.text(((cx - w_/2), y), ln, font=font, fill=fill)
        y += font.size + spacing
    return y

# ---------------------------------------------------------------- mellowdy
M_BG    = (16, 18, 28)      # biru malam
M_PANEL = (24, 27, 42)
M_INK   = (240, 238, 230)
M_SUB   = (168, 172, 190)
M_ACC   = (94, 234, 212)    # teal neon
M_ACC2  = (244, 114, 182)   # pink neon

def vinyl(d, cx, cy, r):
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(10, 11, 18), outline=(52, 56, 76), width=3)
    for rr in range(int(r*0.92), int(r*0.4), -16):
        d.ellipse([cx-rr, cy-rr, cx+rr, cy+rr], outline=(34, 37, 54), width=2)
    lr = int(r*0.30)
    d.ellipse([cx-lr, cy-lr, cx+lr, cy+lr], fill=M_ACC2)
    d.ellipse([cx-7, cy-7, cx+7, cy+7], fill=M_BG)

def eq_bars(d, x0, y_base, n=18, color=M_ACC):
    for i in range(n):
        hgt = 26 + 64*abs(math.sin(i*1.37))
        x = x0 + i*22
        d.rounded_rectangle([x, y_base-hgt, x+10, y_base], radius=5, fill=color)

def m_card(idx, total, kicker, big, body, foot, motif):
    img = Image.new("RGB", (W, H), M_BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([26, 26, W-26, H-26], radius=30, outline=(52, 56, 76), width=2)
    d.text((70, 66), "MELLOWDY MUSIK", font=SANS_B(30), fill=M_ACC)
    r = d.textlength("PLAYLIST", font=SANS(26))
    d.text((W-70-r, 68), "PLAYLIST", font=SANS(26), fill=M_SUB)
    d.text((70, 118), kicker, font=SANS_B(27), fill=M_SUB)
    y = 210
    if motif == "vinyl":
        vinyl(d, W//2, 400, 150); y = 620
    elif motif == "eq":
        eq_bars(d, 150, 470, 36); y = 560
    y = centered(d, W//2, y, big, SERIF_B(64), M_INK, 16)
    y += 26
    if body:
        y = centered(d, W//2, y, body, SANS(37), M_SUB, 14)
    d.text((70, H-110), foot, font=SANS(28), fill=M_SUB)
    pg = f"{idx} / {total}"
    d.text((W-70-d.textlength(pg, font=SANS(28)), H-110), pg, font=SANS(28), fill=M_SUB)
    return img

MELLOW = [
    ("EDISI MALAM", "Playlist Pulang Malam",
     "Empat lagu buat perjalanan pulang yang kepanjangan — dari lampu merah terakhir sampai pintu rumah.",
     "GESER UNTUK DAFTARNYA", "vinyl"),
    ("LAGU 1", "“Evaluasi” — Hindia",
     "Buat kilometer pertama: mengakui capek itu bukan kalah.", "", "eq"),
    ("LAGU 2", "“Satu Bulan” — Bernadya",
     "Buat yang pulangnya membawa kabar yang belum berani diceritakan.", "", "eq"),
    ("LAGU 3", "“Gala Bunga Matahari” — Sal Priadi",
     "Buat berhenti sebentar di tengah jalan, menatap langit, lalu lanjut.", "", "eq"),
    ("LAGU 4", "“Sampai Jadi Debu” — Banda Neira",
     "Buat kilometer terakhir: pelan-pelan saja, rumah sudah dekat.", "", "eq"),
    ("SIMPAN DULU", "Besok ada playlist baru.",
     "Akun ini mengunggah satu playlist pendek setiap malam. Simpan pos ini dan ikuti akunnya, biar playlist besok tidak kelewatan.",
     "MELLOWDY MUSIK — PLAYLIST TIAP MALAM", "vinyl"),
]

# ---------------------------------------------------------------- jejak
J_BG    = (250, 247, 238)
J_INK   = (43, 54, 44)
J_SUB   = (110, 116, 104)
J_ACC   = (46, 94, 62)      # hijau
J_GOLD  = (176, 141, 74)

def geo_motif(d, cx, cy, s, color=J_GOLD):
    # bintang 8 sudut prosedural (dua persegi berputar)
    for ang in (0, 45):
        pts = []
        for k in range(4):
            a = math.radians(ang + k*90)
            pts.append((cx + s*math.cos(a), cy + s*math.sin(a)))
        d.polygon(pts, outline=color, width=4)
    d.ellipse([cx-10, cy-10, cx+10, cy+10], fill=color)

def j_card(idx, total, kicker, big, body, foot, motif):
    img = Image.new("RGB", (W, H), J_BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([26, 26, W-26, H-26], radius=30, outline=J_GOLD, width=3)
    d.text((70, 66), "JEJAK TAARUF", font=SANS_B(30), fill=J_ACC)
    r = d.textlength("EDUKASI", font=SANS(26))
    d.text((W-70-r, 68), "EDUKASI", font=SANS(26), fill=J_SUB)
    d.text((70, 118), kicker, font=SANS_B(27), fill=J_SUB)
    y = 190
    if motif == "geo":
        geo_motif(d, W//2, 330, 92); y = 500
    elif motif == "dot":
        d.ellipse([W//2-16, 300, W//2+16, 332], fill=J_GOLD); y = 420
    y = centered(d, W//2, y, big, SERIF_B(60), J_INK, 16)
    y += 26
    if body:
        y = centered(d, W//2, y, body, SANS(37), J_SUB, 14)
    d.text((70, H-110), foot, font=SANS(28), fill=J_SUB)
    pg = f"{idx} / {total}"
    d.text((W-70-d.textlength(pg, font=SANS(28)), H-110), pg, font=SANS(28), fill=J_SUB)
    return img

JEJAK = [
    ("MULAI DARI NIAT", "5 Tanda Kamu Siap Menjalani Taaruf",
     "Taaruf bukan jalan pintas — ia proses saling mengenal dalam adab, menuju pernikahan. Kesiapan itu bisa dibaca tandanya.",
     "GESER SATU-SATU", "geo"),
    ("TANDA 1", "Niatmu lurus karena Allah",
     "Bukan karena desakan umur, bukan pelarian dari sepi — tapi ibadah yang memang ingin kamu jalani.", "", "dot"),
    ("TANDA 2", "Kamu siap jujur tentang dirimu",
     "Taaruf bertumpu pada keterangan yang benar: keadaan, kebiasaan, dan kekuranganmu sendiri.", "", "dot"),
    ("TANDA 3", "Kamu siap secara lahir",
     "Pekerjaan atau jalan rezeki yang sedang kamu bangun dengan sungguh-sungguh, dan restu keluarga yang kamu usahakan.", "", "dot"),
    ("TANDA 4", "Kamu tahu apa yang kamu cari",
     "Kriteria yang realistis dan tertulis jelas — bukan daftar sempurna, tapi kejujuran tentang prioritas, termasuk apa yang bisa kamu beri.", "", "dot"),
    ("TANDA 5", "Kamu siap pada prosesnya",
     "Ada perantara, ada pertukaran keterangan tertulis, ada kemungkinan tidak berlanjut — dan kamu menerimanya dengan lapang.", "", "dot"),
    ("LANGKAH BERIKUTNYA", "Siap memulai dengan adab?",
     "Fasilitasi taaruf kami berjalan dengan mahram dan keterangan tertulis, tanpa janji berlebihan. Kirim DM dengan kata TAARUF untuk tata cara pendaftarannya.",
     "JEJAK TAARUF — DENGAN ADAB", "geo"),
]

for i, (kick, big, body, foot, motif) in enumerate(MELLOW, 1):
    p = os.path.join(OUT, f"mellowdy_kartu{i}.png")
    m_card(i, len(MELLOW), kick, big, body, foot, motif).save(p); print("saved", p)
for i, (kick, big, body, foot, motif) in enumerate(JEJAK, 1):
    p = os.path.join(OUT, f"jejak_kartu{i}.png")
    j_card(i, len(JEJAK), kick, big, body, foot, motif).save(p); print("saved", p)
print("done")
