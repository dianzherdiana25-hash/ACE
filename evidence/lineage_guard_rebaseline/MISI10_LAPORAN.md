# MISI 10 — LAPORAN RE-BASELINE KONFIRMASI DI MAIN BARU

Tanggal: 2026-11-15. Kode: origin/main `7541782`. Rumah eksekusi: **VM Ian**
(bukan sandbox: discovery butuh kode main baru, bukan populasi kustodi;
pintu SSH sandbox terblokir re-auth Tailscale pemilik sejak 14 Nov 05:22;
pintu MCP 1-CPU dan butuh transfer kode — biaya wall time di VM diterima).

Cakupan: DISCOVERY SAJA. Tidak ada sel, tidak ada larian tersegel, tidak
ada vonis. Paket ini hanya menetapkan ulang digest katalog band konfirmasi
di bawah kode main baru.

## Metode

Driver `~/workspace/misi10-args/discover_bands.py` (pola probe R5):
`build_universe(seed)` → `drv.split_universe` → `drv.run_discovery(pool,
evaluation, control, pair_pool, chain_pool=pair_pool, adapter=GRID_ADAPTER)`
→ `drv._extract_admitted` + `drv.catalog_digest`. Checkpoint atomik per
band (tmp+fsync+os.replace); band yang tersimpan dilewati saat lanjutan.

Jalannya discovery: tiga kali peluncuran karena VM restart dua kali pagi
ini (restart ~07:13 WIB memotong lanjutan pertama di tengah band 20261802;
restart ~09:14 WIB memotong lanjutan kedua setelah ~8 menit; restart
ketiga ~11:14 WIB terjadi sesudah ALL DONE ~11:11 WIB — tidak memotong
discovery, hanya sesi pelaporan). Band 20261801 selamat lewat checkpoint
di setiap lanjutan; tidak pernah diulang.

## Hasil per band

| Band | Detik | Keys | Chains | Catalog digest |
|------|------:|-----:|-------:|---|
| 20261801 | 1527,7 | 6 | 2 | `a9ddf613eda090d88897866444f7db274aeb89b3f50cf3e375363fa0d056e711` |
| 20261802 | 2966,0 | 60 | 1 | `3aab94cf1b8847a5a6a958d443ef19494b1c2fc7fb96d58c4a47d99812dd8df7` |
| 20261803 | 1087,6 | 6 | 0 | `465508efbe082f31a3f87ccf01742cfc43fb76c97477577027a9bc0e44c35913` |

Semua band: pool 12, control 34, pair_pool 6; evaluation 29 (01) / 30
(02, 03).

Verifikasi (verifier `verify_digests.py`, kode main 7541782): ketiga
digest DIHITUNG ULANG dari berkas discovery yang tersimpan via
`_extract_admitted` + `catalog_digest` → **ALL MATCH** (lihat
`digest_verification.json`). Jumlah keys/chains record cocok dengan
hitungan ulang.

## Temuan utama: band 20261802 TIDAK LAYAK

Katalog band 20261802 menerima ALAMI kunci kausal registry
`('name_swap', (5, 2, 3, 0, 1, 4), 'nc')` — kunci yang sama yang
konstruksi infected-nya "ditanam" di ujung katalog — ditambah dua varian
'nc' lain (`(5, 2, 3, 0, 2, 4)` dan `(5, 2, 3, 2, 0, 1, 0)`).
Total 3 kunci name_swap 'nc' dari 60 kunci admitted.

Ini efek langsung ekspansi Stage L2 di main baru: name_swap kini
ditemukan massal (band ini menerima 60 kunci, 40 di antaranya
name_swap, termasuk `unary_not`, `compare_swap`, `subscript_index` —
skema baru L2). Band 20261801/03 hanya menerima 6 kunci skema lama
dan tidak terkena.

Akibat: konstruksi infected (tambah kunci kausal di ujung katalog)
menjadi degenerat — lineage 'nc' bukan lineage asing yang ditanam,
melainkan lineage asli band. **Band 20261802 TIDAK BOLEH dipakai
sebagai band konfirmasi.** Pengganti yang diusulkan: seed **20261804**
(berikutnya dalam blok yang sama, tetap disjoin); discovery pengganti
belum dijalankan — hub menamai seed pengganti pada saat penguncian,
atau memerintahkan Ian menjalankannya.

## Catatan lain

- Digest band 20261803 (`465508ef…`) SAMA dengan digest band Stage 3
  20261603: himpunan admitted-nya identik (6 kunci yang sama, 0 chain).
  Penjelasan, bukan anomali — sama seperti kasus 20261702 di Misi 9.
- Kunci band 20261801 = 6 kunci skema lama yang sama seperti 20261803,
  tetapi dengan 2 chain → digest berbeda (`a9ddf613…`).
- Draf isian akta (`ACT_FIELDS_DRAFT_20261115.md`): Isian 1 tetap
  (PR #192); Isian 2 terisi digest + catatan ketidaklayakan 20261802;
  Isian 3 prosedur snapshot registry (suplemen baterai masih menunggu
  konfirmasi digest kancuto — snapshot BELUM boleh diambil); Isian 4
  rumah eksekusi sandbox custody, pintu dinamai saat penguncian
  (catatan keadaan: SSH terblokir, chown root:root → ubuntu:ubuntu
  tertunda, MCP 1-CPU); Isian 5 jendela dinamai hub sesudah clean-logout
  tutup.
- Sandbox TIDAK TERJANGKAU selama paket ini dibangun (kedua pintu MCP
  HTTP 502 sejak 09:53 WIB, 15 Nov) — tidak memengaruhi paket ini
  (discovery di VM, dorongan via GitHub), tetapi memengaruhi langkah
  lanjutan yang butuh kustodi (suplemen, snapshot, larian tersegel).

## Yang masih tertunda (bukan bagian misi ini)

- Seed pengganti 20261804: discovery belum dijalankan (menunggu kata hub).
- Clean-logout: masih terbuka (gerbang keras, sisi operator).
- Suplemen baterai: transfer menunggu konfirmasi digest kancuto.
- Larian tersegel: menunggu clean-logout tutup + akta hub + tiga band LAYAK.

## Penutup — band pengganti 20261804 (15 Nov 2026, perintah hub ~12:52)

- Discovery dijalankan dua kali: luncuran 12:53 (PID 13470) mati oleh
  restart VM ~17:15 (restart ke-4 hari ini) sebelum menghasilkan output;
  relaunch 19:10 (PID 13922) SELESAI dalam 1.328,17 dtk: pool 12,
  evaluation 30, control 34, pair_pool 6; 6 keys / 1 chain.
- Digest katalog `5005072890bf608dc78a98965e6c9a3bf729a517c9689a12a9ccc051cbbaf62a`
  — hitung ulang dari berkas discovery (verify_digests.py diperluas ke
  empat band): MATCH; keempat band ALL_MATCH.
- Kelayakan: kunci kausal `('name_swap', (5, 2, 3, 0, 1, 4), 'nc')` TIDAK
  diterima alami; nol kunci name_swap sama sekali → **LAYAK** sebagai band
  konfirmasi. Cabang berhenti (bila 'nc' diterima alami) TIDAK terpicu;
  tidak ada seed lain yang dibakar.
- Digest 20261804 sama dengan digest band record tak-diratifikasi
  20261701: himpunan admitted identik (6 kunci skema lama yang sama,
  1 chain) — penjelasan, bukan anomali (preseden: 20261803 = 20261603 =
  20261702).
- TIGA BAND KONFIRMASI FINAL: 20261801 (`a9ddf613…`), 20261803
  (`465508ef…`), 20261804 (`50050728…`). Band 20261802 tetap tercatat
  sebagai band discovery yang DITOLAK.
- Butir tertunda di badan laporan yang kini TUTUP: "Seed pengganti
  20261804: discovery belum dijalankan". Sisanya tidak berubah:
  clean-logout masih terbuka (sisi operator), suplemen baterai menunggu
  konfirmasi digest kancuto, larian tersegel menunggu akta hub.
