# ACE Status — 15 November 2026

Dokumen ini adalah **satu-satunya sumber kebenaran (Single Source of
Truth)** untuk status operasional dan capaian ilmiah repositori ACE
(`dianzherdiana25-hash/ACE`). Versi ini ditulis ulang dari bukti pada
15 November 2026 (batch kejujuran permukaan, PR pendamping dokumen
ini); versi 8 November 2026 digantikan — lihat §6.

---

## 1. Metadata

- **Tanggal Status:** 15 November 2026
- **Commit `main` Acuan:** `77cca3c6ec2a1f0f46647bff275ee796c1661e2b`
  (feat(engine): add mixed tech+language autonomy, loopback auth,
  and ace engine CLI)
- **Status Ilmiah Repositori:** `NOT_ASSESSED`
- **Invarian Rilis:** `release_gate=BLOCK_RELEASE`,
  `oaie_established=False` (lihat §5)

## 2. Papan Gerbang Ω (terverifikasi dari bukti tersegel)

| Gerbang | Status | Bukti |
| :--- | :--- | :--- |
| G1 | `DEMONSTRATED` | Instrumen G1 + paket bukti program |
| G2 | `NOT_DEMONSTRATED` | A/B/C v3: tiga hasil nol berturut-turut (Addendum 59) |
| G3 | `SPECIALIZATION` | Addendum papan gerbang program |
| G4 | `INHERITANCE_DEMONSTRATED` | Addendum 58 |
| G5 | `NOT_ASSESSED` | Jendela panen terkunci 12–30 Nov 2026; praregistrasi `g5-harvest-01` TERKUNCI (draf PR #227) |
| Gerbang Round-2 | `LIFT_DEMONSTRATED` | Addendum 60 |

Papan ini sama dengan papan Ω di dalam repo (Addendum 60 adalah
addendum tertinggi di `main` acuan).

## 3. Keadaan Program (berjangkar bukti)

- **Kecepatan solver:** parse-once/compile-once teradopsi (PR #180,
  rantai #178–#186). Klaim yang dapat dipertahankan: rasio median
  beban-sama 0,7312 (CI95 [0,7203–0,7450], ≈27% lebih cepat),
  ekuivalensi 0/72 mismatch. Garis kecepatan ISTIRAHAT di lantai
  strukturalnya.
- **Stage 3 resmi (PR #192):** P1 `REPRODUCED`, P2 `HELD`,
  P3 `HELD` pada band 20261601–20261603.
- **Lineage guard:** akta aktivasi lengkap (draf PR #225, §9 teks
  FULL PR #188) + manifes suplemen kustodi #2 beku; larian
  konfirmasi tersegel pada triple berurutan {20261803, 20261804,
  20261805} menunggu jendela bernama `JENDELA KONFIRMASI`.
- **Auth Web Studio:** lubang autentikasi misi 0002 (endpoint
  memori terbuka tanpa token) diperbaiki — semua rute `/api/*`
  tergating token WEB25; draf PR #224; 95 tes hijau terverifikasi
  di dua lingkungan (VM + sandbox, Python 3.12.3).
- **Proposer:** stage-1 v1 `NOT_PASSED` (PR #199, berlaku);
  v2 menjawab HANYA pertanyaan grammar-constrained decoding
  (Quality PASS); pertanyaan repair-loop belum terjawab;
  Stage 2 TERTUTUP (tidak ada praregistrasi khusus).
- **Bake-off 02:** Instrumen A SELESAI & FINAL (5 proposal,
  0 ditolak); B/C DITUNDA atas perintah pemilik; garis parkir.
- **Re-baseline band konfirmasi:** paket bukti Misi 10 (draf
  PR #226) — digest terverifikasi ALL MATCH; band 20261802
  DITOLAK (degenerat).

## 4. Hitungan Tes Kanonis

Satu-satunya hitungan yang boleh dikutip dari dokumen ini:

- **Metode:** `PYTHONPATH=code python3 -m unittest discover -s code -p 'test_*.py'`
  (loader `unittest.TestLoader().discover`, dihitung TANPA
  menjalankan tes).
- **Hasil di `main` acuan (77cca3c), 15 Nov 2026:** **1.449 test
  case terdaftar**.
- Angka lama "368/368 PASS" (versi 8 Nov) BASI dan tidak lagi
  berlaku. Klaim LULUS dibuat per-suite di dalam paket buktinya
  masing-masing (mis. 95 tes auth Web Studio di atas), bukan
  sebagai satu angka global.

## 5. Tata Kelola & Batasan Keras (Hard Invariants)

- **Biaya Keuangan:** **Rp0** — hanya komputasi lokal; tanpa API
  AI berbayar sebagai dependensi.
- **Invarian Rilis:** `release_gate=BLOCK_RELEASE`,
  `scientific_status=NOT_ASSESSED`, `oaie_established=False`.
- **Integritas Penilai:** Dilarang mengedit penilai/bank untuk
  meloloskan kandidat; dilarang merge ke `main` tanpa komentar
  `APPROVE-MERGE` dari pemilik repositori.
- **Identitas Agen:** Kode atau usulan dari Antigravity dicatat
  dengan provenance `ADVISOR_AGENT` (sesuai PRD FR-12).
- **Ratifikasi independen** adalah standar semua lini, dan
  kandidat self-dev hanya dihitung berhasil bila terhubung ke
  perilaku aktif + tes hijau — lihat
  `handover/GOVERNANCE_RULES_20261115.md`.

## 6. Catatan Penggantian (versi 8 November 2026)

Versi sebelumnya menyatakan di header `CONFIRMED_SEALED` —
bertentangan dengan bagiannya sendiri tentang invarian
(`NOT_ASSESSED`) — dan memuat angka serta klaim yang tidak lagi
terverifikasi (antara lain tabel "swarm 7 agen", angka §4 seperti
87,12% query reduction dan berbagai speedup, serta hitungan
368 tes). Semua itu TERSUSUL oleh dokumen ini; versi lama tetap
ada di riwayat git untuk keperluan audit, dan tidak boleh
dikutip sebagai status terkini.
