"""Pastikan persyaratan aritmetika bench tidak disatukan atau dilonggarkan."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import verify_bench
from ace_deliberation.test_brier_scorer import fixture as brier_fixture
from ace_deliberation.test_debate_protocol import fixture as debate_fixture
from ace_deliberation.test_decision_brief import fixture as brief_fixture


def pair(case_id, gain):
    debate = debate_fixture()
    debate["plan"]["debate_id"] = case_id
    return {"case_id": case_id,
            "candidate": {"decision_ref": f"fixture/{case_id}/deliberation", "points": 70 + gain,
                          "score_ref": f"fixture/{case_id}/candidate-score", "brief_input": brief_fixture(debate)},
            "single_organ": {"decision_ref": f"fixture/{case_id}/single", "points": 70,
                             "score_ref": f"fixture/{case_id}/single-score"}}


def fixture():
    return {"paired_decisions": [pair("case2", 5), pair("case1", 15)], "brier_input": brier_fixture()}


class BenchTests(unittest.TestCase):
    def test_exact_ten_point_threshold_and_coverage(self):
        raw = fixture()
        report = verify_bench.evaluate(raw)
        self.assertTrue(report["arithmetic_checks_met"])
        self.assertEqual([case["case_id"] for case in report["cases"]], ["case1", "case2"])
        conditions = report["requirements"]
        self.assertEqual(conditions["deliberation_gain_points"]["observed"],
                         {"numerator": 10, "denominator": 1})
        self.assertEqual(conditions["precedent_coverage"]["observed"], {"numerator": 1, "denominator": 1})
        self.assertTrue(conditions["forecast_beats_base_rate"]["met"])
        self.assertEqual(report, verify_bench.evaluate({**raw, "paired_decisions": raw["paired_decisions"][::-1]}))

    def test_partial_coverage_does_not_pass_better_scores(self):
        raw = fixture()
        raw["paired_decisions"][0]["candidate"]["brief_input"]["archive"] = []
        report = verify_bench.evaluate(raw)
        self.assertFalse(report["arithmetic_checks_met"])
        self.assertEqual(report["requirements"]["precedent_coverage"]["observed"], {"numerator": 1, "denominator": 2})
        self.assertTrue(report["requirements"]["deliberation_gain_points"]["met"])
        self.assertTrue(report["requirements"]["forecast_beats_base_rate"]["met"])

    def test_near_threshold_and_equal_brier_stay_separate_failures(self):
        raw = fixture()
        raw["paired_decisions"][1]["candidate"]["points"] -= 1
        for row in raw["brier_input"]["forecasts"]:
            row["probability"] = "0.5"
        result = verify_bench.evaluate(raw)
        conditions = result["requirements"]
        self.assertEqual(conditions["deliberation_gain_points"]["observed"],
                         {"numerator": 19, "denominator": 2})
        self.assertFalse(conditions["forecast_beats_base_rate"]["met"])
        self.assertEqual(result["brier"]["verdict"], "tie")
        self.assertFalse(result["arithmetic_checks_met"])

    def test_rejects_missing_or_reused_ratings_and_foreign_brief(self):
        raw = fixture()
        row = raw["paired_decisions"][0]
        for changes in ({"single_organ": {**row["single_organ"], "score_ref": row["candidate"]["score_ref"]}},
                        {"candidate": {**row["candidate"], "points": True}}, {"case_id": "different-brief"}):
            with self.subTest(changes=changes), self.assertRaises(verify_bench.BenchError):
                verify_bench.evaluate({**raw, "paired_decisions": [{**row, **changes}]})

    def test_cli_ecosystem_requires_all_three_checks(self):
        raw = fixture()
        raw["paired_decisions"][0]["candidate"]["brief_input"]["archive"] = []
        path = Path(self.enterContext(TemporaryDirectory())) / "bench.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(verify_bench.main([str(path)]), 1)
        self.assertFalse(json.loads(output.getvalue())["arithmetic_checks_met"])
