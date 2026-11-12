# ACE Ω — Addendum 14, 2026-11-12: Fase 2 Tahap 2 — Pengukuran Shipping & Desain Pilot A/B/C

Dua item agenda siklus direktur #1 yang berada dalam mandat (Addendum
13) selesai dikerjakan. PR #116 (draft, bertumpuk di atas #115).

## Pengukuran kelemahan shipping (item direktur #3)

Diagnostik kausal atas 30 tugas (evidence: shipping_diagnostic.json),
dengan ablasi sinyal-oracle sebagai instrumen pemisah sebab:

- **Celah operator grammar — terbukti**: defek `multiplier_dropped`
  0/10 bahkan di bawah sinyal oracle. Grammar tidak punya operator
  pemulih pengali; ini kekurangan kemampuan, bukan informasi.
- **Gradien fitness token-search terlalu lemah**: defek
  `free_boundary` 0/10 dengan sinyal shown, **10/10 dengan oracle** —
  perbaikannya ada di ruang pencarian, tetapi fitness 2-kasus tidak
  memeringkatnya dalam anggaran.
- **Komposisi mewarisi keduanya** (0/10 shown semua solver).
- Eksposur bukan penjelas: semua tugas punya ≥1 kasus shown yang
  mengekspos defeknya.

Dokumen: `ACE_PHASE2_SHIPPING_MEASUREMENT_20261112.md`.

## Desain pilot A/B/C kustodi penuh (item direktur #1)

Dokumen: `ACE_PHASE2_PILOT_ABC_DESIGN_20261112.md`, dibangun dari
definisi PRD v0.1 (A Fixed / B Adaptive / C Evolutionary) dan kontrol
adilnya, diterjemahkan ke mesin Ω yang sudah ada: pra-registrasi +
kustodi split di kernel OMEGA-06, pewarisan C di arsip OMEGA-08,
mutasi C di OMEGA-09, adaptasi B dari memori OMEGA-07. Target sampel
PRD (≥30 held-out/keluarga, ≥3 pengulangan) diterjemahkan ke rencana
generasi (±150 tugas/keluarga); aturan INCONCLUSIVE wajib bila tak
tercapai.

Dua keputusan desain yang dicatat terang-terangan:

1. Celah operator shipping dipra-registrasi sebagai **confound**:
   substrat solver v2 (dengan operator pemulih pengali) dibekukan
   untuk SEMUA lengan sebelum pra-registrasi — pilot tidak boleh
   mengukur bug yang sudah diketahui.
2. Pilot v1 **tanpa LLM**: mekanisme seleksi/adaptasi/evolusi diuji
   murni algoritmik (deterministik, Rp0), sesuai pertanyaan terbuka
   PRD sendiri. Di dalam pilot, arah adalah mekanisme ACE sendiri.

**G1 tetap NOT_ASSESSED** sampai pilot berjalan dan audit kernelnya
CLEAN. Tahap berikutnya: bangun substrat v2 + harness pilot sesuai
desain ini, pra-registrasi, lalu jalankan.
