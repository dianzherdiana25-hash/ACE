# Garis A Tranche 2 (A2) — Laporan Penutupan Kandidat Agenda

Menindaklanjuti usulan tranche 2 butir 2 pada [ACE_GARIS_A_AKUNTANSI.md](ACE_GARIS_A_AKUNTANSI.md), `tools/agenda_candidates.py` kini menyediakan `build_closure_report(...)` dan subperintah CLI `closure`.

```sh
python3 tools/agenda_candidates.py --repo . closure \
  --proposals handover/proposals.jsonl \
  --decisions handover/approved_decisions.json
```

## Pembuktian status per item

Setiap kandidat dicocokkan menggunakan `proposal_id` / `candidate_id` dan `decision_pointer` terverifikasi (`path` relatif repo POSIX, batas baris, `sha256`, `commit`, `excerpt` opsional):
- `CLOSED_APPROVED`, `CLOSED_COMPLETED`, `CLOSED_REJECTED`: tertutup resmi beserta `verified_pointers` (`observed_sha256`) dan `proof_sha256`.
- `OPEN_DEFERRED`: ditunda dengan pointer sah.
- `OPEN_PENDING_DECISION`: belum ada keputusan.
- `CONFLICTING_DECISION`: lebih dari satu keputusan berbeda untuk ID yang sama.
- `INVALID_DECISION_POINTER`: **fail-closed** apabila pointer kosong, file tidak ada/keluar repo, nomor baris melampaui file, SHA-256 tidak cocok, atau kutipan tidak ditemukan.
- Keputusan tanpa kandidat di antrean dicatat terpisah pada `orphan_decisions`.

## Cara menjalankan tes

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  tools.test_agenda_candidates tools.test_agenda_closure tools.test_opportunity_register
```
