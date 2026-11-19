# Garis A Tranche 2 (A1) — Kompatibilitas Lintas Versi & Penelusuran Konflik Katalog

Menindaklanjuti usulan tranche 2 butir 1 pada [ACE_GARIS_A_AKUNTANSI.md](ACE_GARIS_A_AKUNTANSI.md), `tools/pattern_catalog.py` kini mendukung evolusi format katalog lintas versi sekaligus menjamin:

1. **Ekspor mundur-kompatibel untuk pengusul (`curriculum_propose.py`)**:
   - Baik snapshot `ace.pattern-catalog.v1` maupun `ace.pattern-catalog.v2` (termasuk rekaman masukan `ace.pattern-distilled.v2` dengan metadata tambahan seperti `format_version`, `catalog_tags`, `provenance.migrated_from`) diekspor melalui `export` (`export_snapshot_jsonl`) menjadi JSONL `ace.pattern-distilled.v1` kanonik lewat `normalize_pattern_for_proposer(...)`.
   - Urutan rantai versi `--previous v1.json --format v2` menjaga `version = v1.version + 1` dan `parent_sha256` persis ke hash kanonik snapshot sebelumnya.

2. **Penelusuran konflik ke input mentah (`trace_conflict_changes` / `trace-conflicts`)**:
   - Setiap penambahan konflik (`added_new`), pola bersih yang berubah menjadi konflik (`added_from_pattern`), konflik yang terselesaikan (`removed_resolved_to_pattern`), konflik yang dibuang (`removed_dropped`), maupun perubahan varian konflik (`variants_changed`) dipetakan kembali ke `variants_added`, `variants_removed`, `variants_unchanged`, dan `input_pointers` berisi `(role, content_sha256, catalog, line)`.
   - `diff_catalogs(old, new)` tetap mempertahankan kunci lama `patterns` dan `conflicts`, sambil menyematkan `conflict_traces` dan `schema`/`version` asal-tujuan.

## Cara menjalankan tes

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=code:. python3 -m unittest -v \
  tools.test_pattern_catalog tools.test_pattern_catalog_compat tools.test_pattern_distill
```
