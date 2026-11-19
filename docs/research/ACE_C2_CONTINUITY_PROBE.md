# C2 · Probe Kontinuitas Model-Diri (`tools/self_model_continuity_probe.py`)

Harness untuk menguji apakah narasi model-diri ACE (`tools/narrative_self_model.py`)
mempertahankan fakta terekstrak yang identik ketika label organ aktif diganti-ganti
atau gaya kalimat narasinya berubah di atas berkas sumber yang sama persis.

## Apa yang Diperiksa
1. **Kesamaan fakta terekstrak (`missing_facts`, `added_facts`, `value_mismatches`)**:
   membandingkan `(section, fact_key, fact_value)` — bukan kesamaan redaksi kalimat.
2. **Integritas sumber (`source_mismatches`, `sourceless_errors`)**:
   menjalankan `assert_no_sourceless_claims` pada setiap keluaran varian.
3. **Anti-kontaminasi label organ (`organ_contamination`)**:
   mendeteksi bila token label organ dari `organ_context` menyusup ke klaim fakta
   identitas/terbukti varian sementara tidak ada pada baseline bersumber.

## Pengujian
```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tools.test_self_model_continuity_probe tools.test_narrative_self_model
python3 tools/verify_sources.py
```
