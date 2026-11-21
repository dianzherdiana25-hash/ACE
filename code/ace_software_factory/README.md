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
