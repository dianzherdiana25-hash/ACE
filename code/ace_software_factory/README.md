# EVO 0054 · Pabrik software lokal

Basis `main` `b7dbafb`. Paket ini menerima kontrak deklaratif dan
menghasilkan artefak lokal baru. Fixture tidak memakai layanan.

| Butir | Program | Verifier |
|---:|---|---|
| 1 | `spec_writer.py` | Ujaran deklaratif, acceptance tertambat, dan klarifikasi eksplisit |
| 2 | `architecture_designer.py` | Graf boundary dan repositori, retensi, serta jejak tiap kebutuhan |
| 3 | `repo_scaffolder.py` | Repository Python yang dapat dijalankan, manifest, dan smoke test |
| 4 | `schema_designer.py` | DDL SQLite STRICT, tipe, kunci rujukan dan literal tersaring |
| 5 | `api_builder.py` | Backend SQLite JSON CRUD, batas kolom dan metode, serta HTTP loopback |
| 6 | `ui_builder.py` | HTML semantik, tabel, navigasi dan form JSON dengan endpoint relatif |
| 7 | `test_factory.py` | Verifier acceptance yang menjalankan CLI sesuai contoh bersumber |
| 8 | `build_loop.py` | Uji dan patch terdaftar pada salinan terisolasi bubblewrap, dengan receipt per ronde |
| 9 | `self_reviewer.py` | Temuan AST dengan posisi dan SHA-256 sumber |
| 10 | `debt_detector.py` | Kompleksitas fungsi dan siklus graf impor internal |
| 11 | `ci_builder.py` | Workflow PR dengan checkout terikat commit dan smoke lokal |
| 12 | `release_packager.py` | ZIP byte-identik dan verifier tiap anggota |
| 13 | `docs_writer.py` | Panduan per antarmuka dengan rujukan spesifikasi dan receipt |
| 14 | `deploy_guide_writer.py` | Topologi deploy, pemeriksaan tahap, dan urutan rollback yang bersumber |
| 15 | `cli_builder.py` | CLI produk mandiri dengan proyeksi, agregasi dan validasi JSON |
| 16 | `service_builder.py` | Worker background SQLite, FIFO, idempotensi, dan penghentian terbatas |
| 17 | `etl_builder.py` | Konversi CSV ke JSONL dari pemetaan, dengan reject per record |
| 18 | `security_scanner.py` | Temuan AST berbasis koordinat dengan nilai kandidat rahasia disembunyikan |
| 19 | `perf_profiler.py` | Wall-time pengujian beban sandbox dengan warm-up dan p95 |
| 20 | `bug_fixer.py` | Koreksi satu literal yang sudah disetujui dengan verifikasi red–green |
| 21 | `safe_refactorer.py` | Rename helper privat terikat AST dengan dua suite sandbox |
| 22 | `dependency_manager.py` | Perbandingan pin dan usulan versi memakai katalog serta advisori offline |
| 23 | `landing_builder.py` | HTML statis responsif dengan CTA terdaftar dan bukti per klaim |
| 24 | `auth_builder.py` | Login lokal ber-role, verifikasi password, dan expiry serta revokasi sesi |
| 25 | `payment_sandbox_builder.py` | Simulasi hold, capture, void dan refund memakai unit fixture |
| 26 | `notifier_builder.py` | Draf notifikasi lokal ber-template, batas field dan idempotency |
| 27 | `admin_builder.py` | Panel tabel dan dispatch yang memeriksa izin serta CSRF |
| 28 | `seed_builder.py` | Snapshot SQLite baru dari data seed dengan verifikasi FK dalam transaksi |
| 29 | `acceptance_judge.py` | Aturan acceptance bertaut spesifikasi, artefak dan observasi |
| 30 | `factory_bench.py` | Tiga produk fixture dari brief sampai acceptance, termasuk UI dan API di loopback |
| 31 | `mobile_builder.py` | Aplikasi web mobile dengan penyimpanan terpisah per tab dan batas lokal |
| 32 | `extension_builder.py` | Manifest V3 dengan izin storage dan pembaruan checklist terserialisasi |
| 33 | `game_builder.py` | Puzzle grid yang dapat dimainkan dan verifier replay saksi BFS |
| 34 | `dashboard_builder.py` | Agregasi periode, skala bersama, dan provenance bagi data dasbor |
| 35 | `worker_builder.py` | Antrean SQLite dengan lease, retry berbatas, dan dead-letter |
| 36 | `api_gateway_builder.py` | Gateway JSON loopback dengan remap rute, batas respons, dan tanpa penerusan header |
| 37 | `migration_builder.py` | Migrasi SQLite aditif pada salinan dengan checksum per tabel |
| 38 | `search_builder.py` | Indeks Unicode FTS5 dengan BM25, filter kelompok, dan anchor byte |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_software_factory -t code -q
```

`spec_writer.py` menerima ujaran berpenanda `perlu`, `uji`,
`batas`, dan `luar` disusul ID serta isi klausa. Contoh lengkap
ada pada `test_spec_writer.py`. Ujaran yang belum dipahami
muncul sebagai item klarifikasi, dengan sumber yang sama.

`architecture_designer.py` membutuhkan keputusan retensi dan
deskripsi interaksi per kebutuhan. `repo_scaffolder.py` mengikat
bentuk arsitektur serta hash spesifikasi pada artefak akhir.
`schema_designer.py` mengeluarkan DDL yang diverifikasi di SQLite
in-memory dari fixture dua tabel.

`api_builder.py` menggunakan model SQLite dan kontrak resource. Runtime
yang dihasilkan membuka loopback dan memakai SQL terparameterisasi.
`ui_builder.py` menghasilkan HTML mandiri, dengan aksi POST JSON bila
halaman disajikan bersama endpoint terkait.

`test_factory.py` mengikat vektor acceptance ke rujukan spesifikasi
dan menghasilkan tes CLI. `build_loop.py` menjalankan tes di namespace
bubblewrap tanpa jaringan dan dengan source read-only. Perbaikan hanya
diterapkan pada salinan ketika head dan checksum byte lama cocok.

## Bench produk

`fixtures/factory_product_bench.json` menetapkan tiga spesifikasi,
input probe, dan nilai harapan per kriteria. Jalankan bench di mode
offline dan beri direktori keluaran baru untuk menyimpan ringkasan,
observasi dan verdict bertaut SHA-256 setiap produk.

```sh
PYTHONPATH=code:. python3 -m ace_software_factory.factory_bench \
  code/ace_software_factory/fixtures/factory_product_bench.json \
  --expect-sha256 fbdb9ea98fbd12d2d38ba03fb66056e8b50d9f42c9bed7a9769077f2bbcc9dea --output DESTINASI_BARU
```

Hash rencana merujuk JSON UTF-8 kanonis dengan kunci diurutkan,
separator tanpa spasi dan karakter non-ASCII dipertahankan. Verifier
browser opsional memerlukan Chromium, Node dan Playwright yang sudah
tersedia lokal. Ia mengisi form produk, menerima respons simpan, dan
membaca data yang baru disimpan dari API loopback.

## Gerbang penerimaan

`step_software_factory` memakai jalur biasa saat flag mati. Bila
`ACE_EVO0054_FACTORY=1`, `ACE_EVO0054_ACCEPTANCE_SHA256` mengikat byte
`evo0054_factory/acceptance.json` pada workspace. Bundle harus memuat
`spec`, `contract`, `observations`, `artifact_sha256`, dan schema
`ace.factory-acceptance-bundle.v1`. Jalur ini hanya mengevaluasi
receipt dan mengembalikan laporan.
