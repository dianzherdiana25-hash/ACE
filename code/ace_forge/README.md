# EVO 0052 · Bahan tempa dan provenance

Draf pembangunan dari main `42f0102`. Peta mengikuti penomoran rencana EVO 0052.

| Butir | Program | Verifier |
|---:|---|---|
| 1 | `dataset_forge.py` | Promosi dari indeks verifier terpisah, deduplikasi, isolasi partisi serta JSONL deterministik |
| 2 | `dataset_custody.py` | SHA-256 per baris dan rantai provenance, penolakan perubahan relatif terhadap anchor eksternal |
| 3 | `synthetic_data_generator.py` | Tiga keluarga tugas berseed, cek mekanis mandiri, dan laporan shortfall |
| 4 | `curriculum_distiller.py` | Distilasi urutan dari demonstrasi berkustodi, konflik, dan isolasi held-out |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_forge -t code -q
PYTHONPATH=code python3 -m ace_forge.dataset_forge candidate.json --verified-index verify.json > dataset.jsonl
PYTHONPATH=code python3 -m ace_forge.dataset_custody seal dataset.jsonl --dataset-ref fixture/dataset > manifest.json
PYTHONPATH=code python3 -m ace_forge.dataset_custody verify dataset.jsonl manifest.json --expect-head "$SHA256"
```

Bentuk input `candidate.json` dan `verify.json` ada di
`test_dataset_forge.py`. Verifier asal menerbitkan indeks yang menyatakan
status, rujukan bukti, lisensi, dan SHA-256 atas payload kanonis.
Kebijakan lisensi berasal dari masukan. Rujukan dan hash dicatat sesuai
artefak yang diberikan pemanggil. Simpan head terverifikasi di saluran
terpisah sebelum menjalankan mode verify. Data fixture menguji mekanisme
penyegelan dan penerimaan.

Pembagian train/held-out memakai hash seed + ID keluarga. Rasio masukan
adalah ambang hash dan proporsi akhir dipengaruhi jumlah contoh di tiap
keluarga. Cek duplikat menggabungkan bentuk Unicode kanonis serta spasi
yang berbeda pada prompt. Cek yang lebih luas untuk contoh nyaris duplikat
termasuk butir 12.

`synthetic_data_generator.py` mengeluarkan calon pada skema masukan
`dataset_forge`. Laporan internalnya mencatat penolakan dan shortfall.
Calon memerlukan indeks terpisah untuk promosi.

`curriculum_distiller.py` menerima dataset JSONL, metadata langkah per
contoh, `--manifest`, dan `--expect-head`. Contoh masukan ada di
`test_curriculum_distiller.py`. Pemeriksa belajar urutan hanya dari
langkah demonstrasi train yang melewati ambang dukungan. Laporan
memuat konflik urutan beserta ID pendukung. Baris held-out membawa
soal dan pointer verifier, sementara jawaban disimpan di dataset
kustodi untuk penilai. Pengaruh terhadap hasil belajar belum dinilai.
