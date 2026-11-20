"""Uji pengurangan sumber dan rentang asumsi atas bukti fixture."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import devil_advocate as challenge


def evidence(identifier, amount, family=None):
    return {"id": identifier, "weight": amount, "source_family": family or identifier,
            "source_ref": "fixture/" + identifier}


def assumption(identifier, low, expected, high):
    return {"id": identifier, "source_ref": "fixture/" + identifier,
            "low": low, "expected": expected, "high": high}


class DevilAdvocateTests(unittest.TestCase):
    def test_removing_one_family_removes_all_correlated_support(self):
        raw = {"proposal": "c1", "threshold": "3.5", "assumptions": [],
               "evidence": [evidence("a", "2.2", "related"), evidence("b", "2.2", "related"),
                            evidence("c", "3.2")]}
        result = challenge.test_consensus(raw)
        self.assertEqual(result["baseline_score"], "7.6")
        self.assertEqual(result["weakest"], {
            "kind": "remove_source_family", "id": "related", "score": "3.2", "margin": "-0.3",
            "breaks_threshold": True, "source_refs": ["fixture/a", "fixture/b"],
        })
        self.assertEqual(result["verdict"], "reopen")
        self.assertEqual(challenge.test_consensus({**raw, "evidence": raw["evidence"][::-1]}), result)

    def test_joint_downside_catches_effect_individual_changes_miss(self):
        raw = {"proposal": "c2", "threshold": "4", "evidence": [evidence(str(i), "1") for i in range(4)],
               "assumptions": [assumption("x", "-0.7", "0.2", "1.2"),
                               assumption("y", "-0.7", "0.7", "0.7"),
                               assumption("z", "0.1", "0.8", "0.9")]}
        result = challenge.test_consensus(raw)
        self.assertEqual(result["baseline_score"], "5.7")
        self.assertEqual([row["kind"] for row in result["scenarios"] if row["breaks_threshold"]],
                         ["joint_downside"])
        self.assertEqual(result["weakest"]["margin"], "-1.3")

    def test_exact_threshold_is_not_a_break(self):
        raw = {"proposal": "c3", "threshold": "0.10", "assumptions": [],
               "evidence": [evidence("a", "0.10"), evidence("b", "1e-1")]}
        self.assertEqual(challenge.test_consensus(raw)["verdict"], "survives_declared_challenges")
        raw["threshold"] = "0.3"
        self.assertEqual(challenge.test_consensus(raw)["verdict"], "baseline_below_threshold")

    def test_negative_evidence_is_not_misreported_as_positive_support(self):
        raw = {"proposal": "c4", "threshold": "1", "assumptions": [],
               "evidence": [evidence("a", "5"), evidence("b", "-1")]}
        result = challenge.test_consensus(raw)
        removal = next(row for row in result["scenarios"] if row["id"] == "b")
        self.assertEqual(removal["score"], "5")
        self.assertFalse(removal["breaks_threshold"])

    def test_rejects_data_with_implicit_or_duplicate_support(self):
        raw = {"proposal": "c5", "threshold": 0, "assumptions": [], "evidence": [evidence("a", 1)]}
        for edits in ({"evidence": []}, {"threshold": 1.0}, {"threshold": "NaN"},
                      {"threshold": "1e9999999"}, {"threshold": True},
                      {"evidence": [evidence("a", 1), {**evidence("b", 2), "source_ref": "fixture/a"}]},
                      {"assumptions": [assumption("bad", "3", "2", "4")]}):
            with self.subTest(edits=edits), self.assertRaises(challenge.ChallengeError):
                challenge.test_consensus({**raw, **edits})

    def test_cli_marks_reopen_with_nonzero_and_prints_witness(self):
        path = Path(self.enterContext(TemporaryDirectory())) / "evidence.json"
        path.write_text(json.dumps({"proposal": "c5", "threshold": 1, "assumptions": [],
                                    "evidence": [evidence("a", 1)]}), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(challenge.main([str(path)]), 1)
        self.assertEqual(json.loads(output.getvalue())["weakest"]["source_refs"], ["fixture/a"])

    def test_exact_representation_for_sub_unit_and_negative_powers(self):
        for raw, expected in (("0.000000000000000001", "0.000000000000000001"),
                              ("-40.0000200", "-40.00002"), ("1e+1", "10"), ("-0", "0")):
            with self.subTest(raw=raw):
                self.assertEqual(challenge._decimal(challenge._number(raw)), expected)

    def test_opt_in_handles_correlated_assumption_and_source_loss(self):
        raw = {"proposal": "c6", "threshold": "1.5",
               "evidence": [evidence("a", "1.2"), evidence("b", "1.2")],
               "assumptions": [assumption("x", "0", "0.4", "0.4")]}
        normal = challenge.test_consensus(raw)
        self.assertEqual(normal["verdict"], "survives_declared_challenges")
        extended = challenge.test_consensus({**raw, "combine_downside": True})
        self.assertEqual(extended["verdict"], "reopen")
        weakest = extended["weakest"]
        self.assertEqual((weakest["kind"], weakest["id"], weakest["score"]),
                         ("joint_downside_without_family", "a", "1.2"))
        self.assertEqual(weakest["source_refs"], ["fixture/a", "fixture/x"])

    def test_bad_option_and_nonstandard_decimal_literals_are_rejected(self):
        raw = {"proposal": "c7", "threshold": 0, "assumptions": [], "evidence": [evidence("a", 1)]}
        for update in ({"combine_downside": 1}, {"threshold": "1_000"}, {"threshold": " 1"}):
            with self.subTest(update=update), self.assertRaises(challenge.ChallengeError):
                challenge.test_consensus({**raw, **update})
