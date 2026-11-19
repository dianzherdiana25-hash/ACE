# Garis B4 · Bench Evaluasi Berdiri (`tools/eval_bench.py`)

Harness offline baca-saja berisi tiga sub-bench evaluasi berdiri:
1. **Bench tanya-jawab introspektif atas `handover/`**: solver ekstraktif + penilai ketat yang mewajibkan setiap jawaban memuat pointer berkas sumber yang sah (`MISSING_SOURCE_POINTER` / `BROKEN_SOURCE_POINTER` / `WRONG_SOURCE_POINTER` menolak jawaban tak bertautan).
2. **Bench konsistensi lintas organ**: membandingkan hasil offline antar-organ (`organ`, `pair`, `arm`, `model`), mengeluarkan laporan ketidaksepakatan putusan, selisih skor melebihi ambang, dan matriks kesepakatan berpasangan.
3. **Bench regresi format**: menjalankan probe terpin atas perkakas program repo (`corpus_lint`, `corpus_registry`, `screen_census`, `bench_table`, `ruleset_readiness`, `opportunity_register`) dan mendeteksi perubahan kunci/tipe/skema/jangkar Markdown.

## Verifikasi
```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tools.test_eval_bench
python3 tools/verify_sources.py
```
