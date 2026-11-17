# DRAF ISIAN AKTA — LINEAGE-GUARD CONFIRMATION, RE-BASELINE 20261115

Status: DRAF FINAL (Misi 10 + lanjutan band pengganti 20261804, 15 Nov
2026). Bukan akta terkunci. Akta terkunci adalah lima isian
yang dilengkapi ke dalam teks PR #188 (langkah 4 urutan aktivasi), dan
mengunci hanya sesudah butir clean-logout TUTUP + hub menamai jendela lari.
Larian tersegel TIDAK terjadi di bawah draf ini.

## Konteks yang mengikat draf ini

- Record konfirmasi 5f2daf0 (band 20261701–20261703, vonis GUARD_ADOPTED)
  TIDAK diratifikasi hub (15 Nov ~06:10 WIB): konsistensi internal angka
  diterima, tetapi gerbang keras clean-logout tidak terbukti dari record.
  Seed 20261701–20261703 TIDAK dipakai ulang.
- Re-baseline di main 7541782: discovery diulang di bawah kode baru
  (ekspansi Stage L2 mengubah katalog) — lihat
  `evidence/lineage_guard_rebaseline/rebaseline_summary.json`.

## Isian 1 — Referensi vonis pemicu (§8.1)

- PR #192 (head 0cfc1199), record `evidence/ctrlreg_stage3_official_record.json`:
  P1 REPRODUCED, P2 HELD, P3 HELD atas band 20261601–20261603.
- Status: TETAP. Tidak berubah oleh re-baseline.

## Isian 2 — Seed band konfirmasi (§8.2)

- **[20261801, 20261803, 20261804]** — tiga band LAYAK final (blok
  20261801–20261804; 20261802 ditolak dan diganti 20261804, lihat di
  bawah). Blok ini disjoin dari semua blok
  terpakai: 20261501–20261503 (dev), 20261601–20261603 (Stage 3),
  20261701–20261703 (record tidak diratifikasi).
- Namespace pendek profiling (2001–2012 dkk.) tidak disentuh.
- Digest katalog (diisi dari discovery re-baseline; terverifikasi hitung ulang
  dari berkas discovery, lihat `digest_verification.json`):
  - 20261801: `a9ddf613eda090d88897866444f7db274aeb89b3f50cf3e375363fa0d056e711`
    (6 keys, 2 chains) — LAYAK.
  - 20261802: `3aab94cf1b8847a5a6a958d443ef19494b1c2fc7fb96d58c4a47d99812dd8df7`
    (60 keys, 1 chain) — **TIDAK LAYAK sebagai band konfirmasi** (lihat di bawah).
  - 20261803: `465508efbe082f31a3f87ccf01742cfc43fb76c97477577027a9bc0e44c35913`
    (6 keys, 0 chains) — LAYAK. Digest ini SAMA dengan digest band Stage 3
    20261603 karena himpunan admitted-nya identik (6 kunci yang sama,
    0 chain) — penjelasan, bukan anomali.
  - 20261804: `5005072890bf608dc78a98965e6c9a3bf729a517c9689a12a9ccc051cbbaf62a`
    (6 keys, 1 chain) — LAYAK (band pengganti; discovery 15 Nov,
    1.328,17 dtk, digest terverifikasi hitung ulang, nol kunci
    name_swap). Digest ini SAMA dengan digest band record
    tak-diratifikasi 20261701 karena himpunan admitted-nya identik
    (6 kunci skema lama yang sama, 1 chain) — penjelasan, bukan anomali.
- Kode discovery: origin/main 7541782 (worktree wt-m9main), driver pola
  probe R5; rumah eksekusi discovery: VM Ian (lihat record).

## Kelayakan band 20261802 — TIDAK LAYAK (temuan re-baseline)

- Katalog band 20261802 menerima ALAMI kunci kausal registry
  `('name_swap', (5, 2, 3, 0, 1, 4), 'nc')` — kunci yang sama yang
  konstruksi infected-nya "ditanam" di ujung katalog. Ditambah dua varian
  'nc' lain: `(5, 2, 3, 0, 2, 4)` dan `(5, 2, 3, 2, 0, 1, 0)`.
  Total 3 kunci name_swap 'nc' dari 60 kunci admitted.
- Akibat: konstruksi infected (tambah kunci kausal di ujung) menjadi
  degenerat — lineage 'nc' bukan lagi lineage asing yang ditanam, melainkan
  lineage asli band. Band ini TIDAK BOLEH dipakai sebagai band konfirmasi.
  Ini efek langsung ekspansi Stage L2 di main baru (name_swap kini
  ditemukan massal); band 20261801/03 yang hanya menerima 6 kunci skema
  lama tidak terkena.
- PENGGANTI: seed **20261804** (berikutnya dalam blok yang sama, tetap
  disjoin dari semua blok terpakai) — SUDAH dijalankan atas perintah hub
  (15 Nov ~12:52; discovery saja, batas sama) dan terverifikasi LAYAK
  (6 keys / 1 chain; kunci kausal TIDAK diterima alami; nol kunci
  name_swap; lihat `digest_verification.json`). Tiga band konfirmasi
  final draf ini: **20261801, 20261803, 20261804**. Penguncian tetap
  langkah hub pada langkah 4, bukan draf ini.

## Isian 3 — Snapshot registry (§8.3)

PROSEDUR (wajib dijalankan pada saat penguncian, dari dalam kustodi —
nilai di bawah ini adalah nilai beku yang DIHARAPKAN, bukan snapshot):
1. Suplemen baterai (PR #195, tree digest
   f4d3c43bc86576e9c0eb16b95da7bb1eb42f62805b4733bcf558b1905654c5ef)
   sudah berada di kustodi + terverifikasi sisi penerima (kancuto).
   STATUS SAAT DRAF INI DITULIS: transfer masih menunggu konfirmasi
   digest kancuto — snapshot BELUM boleh diambil.
2. Dari dalam kustodi, baca
   `/workspace/ace-custody-lineage-guard/wt-battery/code/ace_operational/distractor_registry.json`,
   hitung sha256-nya di host, dan catat path + sha256 + ids.
3. Nilai yang diharapkan (dari manifest beku PR #195; cocokkan, jangan salin
   buta): sha256
   `f9d8982a1314cc5807f815dc700affd0c3dd9cf42ff2b35855a7704dc0911680`,
   ids `["name-swap-523014-nc-band20261501"]`.
4. Bila sha di kustodi ≠ nilai di atas, BERHENTI — snapshot tidak sah,
   laporkan ke hub; jangan lanjut ke penguncian.

## Isian 4 — Ruang eksekusi / operator

- Rumah eksekusi: sandbox custody `/workspace/ace-custody-lineage-guard`
  (populasi R5-terverifikasi, 80 file, tree digest c02221775c…).
- Pintu: DINAMAI pada saat penguncian. Catatan keadaan (diperbarui
  15 Nov sore): perbaikan ownership root:root → ubuntu:ubuntu (satu
  perintah operator) belum terjadi — direktori custody tetap tidak
  terbaca dari pintu SSH. Pintu SSH baru
  (sshremote@ace-sandbox.taild2ddcb.ts.net:443) terverifikasi jalan dari
  VM Ian 15 Nov ~19:20 (hostname 2887726280f4, di luar cgroup MCP),
  tetapi penggunaannya sebagai rumah eksekusi DITAHAN pemilik sejak
  ~19:23. Kedua pintu MCP HTTP 502 sejak 09:53 (diagnosis dari dalam:
  fronting eksternal manus.computer; sandbox sehat; server MCP di dalam
  tetap listening di 8765). Pintu TIDAK diputuskan oleh draf ini.

## Isian 5 — Jendela lari

- DINAMAI hub pada saat penguncian (langkah 4 urutan aktivasi), sesudah
  clean-logout tutup. Syarat jendela: rumah kosong semua pintu, tanda
  eksplisit "RUMAH KOSONG SEMUA PINTU" dari lane sebelumnya (bukan ALL_DONE
  log). Tidak ada jendela yang dijadwalkan oleh draf ini.

## Yang TIDAK ada di draf ini

- Tidak ada larian tersegel, tidak ada sel, tidak ada vonis.
- Tidak ada perubahan pada teks PR #188 (penguncian dilakukan hub pada
  langkah 4, bukan di sini).
