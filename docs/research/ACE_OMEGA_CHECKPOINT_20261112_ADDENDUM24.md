# ACE Ω — Addendum 24, 2026-11-12: Laporan Lengkap Pilot A/B/C untuk Pemilik

Ringkasan resmi Fase 2 untuk pemilik, atas keputusan direktur dari
ruang diskusi. Semua angka dari laporan kernel yang teraudit
(audit CLEAN di kedua pilot; kontrol negatif 0 di kedua pilot).

## Pilot v1 (kurikulum lama, shown 2 kasus) — Addendum 16

Held-out 200 (pricing 115, shipping 85), 3 repetisi, anggaran 200.

| Lengan | Total | Pricing | Shipping |
|---|---|---|---|
| A — Fixed | 190/200 | 105/115 | 85/85 |
| B — Adaptive | 190/200 | 105/115 | 85/85 |
| C — Evolutionary | 190/200 | 105/115 | 85/85 |
| Null | 0/200 | 0/115 | 0/85 |

Δ(C−A) = 0.0pp. Residual 10 tugas: satu bentuk (pricing L3,
member_basis+tax_basis) — kemudian terdiagnosis sebagai perangkap
identifiabilitas shown, bukan dataran fitness (Addendum 17).

## Pilot v2 (kurikulum hasil amendemen, level 1–4) — Addendum 21

Held-out 220 (pricing 135, shipping 85), hash protokol
babfd459b35ddaa1….

| Lengan | Total | Pricing | Shipping |
|---|---|---|---|
| A — Fixed | 220/220 | 135/135 | 85/85 |
| B — Adaptive | 220/220 | 135/135 | 85/85 |
| C — Evolutionary | 220/220 | 135/135 | 85/85 |
| Null | 0/220 | 0/135 | 0/85 |

Δ(C−A) = 0.0pp oleh saturasi total: sinyal shown yang teridentifikasi
+ dapat didaki menaikkan lantai sampai lengan tetap pun sempurna.

## Keluarga grid (di luar pilot A/B/C)

| Pengukuran | Hasil |
|---|---|
| Token-search generik (anggaran 400) | 0/58 |
| Substrat struktural (PR #125) | **58/58** |

Grid belum masuk semesta A/B/C: substratnya baru lahir dan ditulis
terhadap katalog defek yang dikenal; memasukkannya sekarang akan
mengukur hafalan operator, bukan adaptasi.

## Status gerbang terbaru (apa adanya)

- **G0**: PASS, lingkup sesi (tidak berubah).
- **G1**: NOT_ASSESSED (tidak berubah; pilot A/B/C bukan instrumen G1
  — koreksi pemetaan Addendum 16).
- **G2**: MEASURED, hasil nol dua kali (v1 oleh saturasi substrat,
  v2 oleh saturasi sinyal). Dua pengukuran independen menutup
  pertanyaan "apakah adaptasi/evolusi membantu pada medan uji ini"
  dengan jawaban: tidak terukur adanya — medan ujinya yang habis,
  bukan satu kegagalan tunggal.
- **G3–G5**: NOT_ASSESSED. OAIE: belum terbukti (oaie_proven=false).

Tidak ada angka di laporan ini yang dinaikkan statusnya melebihi
buktinya.
