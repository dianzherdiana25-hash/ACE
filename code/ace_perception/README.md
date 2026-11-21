# EVO 0053 · Persepsi lokal

Draf dari `main` pada `42f0102`. Bentuk font dan raster fixture ada di `test_ocr_engine.py`.

| Butir | Program | Verifier |
|---:|---|---|
| 1 | `ocr_engine.py` | OCR geometri dua jalur dengan boks sumber, ambiguitas, dan pembatas decoder PGM |
| 2 | `document_extractor.py` | Klaim teks, jumlah, desimal eksak, dan tanggal dengan zona sumber serta ketidakpastian |
| 3 | `screen_understanding.py` | Geometri frame, induk, label interior, dan boks glyph dalam koordinat layar |
| 4 | `diagram_reader.py` | Grafik batang bertanda, kalibrasi rasional, dan bukti per kategori |
| 5 | `audio_pipeline.py` | Segmen PCM dan pertautan token bertimestamp dari receipt yang terikat ke sumber |
| 6 | `speaker_diarization.py` | Klaster anonim berbasis spektrum dengan abstain dan boks waktu |
| 7 | `perceptual_memory.py` | Indeks persepsi tertambat, recall lintas modalitas, serta konflik satu lokasi |
| 8 | `confidence_calibrator.py` | Kalibrasi per pita dan modalitas dengan ECE/Brier pada keluarga held-out |

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

`screen_understanding.py` membaca frame sumbu sejajar dari raster.
Teks OCR pada interior membuat wilayah menjadi kandidat kontrol.
Jenis tindakan masih perlu sumber lain. Frame dengan anak memperoleh
hubungan induk dari boks terkecil yang mencakupnya.

`diagram_reader.py` memakai daerah plot tanpa sumbu, pita kategori,
dan dua tanda skala yang dirujuk. Satu batang perlu bertemu baseline
nol. Komponen ganda, melewati nol, lepas dari baseline, atau di luar
kalibrasi tetap terbuka. Nilai hasil disimpan sebagai pecahan eksak.

`audio_pipeline.py` membaca WAV PCM 8/16 bit. Roster segmen berasal
dari energi per jendela, durasi minimum, dan batas jeda. Receipt yang
sudah direkam harus menunjuk hash WAV dan roster. Kata membawa
interval sampel dan mikrodetik. Dekode bahasa berada di pihak
pencatat receipt.

`speaker_diarization.py` memakai tiga jendela spektral per segmen
bila panjangnya memungkinkan. Label anonim berlaku dalam satu WAV.
Bagian tanpa energi yang cocok, jarak meyakinkan, atau slot klaster
tetap terbuka. Verifier memakai nada buatan. Kinerja pada rapat
dan tumpang tindih pembicara belum diukur.

`perceptual_memory.py` menyegel indeks JSON mandiri. Pencarian
memerlukan head eksternal dan menampilkan rujukan receipt serta
boks/waktu. Beberapa kutipan berbeda pada wilayah media yang sama
dilaporkan sebagai konflik. Indeks terpisah dari store runtime.

`confidence_calibrator.py` memisahkan train dan held-out berdasarkan
keluarga. Frekuensi posterior per pita memakai prior eksplisit dan
minimum dukungan. Brier dan ECE memakai kasus yang sama pada kedua
lengan dengan confidence dikalibrasi masuk ulang ke pita metrik.
