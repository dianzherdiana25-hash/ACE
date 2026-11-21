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
