#!/usr/bin/env python3
"""Pos pekanan @jejaktaaruf #2 (DRAF bentuk final untuk penilaian hub, TAK-TERBIT):
carousel 9 kartu "7 Tahap Taaruf yang Benar" — sistem visual sama dengan pos pertama jejak."""
from PIL import Image, ImageDraw, ImageFont
import math, os

W, H = 1080, 1350
OUT = os.path.dirname(os.path.abspath(__file__))
FD = "/usr/share/fonts/truetype/dejavu"
def F(n, s): return ImageFont.truetype(os.path.join(FD, n), s)
SERIF_B = lambda s: F("DejaVuSerif-Bold.ttf", s)
SANS_B  = lambda s: F("DejaVuSans-Bold.ttf", s)
SANS    = lambda s: F("DejaVuSans.ttf", s)

J_BG, J_INK, J_SUB, J_ACC, J_GOLD = (250,247,238), (43,54,44), (110,116,104), (46,94,62), (176,141,74)

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
    for ln in wrap(d, text, font, W-220):
        w_ = d.textlength(ln, font=font)
        d.text(((cx-w_/2), y), ln, font=font, fill=fill)
        y += font.size + spacing
    return y

def geo(d, cx, cy, s, color=J_GOLD):
    for ang in (0, 45):
        pts = []
        for k in range(4):
            a = math.radians(ang + k*90)
            pts.append((cx + s*math.cos(a), cy + s*math.sin(a)))
        d.polygon(pts, outline=color, width=4)
    d.ellipse([cx-10, cy-10, cx+10, cy+10], fill=color)

CARDS = [
    ("TAHAP DEMI TAHAP", "7 Tahap Taaruf yang Benar",
     "Taaruf yang dijaga adabnya berjalan bertahap — tidak dilompati, tidak dipercepat. Ini urutan yang kami jaga di Jejak Taaruf.",
     "GESER SATU-SATU", "geo"),
    ("TAHAP 1", "Selalu ada perantara",
     "Sejak awal melibatkan pihak ketiga yang amanah — keluarga atau fasilitator. Tidak ada komunikasi berdua yang bebas.", "", "dot"),
    ("TAHAP 2", "Bertukar keterangan tertulis",
     "Biodata atau CV taaruf dipertukarkan lebih dulu: identitas, keluarga, pekerjaan, dan kriteria — jujur sejak kertas pertama.", "", "dot"),
    ("TAHAP 3", "Menggali yang perlu ditanya",
     "Pertanyaan disampaikan lewat perantara: visi berkeluarga, kebiasaan ibadah, rencana tempat tinggal, dan hal-hal prinsip lainnya.", "", "dot"),
    ("TAHAP 4", "Istikharah",
     "Sesudah keterangan cukup, minta petunjuk dengan salat istikharah — keputusan tidak digantungkan pada rasa semata.", "", "dot"),
    ("TAHAP 5", "Nadzhar, dengan adab",
     "Bila mantap melanjutkan, nadzhar dilakukan dalam batas syariat dan didampingi mahram — bukan pertemuan berdua.", "", "dot"),
    ("TAHAP 6", "Keputusan dalam batas waktu",
     "Hasilnya dinyatakan dengan jelas dan terhormat. Berlarut-larut tanpa keputusan menggerus kehormatan kedua pihak.", "", "dot"),
    ("TAHAP 7", "Khitbah — atau berhenti dengan adab",
     "Cocok: lanjut ke khitbah. Tidak cocok: proses ditutup dengan baik, keterangan dikembalikan, dan tidak ada cerita yang disebar.", "", "dot"),
    ("LANGKAHMU", "Mau berjalan dengan urutan yang benar?",
     "Di Jejak Taaruf setiap proses dijaga perantara dan keterangan tertulis. Kirim DM dengan kata TAARUF untuk tata cara pendaftarannya.",
     "JEJAK TAARUF — DENGAN ADAB", "geo"),
]

for i, (kick, big, body, foot, motif) in enumerate(CARDS, 1):
    img = Image.new("RGB", (W, H), J_BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([26, 26, W-26, H-26], radius=30, outline=J_GOLD, width=3)
    d.text((70, 66), "JEJAK TAARUF", font=SANS_B(30), fill=J_ACC)
    r = d.textlength("EDUKASI", font=SANS(26))
    d.text((W-70-r, 68), "EDUKASI", font=SANS(26), fill=J_SUB)
    d.text((70, 118), kick, font=SANS_B(27), fill=J_SUB)
    y = 190
    if motif == "geo":
        geo(d, W//2, 330, 92); y = 500
    else:
        d.ellipse([W//2-16, 300, W//2+16, 332], fill=J_GOLD); y = 420
    y = centered(d, W//2, y, big, SERIF_B(60), J_INK, 16)
    y += 26
    if body:
        y = centered(d, W//2, y, body, SANS(37), J_SUB, 14)
    if foot:
        d.text((70, H-110), foot, font=SANS(28), fill=J_SUB)
    pg = f"{i} / {len(CARDS)}"
    d.text((W-70-d.textlength(pg, font=SANS(28)), H-110), pg, font=SANS(28), fill=J_SUB)
    p = os.path.join(OUT, f"jejak2_kartu{i}.png")
    img.save(p); print("saved", p)
print("done")
