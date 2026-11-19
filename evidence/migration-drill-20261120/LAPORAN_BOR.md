# LAPORAN BOR MIGRASI — E6 (2026-11-20)

Bor pemulihan rumah kedua dijalankan Ian langsung (sisa paket Antigravity
E4–E6/F, reassignment pemilik 2026-11-20 00:32) di VM Ian, seluruhnya di
direktori bor sementara di luar repo; tidak ada aktivasi, tidak ada berkas
produksi yang diubah oleh bor itu sendiri.

## Susunan bor

- Konfigurasi instans (`instance_kit --init`): sumber `ace-drill-src`
  (root `src-home/ace-drill-src`, port 18100/18101, lock `drill-src`) dan
  target `ace-drill-dst` (root `dst-home/ace-drill-dst`, port 18200/18201,
  lock `drill-dst`); keduanya `foundation_only: true`,
  `second_instance_active: false`. Workspace target dibuat lebih dulu
  sesuai prosedur WS-7.
- `instance_kit --validate src.json dst.json`: **isolated: true,
  violation_count: 0** (8 direktori, 4 port, tanpa tabrakan).

## Bundel dan kebijakan jalur

Percobaan pertama (7 berkas, termasuk `secrets/README.md` dan
`tools/secrets_bundle.py`) **ditolak rehearsal**: "bundle contains a path
outside the migration rehearsal policy". Penolakan ini BENAR menurut
desain — daftar `EXCLUDED` di `migration_rehearsal.py` melarang fragmen
"secret" pada jalur bundel bor, jadi materi bernama-secret tidak pernah
masuk jalur rehearsal; bundel rahasia punya jalurnya sendiri
(`tools/secrets_bundle.py`, GPG). Bundel dibentuk ulang tanpa keduanya.

Bundel final (6 berkas, 76.700 byte): `handover/BOOTSTRAP_RUMAH_BARU.md`,
`docs/ARSITEKTUR_ENGINE.md`, `tools/portability_pack.py`,
`tools/migration_rehearsal.py`, `tools/instance_kit.py`,
`tools/second_home.py`. Manifest SHA-256 (dari receipt `--pack`, disimpan
terpisah sebelum rehearsal): `1c3e46d78bfe37f15214d6a5910c04b739a7669c6b8ea9c0296b815c4afad920`.

## Hasil rehearsal

- `portability_pack --verify` atas bundel percobaan pertama (+ kedua
  config instans): **ok: true**, 7/7 berkas terverifikasi,
  missing/extra/corrupted kosong. Integritas bundel final diverifikasi di
  dalam rehearsal sendiri (`verify_bundle`) dan secara independen lewat
  unpack + `cmp` di bawah.
- `migration_rehearsal bundle.tar.gz src.json dst.json --manifest-sha256 <pin>`:
  **exit 0**, receipt `ace.migration-rehearsal.v1` —
  `restored_and_rechecked: 6`, `isolation_passed: true`,
  `preview_cleaned: true`, `activation_authorized: false`,
  `manifest_sha256` pada receipt **sama persis** dengan pin.
- Verifikasi independen di luar alat: `--unpack` ke direktori ketiga lalu
  `cmp` per berkas terhadap sumber repo — **6/6 IDENTIK byte-per-byte**
  (76.700 byte pulih utuh).
- Kontrol negatif: rehearsal yang sama dengan pin manifest salah
  (64 nol) → **exit 1**, "verified bundle does not match the trusted
  source manifest". Pin benar-benar mengikat.
- Sesudah bor, workspace target kosong kembali (preview dibersihkan);
  tidak ada sisa berkas bor di target.

## Pemeriksaan checklist rumah kedua (#410) — TEMUAN

`second_home.py --strict` dengan inventaris `docs/REPO_INDEX.md` versi
commit dan kebutuhan bor (3 kelompok, 7 langkah, 6 aset) melaporkan
**5 dari 6 aset HILANG_DI_INVENTARIS** (exit 1) — padahal kelima berkas itu
ada dan baru saja dipakai bor. Akar masalahnya bukan pada alat checklist:
**`docs/REPO_INDEX.md` versi commit basi berat** — tertulis 1.564 berkas
(bagian `tools` hanya 42 berkas), sedangkan pohon nyata berisi 2.110
berkas (bagian `tools` 248 berkas). Indeks itu tidak pernah diregenerasi
menyeluruh sesudah gelombang-gelombang merge besar.

Perbaikan yang dilakukan bersama laporan ini: `docs/REPO_INDEX.md`
diregenerasi deterministik dari pohon saat ini dengan
`tools/repo_index.py`. Checklist yang sama kemudian dijalankan ulang:
**matched 6/6, missing 0, all_assets_present: true, exit 0**.

## Batas bor

Bor ini membuktikan jalur pack → verify → rehearsal-restore → checklist
pada bundel dokumen/alat. Ia TIDAK membuktikan: pemindahan state engine
atau database hidup, kapasitas host target, atau aktivasi layanan —
sesuai batas yang dinyatakan `docs/research/ACE_WS7_MIGRATION_REHEARSAL.md`.
Aktivasi rumah kedua tetap keputusan operator terpisah.
