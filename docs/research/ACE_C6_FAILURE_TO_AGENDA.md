# C6 · Permukaan Agenda dari Kegagalan (`tools/failure_to_agenda.py`)

Memindai dokumen vonis/ledger (`handover/*VERDICT*.md`, `RESEARCH_LEDGER.md`, Addendum)
serta keluaran konsolidasi C3 (`ace.metacog-consolidation.v1`) dan snapshot `memory.jsonl`
secara read-only untuk menerbitkan kandidat agenda berformat register.

## Aturan Atribusi & Keputusan
- `brain_of_origin`: `"gravity-proposal"`
- `decision_owner`: `"Ian"`
- `decision_status`: `"PROPOSED_AWAITING_IAN"` (`claim_made=False`)
- Draf register (`register_entry_draft`) bersifat usulan belaka dan tidak menyentuh `OpportunityRegister` di disk.

## Pengujian
```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v tools.test_failure_to_agenda
python3 tools/verify_sources.py
```
