from hashlib import sha256
import unittest

from ._contracts import ContractError, identity
from .script_writer import write_script


def script_plan():
    cards = [dict(id=key, kind=kind, body=body, source_ref=f"fixture:{key}", visual="Sorot kartu",
                  rank=rank, topics=[topic]) for key, kind, body, rank, topic in (
         ("intro", "hook", "Pola warna berubah.", 4, "cahaya"),
         ("basis", "context", "Eksperimen hanya di meja.", 4, "cahaya"),
         ("measured", "evidence", "Meter mencatat 12 lux.", 8, "cahaya"),
         ("extra", "evidence", "Sensor diulang pada permukaan terpisah dengan material lebih gelap.", 0, "cahaya"),
         ("other", "evidence", "Kapal tiba.", 99, "lautan"),
         ("finish", "closing", "Ingat posisi sensor.", 10, "cahaya"))]
    return {"schema": "ace.media.script-plan.v1", "topic": "Cahaya", "audience": "Siswa",
            "length_ms": 9000, "words_per_minute": 180, "cards": cards}


class ScriptTests(unittest.TestCase):
    def test_narration_uses_ranked_relevant_evidence_and_links_original(self):
        plan = script_plan()
        report = write_script(plan, identity(plan))
        self.assertEqual([row["card_id"] for row in report["beats"]],
                         ["intro", "basis", "measured", "finish"])
        claim = report["beats"][2]
        self.assertIn("12 lux", claim["narration"])
        self.assertEqual(claim["source_ref"], "fixture:measured")
        self.assertEqual(claim["source_excerpt_sha256"], sha256(b"Meter mencatat 12 lux.").hexdigest())
        self.assertEqual(report["unused_cards"], ["extra", "other"])
        self.assertLessEqual(report["duration_ms"], 9000)
        self.assertEqual([row["start_ms"] for row in report["beats"][1:]],
                         [row["end_ms"] for row in report["beats"][:-1]])

    def test_no_support_or_no_time_cannot_produce_claims(self):
        plan = script_plan()
        plan["cards"][2]["topics"] = ["another"]
        plan["cards"][3]["topics"] = ["another"]
        with self.assertRaisesRegex(ContractError, "bukti"):
            write_script(plan, identity(plan))
        plan["length_ms"] = 1000
        with self.assertRaisesRegex(ContractError, "durasi"):
            write_script(plan, identity(plan))
