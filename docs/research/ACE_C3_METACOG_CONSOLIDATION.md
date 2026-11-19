# C3 · Konsolidasi Memori Metakognitif (`tools/metacog_memory_consolidate.py`)

Perkakas baca-saja untuk menggabungkan rekaman snapshot memori (`memory.jsonl` berantai hash),
log episode/audit JSONL, dan checkpoint `metacognitive_memory.json` menjadi ringkasan
metakognitif deterministik.

## Keluaran Utama
- **Kluster kegagalan & keberhasilan** (`failure_clusters`, `success_clusters`), termasuk tanda `recurring` untuk pola yang muncul `>= min_cluster_size`.
- **Statistik kalibrasi** (`mean_predicted_prob`, `mean_abs_calibration_error`, `overconfident_failures`) bila episode membawa probabilitas prediksi.
- **Peringatan negative transfer** untuk prosedur yang lolos pada satu konteks namun gagal atau `fail > success` pada konteks lain.
- **Temuan HIGH terbuka & hutang record `superseded`**.
- **Nol tulisan ke store**: aman dijalankan pada direktori store berizin `0555`/`0444`.

## Pengujian
```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tools.test_metacog_memory_consolidate
python3 tools/verify_sources.py
```
