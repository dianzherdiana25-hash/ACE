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
| 17 | `comparison_analyst.py` | Peringkat dengan bobot tetap, unit dinormalisasi dan metrik wajib |
| 18 | `market_analyst.py` | Rekap observasi, denominator per periode dan HHI pada cakupan lengkap |
| 19 | `trend_analyst.py` | Slope Theil–Sen per hari, jendela, gap kalender dan pointer baris |
| 20 | `topic_knowledge_base.py` | Pencarian outcome atau alias dan kartu bukti per konteks |
| 21 | `actor_mapper.py` | Relasi teranotasi yang menyebut kedua aktor dan jarak pada graf berarah |
| 22 | `evidence_grader.py` | Tiers desain, risiko deklaratif, kelompok, dan konflik antar-estimasi |
| 23 | `viral_claim_watcher.py` | Pertumbuhan observasi dari slot sebanding dan status klaim diperiksa ulang |
| 24 | `number_provenance.py` | Posisi angka, konversi satuan dan sumber pengukuran yang sama konteksnya |
| 25 | `rebuttal_writer.py` | Sanggahan numerik yang tetap memuat bukti pendukung |
| 26 | `report_updater.py` | Revisi dari sumber terkini, delta status dan bukti per klaim |
| 27 | `research_qa.py` | Rubrik dan pembacaan ulang byte sumber untuk verifikasi klaim |
| 28 | `research_archiver.py` | ZIP deterministik dengan sumber, laporan, manifest dan verifier |
| 29 | `agenda_generator.py` | Kandidat agenda dari status bukti dengan prioritas dan brain-of-origin |
| 30 | `institute_bench.py` | Kasus tertutup, kunci terpisah, audit angka prosa aktual dan rubrik |
| 31 | `claim_evolution.py` | Riwayat status klaim dari laporan ber-hash dan tanggal |
| 32 | `controversy_mapper.py` | Graf konflik material dari pengukuran sebanding dan komponen terkait |
| 33 | `methodology_grader.py` | Rubrik per desain dengan kutipan aktual dan kriteria belum dinilai |
| 34 | `publication_bias_detector.py` | Sinyal asimetri skala studi dengan permutasi rank eksak |
| 35 | `meta_analyzer.py` | Efek gabungan fixed/random, Q, I², tau², serta bobot dan sumber |
| 36 | `living_glossary.py` | Definisi dengan versi dan konflik alias atau definisi terbaru |
| 37 | `field_chronology.py` | Kejadian dan presisi interval waktu dari kutipan sumber |
| 38 | `paper_conflict.py` | Selisih antar-paper dengan interval, konteks dan kemandirian |
| 39 | `replication_assessor.py` | Toleransi efek, arah dan penahanan saat temuan desain menyimpang |
| 40 | `anomaly_questioner.py` | Pertanyaan falsifiable dari pencilan dan nomor baris data |
| 41 | `replication_designer.py` | Ukuran sampel dua proporsi dan pilihan desain yang memenuhi anggaran |
| 42 | `expert_source_panel.py` | Pemilihan cakupan topik, afiliasi berbeda dan hold konflik |
| 43 | `kb_freshness.py` | Usia bukti bertambat per topik, TTL dan celah kelompok |
| 44 | `tiered_report.py` | Tiga kedalaman laporan dengan sitasi dan celah yang sama |
| 45 | `open_dataset_publisher.py` | Draf dataset lokal, hak pakai, proyeksi kolom, kelompok langka |
| 46 | `viewpoint_coverage.py` | Cakupan perspektif per konteks dan kelompok sumber, label tercatat |
| 47 | `unsourced_number_detector.py` | Posisi angka yang tak punya pointer atau pointer tak terurai |
| 48 | `journal_club.py` | Rotasi dua peran, ketersediaan, dan slot mingguan belum terisi |
| 49 | `failed_research_archive.py` | Indeks draf kegagalan bernama dengan kutipan baris dan protokol |
| 50 | `research_impact.py` | Keputusan dengan sitasi eksplisit serta observasi pre/post seunit |

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest discover -s code/ace_research_institute -t code -q
```


## Bench tertutup

Rencana dan label kasus tersimpan di `fixtures/closed_research_plan.json`
dan `fixtures/closed_research_gold.json`. Arsip pertama di
`fixtures/closed_research_evidence/` menyimpan laporan, rubric QA,
provenance angka per kasus serta manifest hash. Studi sintetis hanya
menilai perilaku terhadap dua fixture, termasuk bukti yang kurang
dan klaim yang berlawanan dengan tabel.

```sh
PYTHONPATH=code:. python3 -m ace_research_institute.institute_bench \
  code/ace_research_institute/fixtures/closed_research_plan.json \
  code/ace_research_institute/fixtures ./research-replay \
  --expect-sha256 7c0ed3901997af8b0c70ccfc4ca60e80258d93bd26f444e88eb85a61f44aaf23
```
