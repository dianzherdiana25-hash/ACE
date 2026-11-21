# EVO 0053 · Persepsi lokal

Draf dari `main` pada `42f0102`. Bentuk font dan raster fixture ada di `test_ocr_engine.py`.

| Butir | Program | Verifier |
|---:|---|---|
| 1 | `ocr_engine.py` | OCR geometri dua jalur dengan boks sumber, ambiguitas, dan pembatas decoder PGM |
| 2 | `document_extractor.py` | Klaim teks, jumlah, desimal eksak, dan tanggal dengan zona sumber serta ketidakpastian |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_perception -t code -q
PYTHONPATH=code python3 -m ace_perception.ocr_engine fixture.pgm font.json
```

OCR menerima PGM P2/P5 hingga 8 bit dan template satu font dengan
grid biner berukuran sama. Input ideal berisi baris horizontal
dan glyph yang dipisah kolom kosong. Angka `word_gap` diukur dalam
piksel. Dua penilai wajib sepakat di bawah batas jarak. Karakter
`�` berarti bukti belum cukup untuk mengenali bentuk. Boks menyimpan
koordinat asli dengan tepi kanan dan bawah eksklusif.

Verifier menggunakan font sintetis yang tidak menyerupai data pemilik.
Batas pengenalan ditunjukkan lewat bentuk asing, nilai ambang, skala,
kontras, dan input rusak.

`document_extractor.py` menerima gambar, font, dan layout JSON dari
pemanggil. Setiap aturan mencari satu baris dalam zona yang ditetapkan
dengan prefiks literal. Zona kosong berarti seluruh gambar. Angka
desimal ditulis sebagai integer dan jumlah digit desimal. Baris yang
bersaing atau belum terbaca sepenuhnya menahan klaim. Fixture memakai
pemisah kata empat piksel dan batas jarak nol.
