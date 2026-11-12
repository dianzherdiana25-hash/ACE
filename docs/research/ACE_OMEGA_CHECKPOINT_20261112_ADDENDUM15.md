# ACE Ω — Addendum 15, 2026-11-12: Fase 2 Tahap 3 — Harness Pilot & Pra-Registrasi

Substrat v2 dan harness pilot A/B/C selesai dibangun dan pilot yang
sebenarnya **sudah dipra-registrasi di kernel sebelum lengan mana pun
berjalan**. PR #117 (draft, bertumpuk di atas #116).

## Substrat v2 (confound ditutup sesuai desain)

Operator grammar OMEGA-11 dikelompokkan ulang (boundary, basis,
nudge) dan ditambah operator yang pengukuran shipping buktikan
hilang: **multiplier** (pulihkan konstanta pengali dari spec). Test
regresi menguncinya: tugas multiplier murni yang v1 nilai 0/10
(bahkan di bawah oracle) kini terpecahkan oleh v2, dan konfigurasi
tanpa operator itu tetap tidak bisa memecahkannya. `reasoning_lab`
v1 dibiarkan beku sebagai catatan OMEGA-11.

## Harness (sesuai desain PR #116)

- **A Fixed**: konfigurasi beku. **B Adaptive**: urutan operator
  disusun ulang antarsiklus dari kredit per-grup yang diperoleh HANYA
  di tugas train. **C Evolutionary**: populasi konfigurasi dimutasi
  dan diseleksi atas fitness train, silsilah lengkap terekam di arsip
  OMEGA-08.
- Kustodi kernel OMEGA-06: pra-registrasi, digest evaluator/fixture,
  artefak metode tiap lengan, semua hasil; lengan null sebagai
  kontrol negatif; held-out hanya disentuh evaluasi akhir.

## Pra-registrasi pilot yang sebenarnya (terverifikasi)

- Eksperimen `pilot-abc-v1`, **protocol_hash
  `bce010ab273183f3…`**, tersimpan di kernel persisten sebelum ada
  hasil apa pun.
- Semesta: 900 tugas (3 repetisi × 2 keluarga × level 1–3 × 50 seed),
  200 di antaranya held-out — **pricing 115, shipping 85**, keduanya
  melampaui target PRD ≥30 per keluarga. Aturan sampel tidak akan
  menjadi alasan INCONCLUSIVE.
- Aturan lulus terdaftar: held-out solve rate ≥ 0,5 per lengan;
  bahasa keputusan komparatif mengikuti dokumen desain.

6 test pilot lulus; sapuan paket penuh **199 test OK (10 skip)**,
termasuk pilot asap dengan audit kernel CLEAN dan kontrol negatif
di 0,0.

Tahap berikutnya adalah eksekusi pilot pada semesta terdaftar ini,
lalu audit dan pemetaan hasil ke bahasa penilaian G1. **G1 tetap
NOT_ASSESSED sampai saat itu.**
