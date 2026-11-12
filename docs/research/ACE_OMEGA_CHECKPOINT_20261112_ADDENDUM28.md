# ACE Ω — Addendum 28, 2026-11-12: Tahap F — Generalisasi Grid Terukur: Hafalan Katalog

Pertanyaan resmi Addendum 26 dijawab lewat tiga putaran
pra-registrasi di kernel OMEGA-06 (dokumen lengkap:
`docs/research/ACE_GRID_GENERALIZATION_RESULTS_20261112.md`,
PR #128 harness, PR #129 hasil):

- **v1 — invalid oleh pagar validitasnya sendiri.** Set shown
  terkecil yang identifiable membuat kontrol katalog hanya 47%
  (garis 80%): kelaparan sinyal. Diagnosis tercatat (13/18
  kegagalan = pencarian tak mencapai shown-sempurna).
- **v2 — invalid oleh kontrol nolnya.** Set shown terbesar
  menyisakan holdout tanpa kasus gagal: kontrol nol
  "menyelesaikan" 64/114. Holdout tak diskriminatif.
- **v3 — sah.** Pool 20 kasus, shown dibatasi failing−3 (setiap
  holdout ≥3 kasus gagal), protocol hash
  `65358f5895148893…`, audit CLEAN, kontrol katalog 33/34,
  kontrol nol 0/113.

**Hasil v3: A = B = C = 0/47 pada kelas defek di luar katalog**
(dist_step_2, bounds_off_by_one, returns_start_distance,
wall_char_x), mixed 2/32, kontrol 33/34. Kompetensi substrat
berhenti persis di batas katalog operatornya; wall_char_x — gejala
sama dengan walls_passable, mekanisme berbeda — membuktikan
substrat mencocokkan mekanisme yang dikenal, bukan gejala.
Ketiga lengan identik di mana-mana: ruang operator 3 buah tak
memberi ruang bagi pembelajaran urutan/subset untuk berbeda.

Konsekuensi program yang tercatat: pertumbuhan kemampuan
berikutnya adalah **pertumbuhan katalog itu sendiri** — operator
baru yang ditemukan/diusulkan oleh mekanisme ACE (direktur riset
lokal / sintesis operator), bukan operator tulisan tangan per
kelas dan bukan penyetelan lengan. Ini menjadi kandidat tahap
terukur berikutnya bersama antrean yang sudah ada (instrumen G1;
uji portabilitas otak / latihan pemecatan otak — Tahap G).

Status gerbang tidak berubah oleh addendum ini.
