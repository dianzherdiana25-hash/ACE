# Garis A Tranche 2 (A4) — Audit Bundel Lintas Paket & Catatan Cakupan Per Pasangan Paket

Menindaklanjuti usulan tranche 2 butir 4 pada [ACE_GARIS_A_AKUNTANSI.md](ACE_GARIS_A_AKUNTANSI.md):

1. **Audit bundel lintas paket terpin (`tools/seal_run.py`)**:
   - Menambahkan `audit_bundle_matrix(...)` (`ace.bundle-matrix-audit.v1`) dan subperintah `audit-matrix` untuk memeriksa daftar bundel `{package, bundle, manifest_sha256}` terhadap manifest terpin.
   - Fixture pada `tools/test_evo_tranche2_audit.py` mengemas tiga paket (`EVO_0004`, `EVO_0005`, `EVO_0006`) lalu menguji empat mode salinan rusak: bit-flip payload, perubahan `manifest.json` (`manifest_sha256_mismatch`), berkas tambahan tak terdaftar, berkas hilang, dan direktori bundel hilang.

2. **Catatan cakupan & pengaman satuan per pasangan paket (`tools/evo_results.py`)**:
   - `compare_metrics` kini menerima `before_unit`, `after_unit`, `before_population`, `after_population`, `comparable`, `scope_note`, dan `scope_notes` tingkat pasangan paket, lalu menyimpannya pada field `scope_notes`.
   - Jika satuan berbeda (`unit_mismatch`) atau populasi ditandai `comparable: false` (`population_or_scope_mismatch`), pengurangan gagal aman (`delta = null`).
   - Menambahkan `compare_package_matrix(...)` (`ace.evo-metric-matrix.v1`) dan subperintah `compare-matrix`.

## Cara menjalankan tes

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  tools.test_evo_experiment_support tools.test_evo_tranche2_audit tools.test_pack_evidence tools.test_evo_scaffold
```
