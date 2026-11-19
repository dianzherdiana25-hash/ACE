# Garis B2 · Analisis Kejenuhan Judge (`tools/saturation_scan.py`)

Perkakas baca-saja untuk memindai JSONL/JSON/.json.gz hasil saring atau ukur guna menemukan tanda-tanda kejenuhan kalibrasi judge:
- **Pasangan tugas jenuh**: ID tugas berulang yang `always_pass` (100% lolos) atau `always_fail` (100% gagal).
- **Pita skor yang berhenti membedakan**: pita `0-39`, `40-44`, `45-75`, atau `76-100` dengan konsentrasi signifikan namun putusan seragam (`CEILING_SATURATED`, `FLOOR_SATURATED`, `UNIFORM_ALL_PASS`, `UNIFORM_ALL_FAIL`, `ZERO_SPREAD_PILEUP`, `LOW_SEPARATION`).
- **Rekomendasi per kelompok**: `RETIRE_EASY`, `HARDEN`, `RECALIBRATE_OR_RETIRE_FAILING`, `KEEP_CALIBRATED`, atau `COLLECT_PAIRED_RUNS`.

## Verifikasi
```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tools.test_saturation_scan
python3 tools/verify_sources.py
```
