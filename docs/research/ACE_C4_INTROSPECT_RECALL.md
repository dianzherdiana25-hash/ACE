# C4 · CLI Recall & Introspeksi (`tools/introspect_recall.py`)

Permukaan tanya-jawab read-only di atas snapshot memori (`memory.jsonl` berantai
hash, `ace_seed_snapshot.json`) dan dokumen `handover/` + ledger repo.

## Aturan Jawaban
1. **Setiap klaim membawa pointer sumber**: `path`, `line`/`line_start..line_end` atau `record_id`, `sha256`, dan `excerpt`.
2. **Hierarki provenans**: bukti `evidence`/`operator`/dokumen handover mengalahkan rekaman `model`; bila hanya rekaman `model` yang cocok, status menjadi `GUESS_ONLY_UNVERIFIED`.
3. **Abstain jujur**: bila tidak ada bukti cocok, keluaran berstatus `NO_VERIFIED_EVIDENCE` dengan `citations: []`.

## Pengujian
```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tools.test_introspect_recall
python3 tools/verify_sources.py
```
