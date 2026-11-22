# EVO 0057 · Institut riset lokal

Basis main `51521d5`. Input penelitian berasal dari berkas lokal
yang ditunjuk pemanggil. Hasil perhitungan menyertakan nomor baris
atau rujukan sumber serta hash. Format tabel hasil di
`test_paper_reader.py` menjelaskan subset Markdown yang didukung.

| Butir | Program | Verifier |
|---:|---|---|
| 1 | `research_planner.py` | Metode bertipe, falsifier, urutan prasyarat, dan anggaran |
| 2 | `source_collector.py` | Relevansi dari baris aktual, umur, custody hash, dan grup independen |
| 3 | `paper_reader.py` | Tabel hasil teranotasi, konversi satuan, interval dan baris yang ditahan |
| 4 | `literature_reviewer.py` | Median per grup serta konflik/ketiadaan bukti yang dibedakan |
| 5 | `claim_checker.py` | Pemeriksaan klaim angka dengan populasi, konteks, sampel, dan sumber |
| 6 | `data_analyst.py` | Profil CSV bertipe, persentil, missingness dan denominator korelasi |
| 7 | `dataset_cleaner.py` | Normalisasi, dedup stabil dan karantina dengan peta baris |
| 8 | `pattern_finder.py` | Pencilan MAD dan tren kontinu, termasuk MAD nol dan waktu ganda |
| 9 | `model_builder.py` | Regresi eksak multi-fitur, split baris eksplisit dan baseline holdout |
| 10 | `hypothesis_tester.py` | Ekor Fisher dan sign-flip eksak dengan deklarasi asumsi |
| 11 | `experiment_designer.py` | Alokasi terblokir dan deterministik, kontrol serta hold bila sampel kurang |
| 12 | `survey_designer.py` | Konstruk, skala, reverse-score, persetujuan dan cabang survei |
| 13 | `survey_analyzer.py` | Codebook jawaban terbuka, konflik, consent dan penekanan kategori langka |
| 14 | `interview_kit.py` | Panduan bercabang, batas waktu terburuk dan jejak simulasi |
| 15 | `deep_report_writer.py` | Laporan numerik terverifikasi dan bibliografi baris, gap yang disebut |
| 16 | `executive_summarizer.py` | Pemilihan temuan berbukti dengan rekonsiliasi sitasi dan keterbatasan |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_research_institute -t code -q
```
