"""Uji urutan, batas keputusan, dan audit replay tanpa memanggil organ."""
from copy import deepcopy
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import debate_protocol as debate


def fixture():
    plan = {"debate_id": "d1", "question": "Pilih prosedur verifikasi", "rounds": 1, "budget": 9,
            "seats": [{"participant": "a", "role": "proponent"},
                      {"participant": "b", "role": "challenger"},
                      {"participant": "c", "role": "reviewer"}]}
    turns = [
        {"turn_id": "a1", "participant": "a", "move": "argument", "statement": "Gunakan dua sumber",
         "cost": 3, "evidence_refs": ["source-a"]},
        {"turn_id": "b1", "participant": "b", "move": "objection", "statement": "Uji independensi sumber",
         "targets": ["a1"], "cost": 2},
        {"turn_id": "c1", "participant": "c", "move": "synthesis", "statement": "Adopsi dengan pemeriksaan",
         "targets": ["a1", "b1"], "cost": 4},
    ]
    return {"plan": plan, "turns": turns, "decision": {
        "outcome": "adopt", "rationale": "Sintesis mencatat syarat pemeriksaan.", "basis_turns": ["c1"],
    }}


class DebateTests(unittest.TestCase):
    def test_replay_yields_exact_report_and_preserves_dissent(self):
        raw = fixture()
        report = debate.replay(raw)
        self.assertEqual(debate.replay(raw), report)
        self.assertEqual(report["spent"], 9)
        self.assertEqual(report["dissent_turns"], ["b1"])
        self.assertEqual(report["decision"], raw["decision"])
        self.assertIsNone(report["next_turn"])
        self.assertTrue(debate.verify_report(report))
        altered = deepcopy(report)
        altered["turns"][1]["statement"] = "diganti"
        self.assertFalse(debate.verify_report(altered))

    def test_rejection_leaves_turn_and_budget_intact(self):
        raw = fixture()
        protocol = debate.DebateProtocol(raw["plan"])
        before = protocol.report()
        with self.assertRaisesRegex(debate.DebateError, "luar giliran"):
            protocol.submit(raw["turns"][1])
        self.assertEqual(protocol.report(), before)
        protocol.submit(raw["turns"][0])
        before = protocol.report()
        for change, message in (({"targets": ["future"]}, "belum ada"),
                                ({"cost": 7}, "melampaui"),
                                ({"turn_id": "a1"}, "ganda"),
                                ({"targets": []}, "perlu merujuk"),
                                ({"move": "argument"}, "pertama penyanggah")):
            with self.subTest(change=change), self.assertRaisesRegex(debate.DebateError, message):
                protocol.submit({**raw["turns"][1], **change})
            self.assertEqual(protocol.report(), before)

    def test_no_early_decision_or_unanswered_adoption(self):
        raw = fixture()
        protocol = debate.DebateProtocol(raw["plan"])
        with self.assertRaisesRegex(debate.DebateError, "semua giliran"):
            protocol.close(raw["decision"])
        raw["turns"][-1]["targets"] = ["a1"]
        for turn in raw["turns"]:
            protocol.submit(turn)
        with self.assertRaisesRegex(debate.DebateError, "belum ditanggapi"):
            protocol.close(raw["decision"])
        self.assertEqual(protocol.close({**raw["decision"], "outcome": "defer"})["outcome"], "defer")
        with self.assertRaises(debate.DebateError):
            protocol.close(raw["decision"])

    def test_second_round_restarts_with_same_seats_and_preserves_history(self):
        raw = fixture()
        protocol = debate.DebateProtocol({**raw["plan"], "rounds": 2, "budget": 20})
        for turn in raw["turns"]:
            protocol.submit(turn)
        self.assertEqual(protocol.next_turn, {"round": 2, "participant": "a", "role": "proponent"})
        event = protocol.submit({**raw["turns"][0], "turn_id": "a2", "move": "response", "targets": ["b1"]})
        self.assertEqual(event["round"], 2)
        self.assertEqual(protocol.report()["dissent_turns"], ["b1"])
        self.assertTrue(debate.verify_report(protocol.report()))

    def test_requires_real_seats_strict_numbers_and_utf8(self):
        raw = fixture()
        for change in ({"rounds": True}, {"budget": 0}, {"question": "\ud800"},
                       {"seats": [raw["plan"]["seats"][0]] * 3}):
            with self.subTest(change=change), self.assertRaises(debate.DebateError):
                debate.DebateProtocol({**raw["plan"], **change})

    def test_cli_replays_and_verifies_a_report(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        path = root / "debate.json"
        path.write_text(json.dumps(fixture()), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(debate.main([str(path)]), 0)
        path.write_text(output.getvalue(), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(debate.main([str(path), "--verify-report"]), 0)
            self.assertEqual(json.loads(output.getvalue()), {"valid": True})
