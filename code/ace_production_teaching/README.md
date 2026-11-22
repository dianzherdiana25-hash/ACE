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
| 31 | `epub_builder.py` | EPUB 3, OCF, spine, TOC, dan bab XHTML yang dapat dibaca ulang |
| 32 | `content_calendar_builder.py` | ICS lokal, interval UTC, dependensi dan fold UTF-8 |
| 33 | `invoice_builder.py` | Aritmetika faktur draf dengan neto, pajak, total dan sumber per baris |
| 34 | `contract_builder.py` | Draf bertemplat dari klausul bertambat dan cakupan topik wajib |
| 35 | `certificate_builder.py` | Bukti capaian dan izin label sebelum membuat sertifikat lokal |
| 36 | `label_builder.py` | Label per paket, konflik alamat, dan daftar barang tanpa alamat |
| 37 | `finance_report_builder.py` | Rekap tabel baca-saja dengan total, kategori, dan jendela tanggal |
| 38 | `static_dashboard.py` | Satu HTML statis dengan data ter-escape, grafik dan navigasi lokal |
| 39 | `document_proofreader.py` | Saran ejaan ID/EN, pengulangan dan spasi dengan lokasi |
| 40 | `doc_a11y_checker.py` | Heading, label tautan, alt dan header tabel native |
| 41 | `case_method_teacher.py` | Kasus berizin sesuai topik, baris skenario dan pertanyaan tanpa bocor jawaban |
| 42 | `project_teacher.py` | Prasyarat milestone proyek dan bukti struktur artefak |
| 43 | `essay_grader.py` | Kredit isi, urutan lapisan dan sitasi yang dapat diperiksa |
| 44 | `listening_trainer.py` | WAV potong terukur, opsi acak berseed dan kunci terpisah |
| 45 | `pronunciation_coach.py` | Penyelarasan grapheme ID dan tindakan latihan berdasar transkrip |
| 46 | `vocab_trainer.py` | Kosakata konteks dengan gap tunggal, distraktor serta sumber |
| 47 | `math_story_trainer.py` | Cerita aritmetika lokal dengan kuantitas, satuan dan kunci eksak |
| 48 | `code_tutor.py` | Penilaian fungsi pada interpreter AST pure berbatas langkah dan ukuran |
| 49 | `writing_coach.py` | Delta revisi dan hubungan perubahan dengan umpan balik serta syarat |
| 50 | `self_study_planner.py` | Jadwal tiga puluh hari, anggaran, review dan verifikasi prasyarat |
| 51 | `learning_style_probe.py` | Capaian berpasangan lintas format dengan kasus tidak lengkap terpisah |
| 52 | `at_risk_detector.py` | Sinyal penurunan, skor rendah atau jeda, dengan bukti minimum |
| 53 | `learner_report_card.py` | Rapor native per periode, poin bersumber dan belum diukur |
| 54 | `question_bank.py` | Kalibrasi butir dari percobaan unik terikat hash soal |
| 55 | `explained_key.py` | Perhitungan ulang dan langkah periksa kunci aritmetika |
| 56 | `reteach_engine.py` | Materi ulang dengan metode lain, verifikasi dan anggaran eksplisit |
| 57 | `bridge_lesson.py` | Target majemuk, prasyarat bersama dan latihan gabungan |
| 58 | `material_qa.py` | Sumber, tujuan, struktur a11y dan jawaban tertahan |
| 59 | `learning_journey.py` | Arsip perjalanan pseudonim berisi receipt sesi tertutup berantai |
| 60 | `cohort_report.py` | Rekap skor berpasangan dengan penyembunyian kelompok kecil |

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


## Gerbang integrasi

`step_dashboard_v3` dapat menyertakan ringkasan fixture saat
`ACE_EVO0058_TEACHING=1` dan `ACE_EVO0058_REPORT_SHA256` cocok dengan
`evo0058_teaching/run.json` di workspace. Seluruh byte pada manifest
diperiksa ulang. Gerbang mati secara bawaan dan hook tambahan
hanya membaca. Ringkasan keuangan, faktur, kontrak, dan label
dihasilkan secara lokal dari masukan yang diberikan.
