# C1 · Model-Diri Naratif (`tools/narrative_self_model.py`)

Dokumen desain dan verifikasi untuk modul Lapis 3 read-only model-diri naratif ACE.

## Tujuan
Menyediakan model-diri naratif deterministik dan jujur atas:
1. `identity` — identitas konstitusional (`Multi-brain sovereignty`, `birth_certificate_rule`, gerbang rilis `BLOCK_RELEASE`, ringkasan status rantai memori);
2. `proven` — fakta gerbang/kemampuan/memori terverifikasi (`G3`, `G4`, `round2-gate-01`, rekaman `evidence`/`operator` dari `memory.jsonl`);
3. `unproven` — gerbang hasil nol/belum dinilai (`G2`, `G5`), `oaie_established=False`, `PHENOMENAL_CONSCIOUSNESS_UNKNOWN`, serta rekaman bersumber `model` (*guess*).

## Pagar Integritas & Read-Only
- **Nol jalur tulis**: `read_memory_snapshot_readonly()` mem-parse `memory.jsonl` berantai hash maupun snapshot JSON secara baca-saja langsung dari disk (tidak memanggil `CognitiveMemory()` agar tidak menciptakan berkas/direktori pada path kosong).
- **Wajib pointer sumber**: `verify_claim_sources()` + `assert_no_sourceless_claims()` menjamin setiap klaim memiliki berkas sumber valid dan SHA-256 cocok; klaim tanpa sumber disaring keluar ke `rejected_sourceless_claims`.
- **Kedaulatan multi-otak**: label organ hanya berada di metadata `organ_context` terpisah.

## Pengujian
```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tools.test_narrative_self_model
python3 tools/verify_sources.py
```
