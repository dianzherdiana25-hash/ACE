"""Tests for the round-2 gate instrument (synthetic dossiers)."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ace_operational.round2_instrument import assess_round2

IMPROVEMENT = {"name": "lifted-mechanism-round2",
               "digest": "abc123"}


def report(**overrides):
    data = {"protocol_hash": "aa" * 32,
            "audit_status": "CLEAN",
            "improvement_name": IMPROVEMENT["name"],
            "improvement_digest": IMPROVEMENT["digest"],
            "held_out": True,
            "baseline_score": 20.0,
            "improvement_score": 85.0,
            "margin_pp": 60.0}
    data.update(overrides)
    return data


class Round2InstrumentTests(unittest.TestCase):
    def _dossier(self, tmp, source, evaluations):
        d = Path(tmp)
        (d / "source.json").write_text(json.dumps(source))
        eval_files = []
        for i, ev in enumerate(evaluations):
            name = f"eval{i}.json"
            (d / name).write_text(json.dumps(ev))
            eval_files.append({"family": ev.get("family", "grid"),
                               "report": name})
        dossier = {"improvement": IMPROVEMENT,
                   "source": {"family": source.get("family",
                                                   "statement_order"),
                              "report": "source.json"},
                   "evaluations": eval_files}
        (d / "dossier.json").write_text(json.dumps(dossier))
        return str(d / "dossier.json")

    def test_lift_demonstrated(self):
        with TemporaryDirectory() as tmp:
            path = self._dossier(
                tmp,
                report(family="statement_order"),
                [report(family="grid", baseline_score=70.0,
                        improvement_score=70.0, margin_pp=0.0)])
            result = assess_round2(dossier=path)
            self.assertEqual(result["overall"], "LIFT_DEMONSTRATED")
            self.assertEqual(result["identity_mismatches"], [])

    def test_target_below_margin(self):
        with TemporaryDirectory() as tmp:
            path = self._dossier(
                tmp,
                report(family="statement_order",
                       improvement_score=40.0),
                [report(family="grid", baseline_score=70.0,
                        improvement_score=70.0, margin_pp=0.0)])
            result = assess_round2(dossier=path)
            self.assertEqual(result["overall"], "NOT_DEMONSTRATED")
            self.assertEqual(
                result["clauses"]["C3_positive_lift_effect"]["verdict"],
                "FAIL")

    def test_stability_regression_is_named_failure(self):
        with TemporaryDirectory() as tmp:
            path = self._dossier(
                tmp,
                report(family="statement_order"),
                [report(family="grid", baseline_score=70.0,
                        improvement_score=68.0, margin_pp=0.0)])
            result = assess_round2(dossier=path)
            self.assertEqual(result["overall"], "LIFT_WITH_REGRESSION")
            self.assertEqual(
                result["clauses"]["stability_no_regression"]["verdict"],
                "FAIL")
            self.assertEqual(
                result["clauses"]["C3_positive_lift_effect"]["verdict"],
                "PASS")

    def test_identity_mismatch_forces_not_demonstrated_once(self):
        with TemporaryDirectory() as tmp:
            path = self._dossier(
                tmp,
                report(family="statement_order",
                       improvement_digest="deadbeef"),
                [report(family="grid", baseline_score=70.0,
                        improvement_score=70.0, margin_pp=0.0)])
            result = assess_round2(dossier=path)
            self.assertEqual(result["overall"], "NOT_DEMONSTRATED")
            self.assertEqual(len(result["identity_mismatches"]), 1)

    def test_missing_dossier_fails_closed(self):
        result = assess_round2(dossier="/nonexistent/dossier.json")
        self.assertEqual(result["overall"], "NOT_DEMONSTRATED")
        self.assertIn("missing/unparseable",
                      result["clauses"]["C1_identified_improvement"]
                      ["missing"][0])

    def test_malformed_dossier_fails_closed(self):
        with TemporaryDirectory() as tmp:
            bad = Path(tmp) / "dossier.json"
            bad.write_text("{not json")
            result = assess_round2(dossier=str(bad))
            self.assertEqual(result["overall"], "NOT_DEMONSTRATED")

    def test_missing_margin_not_counted(self):
        with TemporaryDirectory() as tmp:
            target = report(family="statement_order")
            del target["margin_pp"]
            path = self._dossier(
                tmp, target,
                [report(family="grid", baseline_score=70.0,
                        improvement_score=70.0, margin_pp=0.0)])
            result = assess_round2(dossier=path)
            self.assertEqual(result["overall"], "NOT_DEMONSTRATED")
            self.assertTrue(any("margin_pp" in w for w in
                                result["clauses"]["C3_positive_lift_effect"]
                                ["warnings"]))

    def test_non_numeric_scores_fail(self):
        with TemporaryDirectory() as tmp:
            path = self._dossier(
                tmp,
                report(family="statement_order",
                       improvement_score="eighty-five"),
                [report(family="grid", baseline_score=70.0,
                        improvement_score=70.0, margin_pp=0.0)])
            result = assess_round2(dossier=path)
            self.assertEqual(result["overall"], "NOT_DEMONSTRATED")

    def test_one_family_only_fails_c2(self):
        with TemporaryDirectory() as tmp:
            path = self._dossier(tmp,
                                 report(family="statement_order"),
                                 [])
            result = assess_round2(dossier=path)
            self.assertEqual(result["overall"], "NOT_DEMONSTRATED")
            self.assertEqual(
                result["clauses"]["C2_two_distinct_families"]["verdict"],
                "FAIL")

    def test_source_not_positive_fails_c1(self):
        with TemporaryDirectory() as tmp:
            path = self._dossier(
                tmp,
                report(family="statement_order",
                       improvement_score=20.0),
                [report(family="grid", baseline_score=70.0,
                        improvement_score=70.0, margin_pp=0.0)])
            result = assess_round2(dossier=path)
            self.assertEqual(result["overall"], "NOT_DEMONSTRATED")
            self.assertEqual(
                result["clauses"]["C1_identified_improvement"]["verdict"],
                "FAIL")

    def test_audit_not_clean_fails(self):
        with TemporaryDirectory() as tmp:
            path = self._dossier(
                tmp,
                report(family="statement_order",
                       audit_status="DIRTY"),
                [report(family="grid", baseline_score=70.0,
                        improvement_score=70.0, margin_pp=0.0)])
            result = assess_round2(dossier=path)
            self.assertEqual(result["overall"], "NOT_DEMONSTRATED")

    def test_held_out_false_rejected(self):
        with TemporaryDirectory() as tmp:
            path = self._dossier(
                tmp,
                report(family="statement_order"),
                [report(family="grid", held_out=False,
                        baseline_score=70.0, improvement_score=70.0,
                        margin_pp=0.0)])
            result = assess_round2(dossier=path)
            self.assertEqual(result["overall"], "NOT_DEMONSTRATED")
            self.assertEqual(
                result["clauses"]["C2_two_distinct_families"]["verdict"],
                "FAIL")

    def test_unknown_family_rejected(self):
        with TemporaryDirectory() as tmp:
            path = self._dossier(
                tmp,
                report(family="statement_order"),
                [report(family="shipping", baseline_score=70.0,
                        improvement_score=70.0, margin_pp=0.0)])
            result = assess_round2(dossier=path)
            self.assertEqual(result["overall"], "NOT_DEMONSTRATED")

    def test_duplicate_family_is_warning_not_second_family(self):
        with TemporaryDirectory() as tmp:
            path = self._dossier(
                tmp,
                report(family="statement_order"),
                [report(family="grid", baseline_score=70.0,
                        improvement_score=70.0, margin_pp=0.0),
                 report(family="grid", baseline_score=70.0,
                        improvement_score=70.0, margin_pp=0.0)])
            result = assess_round2(dossier=path)
            self.assertEqual(result["overall"], "LIFT_DEMONSTRATED")
            self.assertTrue(result["clauses"]["C2_two_distinct_families"]
                            ["warnings"])

    def test_missing_protocol_hash_fails_c1(self):
        with TemporaryDirectory() as tmp:
            path = self._dossier(
                tmp,
                report(family="statement_order", protocol_hash=None),
                [report(family="grid", baseline_score=70.0,
                        improvement_score=70.0, margin_pp=0.0)])
            result = assess_round2(dossier=path)
            self.assertEqual(result["overall"], "NOT_DEMONSTRATED")

    def test_target_margin_encoding_h1_bar(self):
        """The H1 bar (arm B >= 80% of discriminating tasks)
        encoded as margin_pp = 80 - baseline: B at 85 vs A at
        20 passes (85 - 20 >= 60); B at 79 fails."""
        with TemporaryDirectory() as tmp:
            path = self._dossier(
                tmp,
                report(family="statement_order",
                       baseline_score=20.0, improvement_score=79.0,
                       margin_pp=60.0),
                [report(family="grid", baseline_score=70.0,
                        improvement_score=70.0, margin_pp=0.0)])
            result = assess_round2(dossier=path)
            self.assertEqual(result["overall"], "NOT_DEMONSTRATED")


if __name__ == "__main__":
    unittest.main()
