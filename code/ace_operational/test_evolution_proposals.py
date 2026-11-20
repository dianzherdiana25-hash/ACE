"""Tes unit untuk code/ace_operational/evolution_proposals.py (AG98)."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest

from ace_operational.evolution_proposals import (
    ProposalValidationError,
    QUEUE_SCHEMA,
    RatificationQueue,
    RatificationTransitionError,
)


class _FakeAnchorStore:
    def __init__(self, valid: set[str]) -> None:
        self._valid = valid

    def verify_ref(self, ref: str) -> bool:
        return ref in self._valid


class EvolutionProposalsTests(unittest.TestCase):
    def test_no_engine_imports(self) -> None:
        src_path = Path(__file__).with_name("evolution_proposals.py")
        tree = ast.parse(src_path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertFalse(any("autonomous_engine" in name for name in imported))

    def test_complete_proposal_advances_to_terjadwal_while_missing_measurement_stops_before_queue(self) -> None:
        anchors = _FakeAnchorStore({"receipt:rcpt-101", "memory:seq-42"})
        queue = RatificationQueue(anchor_store=anchors)

        # Proposal cacat: hilang measurement_method -> harus berhenti di validator sebelum masuk antrean.
        incomplete = {
            "proposal_id": "prop-cacat-ukur",
            "benefit_hypothesis": "Mengurangi 0-record recall sebesar 40%",
            # measurement_method sengaja tidak ada
            "cost": {"cycles": 3},
            "risk": {"level": "low", "mitigation": "Batasi ke fixture terlebih dulu"},
            "fact_anchors": ["receipt:rcpt-101"],
        }
        with self.assertRaises(ProposalValidationError):
            queue.submit(incomplete)
        self.assertIsNone(queue.get("prop-cacat-ukur"))
        self.assertEqual(queue.list_entries(), [])

        # Proposal dengan jangkar fakta menggantung juga ditolak sebelum masuk antrean.
        dangling_prop = {
            "proposal_id": "prop-jangkar-putus",
            "benefit_hypothesis": "Meningkatkan rasio hit",
            "measurement_method": "Probe recall 8 tugas heldout",
            "cost": {"cycles": 2},
            "risk": {"level": "low", "mitigation": "Rollback mudah"},
            "fact_anchors": ["memory:tidak-ada"],
        }
        with self.assertRaises(ProposalValidationError):
            queue.submit(dangling_prop)
        self.assertEqual(queue.list_entries(), [])

        # Proposal lengkap maju penuh: diajukan -> ditantang -> lolos -> terjadwal.
        complete = {
            "proposal_id": "prop-lengkap-01",
            "benefit_hypothesis": "Penggabungan kandidat recall menekan 0-record bertetangga menjadi 0",
            "measurement_method": "Jalankan recall_delivery_probe pada 8 tugas heldout; wajib 0 flag bertetangga",
            "cost": {"cycles": 4, "notes": "1 replay + 1 fixture check"},
            "risk": {"level": "low", "mitigation": "Hanya menaikkan batas kandidat, dapat dibalikkan instan"},
            "fact_anchors": ["receipt:rcpt-101", "memory:seq-42"],
        }
        s1 = queue.submit(complete)
        self.assertEqual(s1["status"], "diajukan")

        # Melompati 'ditantang' langsung ke 'lolos' atau 'terjadwal' ditolak.
        with self.assertRaises(RatificationTransitionError):
            queue.decide("prop-lengkap-01", verdict="lolos", rationale="Lompat")
        with self.assertRaises(RatificationTransitionError):
            queue.schedule("prop-lengkap-01", slot="wave-next")

        s2 = queue.challenge("prop-lengkap-01", notes="Uji apakah latensi tetap di bawah batas 50ms")
        self.assertEqual(s2["status"], "ditantang")

        s3 = queue.decide("prop-lengkap-01", verdict="lolos", rationale="Latensi 12ms < 50ms & 0 flag")
        self.assertEqual(s3["status"], "lolos")

        s4 = queue.schedule("prop-lengkap-01", slot="siklus-terjadwal-07")
        self.assertEqual(s4["status"], "terjadwal")
        self.assertEqual(
            [step["to"] for step in s4["history"]],
            ["diajukan", "ditantang", "lolos", "terjadwal"],
        )

        exported = queue.export_queue()
        self.assertEqual(exported["schema"], QUEUE_SCHEMA)
        self.assertEqual(exported["count"], 1)

    def test_rejected_proposal_cannot_be_scheduled(self) -> None:
        queue = RatificationQueue()
        queue.submit(
            {
                "proposal_id": "prop-tolak",
                "benefit_hypothesis": "Eksperimen risiko tinggi",
                "measurement_method": "Audit regresi",
                "cost": {"cycles": 5},
                "risk": {"level": "high", "mitigation": "Snapshot penuh"},
                "fact_anchors": ["receipt:rcpt-9"],
            }
        )
        queue.challenge("prop-tolak", notes="Biaya lebih tinggi dari manfaat terukur")
        rejected = queue.decide("prop-tolak", verdict="ditolak", rationale="ROI negatif")
        self.assertEqual(rejected["status"], "ditolak")
        with self.assertRaises(RatificationTransitionError):
            queue.schedule("prop-tolak", slot="siklus-01")


if __name__ == "__main__":
    unittest.main()
