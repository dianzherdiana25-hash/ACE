"""Verifier kuorum, ambiguitas, dan ketahanan audit panel."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import resolution_panel as model


def q(n, d=1):
    return {"numerator": n, "denominator": d}


def ballot(name, stance, rubric, when="2026-11-20T12:00:00Z"):
    return {"reviewer": name, "ballot_ref": f"fixture/ballot/{name}",
            "rubric_hash": model.rubric_digest(rubric), "stance": stance,
            "submitted_at": when, "evidence_refs": [] if stance == "abstain" else [f"fixture/evidence/{name}"]}


def fixture():
    rubric = {"ref": "fixture/rubric", "criteria": "Cocokkan tanggal dan nilai di artefak final.",
              "quorum": 3, "agreement": q(2, 3), "ambiguity_ceiling": q(1, 4)}
    return {
        "question_id": "q1", "question_ref": "fixture/q1", "opens_at": "2026-11-20T00:00:00Z",
        "closes_at": "2026-11-21T00:00:00Z", "panel": ["a", "b", "c", "d", "e"],
        "rubric": rubric, "ballots": [
            ballot("a", "yes", rubric), ballot("b", "yes", rubric), ballot("c", "no", rubric),
            ballot("d", "abstain", rubric),
        ],
    }


class PanelTests(unittest.TestCase):
    def test_exact_supermajority_is_resolved_and_auditable(self):
        raw = fixture()
        result = model.resolve(raw)
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["outcome"], 1)
        self.assertEqual(result["counts"], {"yes": 2, "no": 1, "ambiguous": 0, "abstain": 1})
        self.assertEqual(result["shares"], {"yes": q(2, 3), "no": q(1, 3), "ambiguous": q(0)})
        self.assertEqual(result["substantive_ballots"], 3)
        self.assertEqual(result["valid_ballots"], 4)
        self.assertEqual(result["panel_without_valid_ballot"], ["e"])
        self.assertEqual(result["accepted"][0]["evidence_refs"], ["fixture/evidence/a"])
        self.assertEqual(result["rubric"]["sha256"], model.rubric_digest(raw["rubric"]))

    def test_negative_majority_is_a_false_outcome_not_unresolved(self):
        raw = fixture()
        raw["ballots"] = [ballot(reviewer, choice, raw["rubric"])
                          for reviewer, choice in zip("abc", ("no", "no", "ambiguous"))]
        raw["rubric"]["ambiguity_ceiling"] = q(1, 3)
        for row in raw["ballots"]:
            row["rubric_hash"] = model.rubric_digest(raw["rubric"])
        report = model.resolve(raw)
        self.assertEqual(report["status"], "resolved")
        self.assertEqual(report["outcome"], 0)

    def test_equal_ballots_do_not_resolve_even_with_quorum(self):
        raw = fixture()
        raw["ballots"][3] = ballot("d", "no", raw["rubric"])
        report = model.resolve(raw)
        self.assertEqual(report["status"], "agreement_missing")
        self.assertIsNone(report["outcome"])
        self.assertEqual(report["decisive_ballots"], [])

    def test_ambiguity_ceiling_can_stop_a_definite_supermajority(self):
        raw = fixture()
        raw["ballots"][2] = ballot("c", "ambiguous", raw["rubric"])
        result = model.resolve(raw)
        self.assertEqual(result["status"], "ambiguity_ceiling_exceeded")
        self.assertEqual(result["shares"]["yes"], q(2, 3))
        self.assertEqual(result["shares"]["ambiguous"], q(1, 3))

    def test_ambiguous_ballots_stay_in_agreement_denominator(self):
        raw = fixture()
        raw["ballots"][2] = ballot("c", "ambiguous", raw["rubric"])
        raw["ballots"][3] = ballot("d", "no", raw["rubric"])
        self.assertEqual(model.resolve(raw)["status"], "agreement_missing")

    def test_only_substantive_ballots_enter_quorum(self):
        raw = fixture()
        raw["ballots"][2] = ballot("c", "abstain", raw["rubric"])
        self.assertEqual(model.resolve(raw)["status"], "quorum_missing")
        raw["ballots"] = [ballot("c", "abstain", raw["rubric"])]
        report = model.resolve(raw)
        self.assertEqual(report["shares"], {"yes": None, "no": None, "ambiguous": None})
        self.assertEqual(report["valid_ballots"], 1)

    def test_late_outside_panel_and_different_rubric_stay_visible(self):
        raw = fixture()
        raw["ballots"] += [ballot("x", "yes", raw["rubric"]),
                           ballot("e", "yes", raw["rubric"], "2026-11-21T00:00:00.000001Z")]
        raw["ballots"][0]["rubric_hash"] = "0" * 64
        report = model.resolve(raw)
        self.assertEqual({item["reviewer"]: item["reason"] for item in report["excluded"]}, {
            "a": "rubric_mismatch", "e": "outside_window", "x": "not_on_panel",
        })
        self.assertEqual(report["panel_without_valid_ballot"], ["a", "e"])
        self.assertEqual(report["status"], "quorum_missing")

    def test_windows_include_open_and_close_and_normalize_zones(self):
        raw = fixture()
        raw["ballots"][0]["submitted_at"] = "2026-11-20T07:00:00+07:00"
        raw["ballots"][1]["submitted_at"] = "2026-11-21T07:00:00+07:00"
        result = model.resolve(raw)
        self.assertFalse(result["excluded"])
        for index, day in enumerate((20, 21)):
            self.assertEqual(result["accepted"][index]["submitted_at"], f"2026-11-{day}T00:00:00+00:00")

    def test_ballots_that_can_change_an_outcome_are_traced(self):
        first = model.resolve(fixture())
        self.assertEqual([x["reviewer"] for x in first["decisive_ballots"]], ["a", "b", "c"])
        raw = fixture()
        raw["ballots"][2] = ballot("c", "yes", raw["rubric"])
        raw["ballots"].append(ballot("e", "no", raw["rubric"]))
        self.assertEqual(model.resolve(raw)["decisive_ballots"], [])

    def test_invalid_ballot_inputs_are_refused_with_no_partial_outcome(self):
        for change in ({"stance": "maybe"}, {"evidence_refs": []}, {"evidence_refs": ["fixture/ballot/a"]},
                       {"reviewer": "b"}, {"ballot_ref": "fixture/ballot/b"}):
            raw = fixture()
            raw["ballots"][0].update(change)
            with self.subTest(change=change), self.assertRaises(model.InputError):
                model.resolve(raw)

    def test_rubric_validation_rejects_half_or_smaller_agreement(self):
        for agreement in (q(1, 2), q(1, 3), q(0)):
            raw = fixture()
            raw["rubric"]["agreement"] = agreement
            with self.subTest(agreement=agreement), self.assertRaises(model.InputError):
                model.resolve(raw)

    def test_cli_uses_canonical_order_for_panel_ballot_and_rubric(self):
        raw = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "panel.json"
        logs = []
        for _ in range(2):
            path.write_text(json.dumps(raw), encoding="utf-8")
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(model.main([str(path)]), 0)
            logs.append(output.getvalue())
            raw["panel"].reverse()
            raw["ballots"].reverse()
            raw["rubric"] = dict(reversed(list(raw["rubric"].items())))
        self.assertEqual(logs[0], logs[1])

    def test_misattributed_ballot_does_not_borrow_roster_access(self):
        raw = fixture()
        raw["ballots"][0]["reviewer"] = "aa"
        result = model.resolve(raw)
        self.assertEqual(result["panel_without_valid_ballot"], ["a", "e"])
        self.assertEqual(result["excluded"][0]["reason"], "not_on_panel")
        self.assertEqual(result["excluded"][0]["ballot_ref"], "fixture/ballot/a")

    def test_rewritten_criteria_invalidate_already_cast_ballots(self):
        raw = fixture()
        original_hash = model.rubric_digest(raw["rubric"])
        raw["rubric"]["criteria"] = "Gunakan draf, termasuk yang belum final."
        report = model.resolve(raw)
        self.assertNotEqual(report["rubric"]["sha256"], original_hash)
        self.assertEqual(report["accepted"], [])
        self.assertEqual(len(report["excluded"]), 4)
        self.assertTrue(all(row["reason"] == "rubric_mismatch" for row in report["excluded"]))
        self.assertEqual(report["status"], "quorum_missing")
        self.assertIsNone(report["outcome"])
