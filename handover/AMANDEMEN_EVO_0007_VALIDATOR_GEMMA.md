# AMANDEMEN EVO 0007 §11 — Parser validator fleksibel; validator kode berpindah ke Gemma 4 31B

Status: AMANDEMEN ARAHAN PEMILIK, 2026-11-18 21:35 WIB
("cara termudahnya ya buat fleksibel"), dieksekusi
2026-11-19 dini hari. Mengamendemen PRAREGISTRASI_EVO_0007
FINAL (PR #311) dan melengkapi Amendemen §10 pada dua titik:
semantik penerimaan jawaban validator, dan identitas organ
validator kode untuk baris yang belum tersegel. Semua
ketentuan lain berdiri utuh — khususnya parser judge TIDAK
berubah sama sekali.

## 1. Yang berubah

(a) **Parser validator fleksibel** — fungsi baru
`parse_validator_output(text) -> bool` menggantikan
pemeriksaan kaku `startswith("RATIFY")` di run_episode():
  1. teks yang diawali RATIFY → True (perilaku lama persis);
  2. selain itu, kemunculan kata RATIFY/REJECT (word-
     boundary, case-insensitive) pada paruh kedua teks:
     kemunculan TERAKHIR menentukan;
  3. tidak ada kemunculan yang memenuhi syarat → False
     (fail-closed, sama seperti sebelumnya).

(b) **Validator kode** → ("gemini", "gemma-4-31b-it"),
melengkapi §10 (proposer bahasa sudah Gemma). Dengan ini
tidak ada lagi peran Gemini-flash di sisa lengan; penghambat
napas ember hilang dari jalur kritis.

## 2. Bukti yang mendasari

- Dua output Gemma nyata (smoke 2026-11-18, prompt validator
  PERSIS milik runner, proposal sempurna): keduanya menaruh
  vonis di ujung analisis ("...requirements.RATIFY",
  "RATIFY: <alasan>") — terbaca benar oleh aturan baru,
  tertolak oleh aturan lama.
- Implementasi ditulis Codex atas prompt pemilik
  (branch codex/evo0007-flexible-validator @ ec92a9f3),
  disaring Ian baris demi baris: cocok spesifikasi, diff
  minimal (satu fungsi + satu call-site + tes), parser judge
  dan ORGAN_ROLES tidak disentuh Codex.
- Tes modul 33/33 hijau (21 lama + 12 baru, termasuk kedua
  kutipan Gemma nyata dan tes routing ujung-ke-ujung).
- **Set validasi hidup** (gerbang bernama sebelum organ
  berpindah): 4 kasus berkunci pasti dijalankan lewat
  Gemma 4 31B + parser baru — proposal benar (add) → RATIFY;
  proposal salah operator → REJECT; proposal mengabaikan
  syarat eksplisit (divide tanpa penjaga nol) → REJECT;
  proposal benar (divide berpenjaga) → RATIFY. **4/4 benar.**
  Rekaman: stage out/gemma_validator_validation.json.

## 3. Batas dan pencatatan

Berlaku dari baris tersegel ke-66; baris 1–65 berdiri di
bawah parser lama + organ lama dan tidak dijalankan ulang.
Setiap baris mencap brain_validator-nya, dan konsolidasi
WAJIB menabulasikan komposisi per lengan serta menyebut
perubahan semantik validator ini sebagai keterbatasan
bernama vonis §6 — aturan baru adalah superset aturan lama
(setiap jawaban yang lolos aturan lama lolos aturan baru),
tetapi gerbang validator set-baru tidak identik dengan
set-lama, dan itu dikatakan apa adanya.

## 4. Ketahanan transport (dicatat, bukan diam-diam)

Tier gratis Gemma terukur melempar HTTP 503 "high demand"
berkala malam 18–19 Nov (±1 dari 2 panggilan pada satu
jendela pengamatan). Driver lengan (alat stage, bukan
instrumen beku) diberi retry terbatas untuk galat kelas-503
saja: maks 4 percobaan, jeda 45 detik; panggilan gagal tidak
menghasilkan baris; retry habis = berhenti seperti
sebelumnya (resume-safe). Kelas kuota tetap jeda bersih;
kelas lain tetap stop-on-first-error.
