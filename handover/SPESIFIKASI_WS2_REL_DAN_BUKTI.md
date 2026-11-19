# Spesifikasi WS-2 — Rel yang Dicakup & Kriteria Bukti per Rel

Ditetapkan Ian, 2026-11-19. Dokumen ini adalah rujukan
berdiri untuk WS-2 (verifikator pendapatan + generator
laporan) dan untuk Garis H1 Program Codex Jauh. Ia menjawab
penghambat yang dicatat Codex di PR #331: rel mana yang
diverifikasi, bukti wajib per rel, dan aturan penerimaannya.

## Aturan umum (semua rel)

Pendapatan terverifikasi = TIGA bukti cocok:
1. catatan platform,
2. catatan penarikan/pencairan,
3. mutasi rekening/e-wallet penerima.

Status **COCOK PENUH** hanya bila:
- nominal sama persis (rupiah bulat) di ketiga bukti;
- nama penerima "Dian Herdiana" bila field nama tersedia;
- tanggal berurutan: periode platform ≤ penarikan ≤ mutasi,
  dengan mutasi paling lambat `--max-lag-days` hari sesudah
  penarikan (default 14; jadikan argumen perkakas).

Status lain:
- **SEBAGIAN** — dua dari tiga cocok; laporan menyebutkan
  kaki yang meleset.
- **HILANG** — satu kaki tidak ada; tidak pernah dianggap
  nol dan tidak pernah diisi karangan.
- **REL TAK TERDAFTAR** — catatan dari rel di luar §Rel di
  bawah; tidak pernah diloloskan sebagai terverifikasi.

Nomor rekening penuh TIDAK PERNAH disimpan di berkas mana
pun — yang dicatat hanya nama + platform + nominal +
tanggal.

## Rel 1 — KBM → SeaBank (rel hidup program)

- Kaki platform: laporan royalti KBM. Keluaran
  `tools/royalty_track.py` (ringkasan CSV per bulan) boleh
  menjadi salah satu format masukan kaki platform;
  perkakas itu tidak diubah oleh WS-2.
- Kaki penarikan: catatan pencairan KBM.
- Kaki mutasi: mutasi SeaBank penerima.
- Satuan pencocokan: PERISTIWA PENCAIRAN (KBM membayar
  bulanan, minimum Rp15.000), bukan per bab dan bukan
  per bulan kalender.

## Rel 2 — Fastwork → rekening bank

- Kaki platform: riwayat penarikan Fastwork.
- Kaki penarikan: catatan penarikan Fastwork, yang WAJIB
  memuat biaya penarikan sebagai field eksplisit.
- Kaki mutasi: mutasi rekening bank penerima.
- Nominal mutasi yang diharapkan = nominal bruto penarikan
  − biaya tercatat. Biaya TIDAK boleh di-hardcode atau
  dikarang: syarat biaya Fastwork di catatan program belum
  terverifikasi (Rp3.000 tetap vs gratis bertentangan);
  perkakas membaca biaya dari catatan penarikan. Bila
  field biaya absen, status kaki itu HILANG, bukan nol.

## Rel 3 — GoPay / QRIS (rel langsung)

- Kaki platform: laporan penyelesaian (settlement)
  GoPay/QRIS.
- Kaki penarikan: catatan transfer keluar dari platform
  dompet/QRIS.
- Kaki mutasi: mutasi GoPay atau SeaBank penerima.

## Di luar cakupan

- **Facebook** — syarat misinya belum terverifikasi di
  program ini. Setiap catatan Facebook di masukan
  diklasifikasikan REL TAK TERDAFTAR.
- Rel lain yang belum tercantum di dokumen ini juga REL
  TAK TERDAFTAR sampai Ian menambahkannya lewat revisi
  dokumen ini.

## Kewajiban tes yang lahir dari spesifikasi ini

- Satu fixture COCOK PENUH per rel (Rel 1, 2, 3).
- Fixture Fastwork dengan biaya tercatat: mutasi ≠ bruto
  tetapi = neto → COCOK PENUH; fixture yang sama dengan
  biaya diabaikan → TIDAK COCOK.
- Fixture rel tak terdaftar (Facebook) → REL TAK TERDAFTAR.
- Fixture kaki absen → HILANG (bukan nol, bukan SEBAGIAN
  yang lolos).
- Fixture jendela tanggal: mutasi melewati
  `--max-lag-days` → bukan COCOK PENUH.
