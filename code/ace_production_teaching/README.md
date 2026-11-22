# EVO 0058 · Produksi dokumen dan pengajaran

Basis main `51521d5`. Rencana dan artefak baru hanya memakai masukan
lokal ber-anchor. Backend slide `python-pptx` bersifat lokal.
Verifier `python-docx`, `pypdf`, `openpyxl`, dan `python-pptx`
membaca kembali artefak yang ditulis pada fixture.

| Butir | Program | Verifier |
|---:|---|---|
| 1 | `tabular_engine.py` | Join many-to-one, pivot, agregasi, sel kosong dan lineage CSV |
| 2 | `document_builder.py` | Templat berisi binding bersumber ke DOCX dan PDF asli |
| 3 | `sheet_builder.py` | XLSX dengan formula hidup, cache nilai, dan deteksi siklus |
| 4 | `slide_builder.py` | PPTX tiga tata letak, teks, tabel editable dan sumber per slide |
| 5 | `chart_builder.py` | Grafik bar dengan baseline nol, grafik garis, skala dan sitasi per titik |
| 6 | `report_composer.py` | Metrik dari observasi bersumber, rekonsiliasi satuan dan binding yang sama di seluruh laporan |
| 7 | `artifact_qa.py` | Gate hash, struktur native, syarat minimum dan fitur aktif yang ditahan |
| 8 | `data_anonymizer.py` | Kebijakan drop/mask/keep/pseudonim per kolom, HMAC lingkup lokal dan audit tanpa nilai |
| 9 | `schema_validator.py` | Validasi data bertingkat dengan JSON Pointer dan kaidah nilai berhingga |
| 10 | `document_merger.py` | Transfer paragraf, tabel dan daftar isi DOCX dengan bookmark yang dapat diklik |
| 11 | `citation_manager.py` | Nomor sitasi lintas dokumen, alias bukti dan referensi yang belum terurai |
| 12 | `artifact_versioning.py` | Versi bertambat parent dengan daftar tambahan, selisih, dan penghapusan |
| 13 | `learner_model.py` | Kredit parsial tepat, prior Beta dan jumlah bukti per topik |
| 14 | `topic_map.py` | Prasyarat graf, rute kritis dan penolakan siklus |
| 15 | `lesson_planner.py` | Rekomendasi adaptif yang memisahkan gap ukur dan prasyarat belum lulus |
| 16 | `exercise_generator.py` | Latihan bertingkat, kombinasi unik dan kunci held-out terpisah |
| 17 | `grader.py` | Nilai jawaban terbuka dari rubrik frasa, kredit parsial dan kontradiksi |
| 18 | `misconception_tracker.py` | Temuan berulang antartugas dalam jendela bukti |
| 19 | `spaced_repetition.py` | Interval pengulangan, ease, jatuh ulang, dan tanggal jatuh tempo |
| 20 | `explanation_adapter.py` | Varian tingkat penjelasan dengan binding fakta dan sumber yang sama |
| 21 | `session_manager.py` | Sesi stdio, evaluasi terbuka dan transisi receipt berantai hash |
| 22 | `hint_engine.py` | Rantai petunjuk dan hold ketika mengulang bentuk jawaban terlindungi |
| 23 | `socratic_questioner.py` | Pertanyaan lanjutan berdasar bukti rubrik dan fokus kontradiksi |
| 24 | `mastery_predictor.py` | Prognosis dengan half-life deklaratif dan batas bukti prasyarat |
| 25 | `feedback_writer.py` | Umpan balik, alasan kredit dan tindakan ulang terarah |
| 26 | `exam_builder.py` | Ujian native dari kisi held-out dengan kunci terpisah |
| 27 | `notes_generator.py` | Catatan dan gap dari rantai receipt yang diverifikasi ulang |
| 28 | `flashcard_engine.py` | Kartu dari kelemahan teramati, pointer baris sumber jawaban |
| 29 | `progress_visualizer.py` | Grafik checkpoint per topik dengan gap eksplisit |
| 30 | `teaching_bench.py` | Artefak native dan hasil learner simulasi tertutup dengan kunci terpisah |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_production_teaching -t code -q
```


## Bench tertutup

`fixtures/teaching_plan.json` memuat rencana fixture dan anchor atas
`fixtures/teaching_gold.json`. Artefak serta receipt perhitungan berada
di `fixtures/teaching_bench_evidence/`. Ukuran pengajaran memakai
learner deterministik dengan perubahan level yang disebut di rencana.
Angka itu berlaku pada simulator tersebut.

```sh
PYTHONPATH=code:. python3 -m ace_production_teaching.teaching_bench \
  code/ace_production_teaching/fixtures/teaching_plan.json ./teaching-replay \
  --root code/ace_production_teaching/fixtures \
  --expect-sha256 34ba6d3b3ce6a76df7ab05db673bc1d50081d8475b90f2e3ac0750b81c4d15d0
```
