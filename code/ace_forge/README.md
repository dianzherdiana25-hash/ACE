# EVO 0052 · Bahan tempa dan provenance

Draf pembangunan dari main `42f0102`. Peta mengikuti penomoran rencana EVO 0052.

| Butir | Program | Verifier |
|---:|---|---|
| 1 | `dataset_forge.py` | Promosi dari indeks verifier terpisah, deduplikasi, isolasi partisi serta JSONL deterministik |
| 2 | `dataset_custody.py` | SHA-256 per baris dan rantai provenance, penolakan perubahan relatif terhadap anchor eksternal |
| 3 | `synthetic_data_generator.py` | Tiga keluarga tugas berseed, cek mekanis mandiri, dan laporan shortfall |
| 4 | `curriculum_distiller.py` | Distilasi urutan dari demonstrasi berkustodi, konflik, dan isolasi held-out |
| 5 | `lora_trainer.py` | Optimasi dua faktor pada aktivasi dense beku, gradien numerik, dan loss train |
| 6 | `preference_trainer.py` | DPO readout fitur tetap, log-ratio relatif referensi, dan gradien |
| 7 | `forgetting_guard.py` | Akurasi berpasangan per domain, penurunan kritis, dan bukti yang kurang |
| 10 | `brain_bench.py` | Perbandingan kualitas dan sumber daya, hash artefak, dan diagnosis per kasus |

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

`forgetting_guard.py` menerima protokol dan hasil boolean berpasangan,
dengan komitmen protokol yang diteruskan lewat
`--expect-protocol-sha256`. `brain_bench.py` mengunci roster kasus,
rubrik, identitas artefak, dan ambang sampel lewat `--expect-bench-sha256`.
Bench menerima skor 0–10.000 serta waktu dalam mikrodetik dan peak dalam
byte, lalu menghitung dua lengan dari observasi yang sama-sama tersedia.
Untuk persetujuan tempa, jalankan pemeriksa regresi terpisah pada domain
umum. Kedua program menerima pengukuran yang sudah direkam. Butir 7
dan 10 dikerjakan sebelum pelatihan agar penerimaan hasil dapat diuji
tanpa mengaktifkan organ.

`lora_trainer.py` menerima resep dan snapshot aktivasi dense dari
artefak asal, beserta anchor `--expect-dataset-sha256`. Keluaran berisi
matriks A/B dan jejak MSE train. `preference_trainer.py` menerima pasangan
pilihan dengan fitur tetap dan log-probabilitas baseline serta referensi.
Anchor dimasukkan lewat `--expect-pairs-sha256`. Hasilnya adalah delta
linear pada fitur tersebut dan trace loss DPO. Keduanya menguji optimizer
dengan fixture numerik. Ekstraksi aktivasi, fitting model penuh, integrasi
runtime, dan gain held-out memerlukan proses atau bukti terpisah.
