# ACE Fase 2 — Hasil Pilot A/B/C v1 (2026-11-12)

Eksekusi persis sesuai pra-registrasi `pilot-abc-v1` (protocol_hash
`bce010ab273183f3…`, Addendum 15). Evidence mentah:
`pilot_abc_v1_report.json`. Waktu jalan 13,6 detik; **audit kernel
CLEAN**; kontrol negatif (lengan null) 0/200 sebagaimana wajib;
target sampel PRD terlampaui (held-out pricing 115, shipping 85;
target ≥30).

## Hasil utama

| Lengan | Held-out (pooled) | Pricing | Shipping |
|---|---|---|---|
| A — Fixed | 190/200 (94,9%) | 105/115 | 85/85 |
| B — Adaptive | 190/200 (94,9%) | 105/115 | 85/85 |
| C — Evolutionary | 190/200 (94,9%) | 105/115 | 85/85 |
| Null (kontrol) | 0/200 | 0/115 | 0/85 |

**Δ(C−A) = 0,0 poin persentase.** Hipotesis keunggulan mekanisme
adaptif/evolusioner **TIDAK DIDUKUNG** pada semesta tugas ini.

## Mengapa nol — analisis plafon

Ini bukan pilot yang gagal; ini pilot yang bekerja dan mengukur
hasil nol, dengan sebab yang teridentifikasi:

1. **Substrat v2 menjenuhkan semesta.** Operator pengali menutup
   kelemahan shipping sepenuhnya (85/85 untuk semua lengan), dan
   pada fitness train pun konfigurasi awal sudah di plafon — tidak
   ada ruang kepala (headroom) bagi adaptasi B atau mutasi C untuk
   menunjukkan nilai. Adaptasi tidak bisa mengalahkan konfigurasi
   yang sudah benar.
2. **Residu yang tak terpecahkan semua lengan identik**: 10 tugas,
   semuanya pricing level 3 dengan pasangan defek
   `member_basis + tax_basis`. Kedua defek adalah tukar-basis yang
   *berinteraksi*: memperbaiki satu saja tidak menaikkan skor kasus
   shown (yang lain masih merusak hasil), sehingga pendakian greedy
   tidak punya gradien satu-langkah — dataran fitness klasik.
   Mengatasinya butuh kelas kemampuan baru (pencarian lookahead/
   beam, atau operator berpasangan), bukan penataan ulang operator
   yang ada — persis jenis pertanyaan yang harus dijawab semesta
   tugas yang lebih keras.

## Pemetaan gerbang (dengan koreksi)

Agenda direktur dan dokumen desain menyebut pilot ini "evaluasi
G1". Teks PRD v0.1 menempatkan perbandingan A/B/C yang adil pada
tugas yang tidak digunakan selama evolusi sebagai **G2 — Ilmiah**.
Koreksi pemetaan ini dicatat agar kertas kerja kami tidak mewarisi
kesalahan label:

- **G2: kini TERUKUR.** Perbandingan A/B/C yang adil di bawah kustodi
  penuh sudah ada dan auditnya CLEAN — dengan hasil ilmiah nol:
  tidak ada keunggulan terukur dari mekanisme perbaikan-diri atas
  substrat tetap pada semesta ini. Apakah "terukur dengan hasil
  nol" memenuhi gerbang adalah penilaian direktur program/pemilik;
  yang tidak boleh terjadi adalah menyebutnya bukti keunggulan.
- **G1 tetap NOT_ASSESSED** (objeknya kemampuan coding umum pada
  tugas tak terlihat; pilot ini tidak mengubahnya).
- **OAIE tetap belum terbukti** (`oaie_proven=false`).

## Konsekuensi untuk tahap berikutnya

Pertanyaan riset berpindah: bukan lagi "apakah evolusi membantu"
pada semesta jenuh ini, melainkan (a) bangun semesta yang lebih
keras — defek berinteraksi, keluarga ketiga, level adversarial —
agar ada headroom yang bisa diukur; dan (b) uji kelas kemampuan
baru (lookahead/beam) terhadap residu berinteraksi yang kini
terkarakterisasi persis. Keduanya adalah bahan observasi untuk
siklus direktur berikutnya.
