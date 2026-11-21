# EVO 0054 · Pabrik software lokal

Basis `main` `b7dbafb`. Paket ini menerima kontrak deklaratif dan
menghasilkan artefak lokal baru. Fixture tidak memakai layanan.

| Butir | Program | Verifier |
|---:|---|---|
| 1 | `spec_writer.py` | Ujaran deklaratif, acceptance tertambat, dan klarifikasi eksplisit |
| 2 | `architecture_designer.py` | Graf boundary dan repositori, retensi, serta jejak tiap kebutuhan |
| 3 | `repo_scaffolder.py` | Repository Python yang dapat dijalankan, manifest, dan smoke test |
| 4 | `schema_designer.py` | DDL SQLite STRICT, tipe, kunci rujukan dan literal tersaring |

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
