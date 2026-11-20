"""Tes regresi fixture-only untuk tools.memory_hygiene_audit (AG42)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools import memory_hygiene_audit


def _build_entry(seq: int, prev: str, event: dict, *, tamper_hash: str | None = None) -> dict:
    digest = tamper_hash or memory_hygiene_audit.compute_entry_hash(prev, event)
    return {"seq": seq, "prev": prev, "event": event, "hash": digest}


class MemoryHygieneAuditTest(unittest.TestCase):
    def test_clean_segment_plus_one_example_of_each_defect(self) -> None:
        valid_ev = "ev-verified-001"
        missing_ev = "ev-orphan-999"

        # Segmen bersih di awal (seq 1..2): unik, evidence ada, rantai valid, provenance lengkap.
        e1 = _build_entry(
            1,
            memory_hygiene_audit.GENESIS_PREV,
            {
                "type": "record",
                "record": {
                    "id": "rec-clean-1",
                    "kind": "fact",
                    "content": "fakta bersih pertama tentang bridge",
                    "source": {"kind": "verify", "ref": valid_ev},
                    "evidence_refs": [valid_ev],
                    "confidence": 0.95,
                },
            },
        )
        e2 = _build_entry(
            2,
            e1["hash"],
            {
                "type": "record",
                "record": {
                    "id": "rec-clean-2",
                    "kind": "procedure",
                    "content": "prosedur cek rumah tanpa side effect",
                    "source": {"kind": "verify", "ref": valid_ev},
                    "evidence_refs": [valid_ev],
                    "confidence": 0.9,
                },
            },
        )
        # Cacat 1: duplikat konten persis terhadap rec-clean-1.
        e3 = _build_entry(
            3,
            e2["hash"],
            {
                "type": "record",
                "record": {
                    "id": "rec-dup-3",
                    "kind": "fact",
                    "content": "fakta bersih pertama tentang bridge",
                    "source": {"kind": "verify", "ref": valid_ev},
                    "evidence_refs": [valid_ev],
                    "confidence": 0.92,
                },
            },
        )
        # Cacat 2: bukti yatim / menggantung (orphan ref) + Cacat 3: hash rantai rusak.
        e4 = _build_entry(
            4,
            e3["hash"],
            {
                "type": "record",
                "record": {
                    "id": "rec-orphan-4",
                    "kind": "fact",
                    "content": "klaim dengan referensi hilang",
                    "source": {"kind": "verify", "ref": missing_ev},
                    "evidence_refs": [missing_ev],
                    "confidence": 0.8,
                },
            },
            tamper_hash="0" * 64,
        )
        # Cacat 4: provenance tak lengkap (tanpa ref & tanpa confidence), rantai setelah e4 tersambung ke e4["hash"].
        e5 = _build_entry(
            5,
            e4["hash"],
            {
                "type": "record",
                "record": {
                    "id": "rec-noprov-5",
                    "kind": "fact",
                    "content": "rekaman tanpa provenance lengkap",
                    "source": {"kind": "manual", "ref": ""},
                },
            },
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mem_path = root / "memory.jsonl"
            refs_path = root / "verified_refs.json"
            out_path = root / "audit.json"
            mem_path.write_text(
                "\n".join(json.dumps(e, ensure_ascii=False) for e in (e1, e2, e3, e4, e5)) + "\n",
                encoding="utf-8",
            )
            refs_path.write_text(json.dumps([valid_ev]), encoding="utf-8")

            rc = memory_hygiene_audit.main(
                ["--memory", str(mem_path), "--refs", str(refs_path), "--out", str(out_path)]
            )
            self.assertEqual(rc, 0)
            rep = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertEqual(rep["schema"], memory_hygiene_audit.SCHEMA)
        self.assertFalse(rep["hygiene_ok"])

        # Rantai hash: tepat 4 entri sah (1,2,3,5) dan 1 cacat hash_mismatch pada seq 4.
        self.assertFalse(rep["hash_chain"]["valid"])
        self.assertEqual(rep["hash_chain"]["total_entries"], 5)
        self.assertEqual(rep["hash_chain"]["verified_entries"], 4)
        self.assertEqual(rep["hash_chain"]["error_count"], 1)
        self.assertEqual(rep["hash_chain"]["errors"][0]["reason"], "hash_mismatch")
        self.assertEqual(rep["hash_chain"]["errors"][0]["seq"], 4)

        # Duplikat persis: tepat 1 kelompok antara rec-clean-1 dan rec-dup-3.
        self.assertEqual(rep["duplicates"]["exact_duplicate_group_count"], 1)
        self.assertEqual(
            rep["duplicates"]["exact_duplicate_groups"][0]["record_ids"],
            ["rec-clean-1", "rec-dup-3"],
        )

        # Referensi yatim: hanya dari rec-orphan-4 (2 field: source.ref dan evidence_refs).
        self.assertEqual(rep["orphan_refs"]["dangling_evidence_count"], 2)
        self.assertTrue(
            all(
                item["record_id"] == "rec-orphan-4" and item["ref"] == missing_ev
                for item in rep["orphan_refs"]["dangling_evidence_refs"]
            )
        )

        # Kelengkapan provenance: 4 dari 5 rekaman lengkap, rec-noprov-5 tidak lengkap.
        self.assertEqual(rep["provenance"]["total_records"], 5)
        self.assertEqual(rep["provenance"]["provenance_complete_records"], 4)
        self.assertEqual(rep["provenance"]["provenance_completeness_rate"], 0.8)
        self.assertEqual(len(rep["provenance"]["incomplete_records"]), 1)
        self.assertEqual(
            rep["provenance"]["incomplete_records"][0]["record_id"], "rec-noprov-5"
        )

    def test_clean_cognitive_memory_store_passes_all_checks(self) -> None:
        from ace_operational.cognitive_memory import CognitiveMemory

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mem = CognitiveMemory(root)
            digest = mem.anchor_evidence(b"verified unit artifact")
            mem.remember(
                kind="semantic",
                content={"claim": "house_check murni baca"},
                source_kind="evidence",
                source_ref=digest,
                confidence=0.95,
            )
            rep = memory_hygiene_audit.audit_memory_log(root / "memory.jsonl")

        self.assertTrue(rep["hygiene_ok"])
        self.assertTrue(rep["hash_chain"]["valid"])
        self.assertEqual(rep["hash_chain"]["verified_entries"], 2)
        self.assertEqual(rep["provenance"]["provenance_completeness_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
