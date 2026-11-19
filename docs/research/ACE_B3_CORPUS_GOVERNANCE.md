# Garis B3 · Tata Kelola Korpus (Perkakas Baru)

Tiga perkakas baru untuk siklus pembekuan dan pemeriksaan korpus tanpa mengubah `handover/` maupun perkakas lama:
1. `tools/frozen_corpus_registry.py`: memindai direktori korpus (`name`, `line_count`, `bytes`, `sha256`, `task_kind_distribution`) dan menyediakan mode `--check` untuk mendeteksi drift (`ADDED`, `REMOVED`, `MODIFIED`).
2. `tools/corpus_freeze_packer.py`: memvalidasi ID kandidat terpilih via linter v2 secara fail-closed, lalu menulis berkas korpus beku ke direktori target, memutakhirkan entri registry JSON secara atomik, dan menerbitkan catatan pembekuan Markdown.
3. `tools/corpus_lint_v2.py`: linter generasi berikut lintas berkas mencakup tiga lapis — skema JSONL `{id, kind, task_kind, instruction}`, pemeriksaan kendala mekanis (`--lang-specs`, `--lang-samples-dir`, `--code-specs`, termasuk deteksi kontradiksi frasa/larangan & urutan), dan deteksi duplikat/near-duplicate Jaccard lintas berkas maupun terhadap `--frozen`.

## Verifikasi
```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tools.test_corpus_governance
python3 tools/verify_sources.py
```
