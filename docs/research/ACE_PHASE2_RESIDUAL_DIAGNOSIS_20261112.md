# ACE Fase 2 — Probe Residu Pilot: Bukan Pencarian, Melainkan Identifiabilitas Sinyal (2026-11-12)

Pertanyaan tahap ini: apakah kelas kemampuan lookahead/beam dapat
menyeberangi dataran fitness yang menghentikan ketiga lengan pilot?
Evidence: `beam_probe.json`, `residual_diagnosis.json`. Semesta uji:
15 tugas berbentuk residu pilot (pricing L3, defek
`member_basis + tax_basis`) + 45 tugas kontrol L3 lain dari seed yang
sama.

## Hasil probe

| Solver | Residu (15) | Kontrol (45) | Biaya eval rata-rata (residu) |
|---|---|---|---|
| Greedy v2 | 0 | 45 | 14,9 |
| Beam (lebar 4, kedalaman 4, anggaran 400) | 0 | 45 | 11,9 |

Lookahead **tidak** menyeberangi dataran itu — petunjuk bahwa
mekanismenya bukan yang kami kira.

## Diagnosis mekanistik (terverifikasi per tugas)

1. Pada **15/15** tugas residu terdapat *jebakan shown*: sebuah
   varian perbaikan-tunggal yang **sempurna pada 2 kasus shown**
   tetapi **salah pada holdout**. Pendakian greedy (dan beam, yang
   memakai fitness shown yang sama) berhenti di kode yang tampak
   selesai padahal defek kedua bersembunyi di wilayah yang tidak
   dicakup dua kasus itu.
2. Solver greedy **yang sama persis**, tanpa operator baru, dengan
   sinyal 4 kasus shown pengekspos memecahkan **15/15**.

## Kesimpulan

Kegagalan residu adalah **kegagalan identifiabilitas set shown**
pada kurikulum OMEGA-10: dua kasus shown tidak cukup mengidentifikasi
tugas dua-defek yang berinteraksi. Bukan kegagalan pencarian (beam
gagal dengan cara yang sama), bukan kegagalan operator (perbaikannya
ada dan terjangkau dalam ≤2 langkah). Ini juga menjelaskan sebagian
kelemahan gradien token-search pada pengukuran shipping: keluarga
masalah yang sama — sinyal terlalu miskin untuk membedakan hipotesis
perbaikan yang bersaing.

## Perbaikan yang terukur (untuk tahap pembangunan berikutnya)

Kriteria pemilihan kasus shown di OMEGA-10 harus ditambah syarat
identifiabilitas: **tidak boleh ada perbaikan parsial sejati yang
sempurna-di-shown** — untuk setiap subset defek yang diperbaiki
sebagian, minimal satu kasus shown tetap gagal; ukuran shown tumbuh
mengikuti jumlah defek. Kriteria ini dapat diuji otomatis saat
generasi tugas (validator kurikulum), sama seperti validitas dasar
yang sudah ditegakkan sejak OMEGA-10.
