"""Verifier penurunan domain, kasus kritis, dan laporan cakupan."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import forgetting_guard as model


def q(n, d=1):
    return {"numerator": n, "denominator": d}


def case(key, scope, critical=False):
    return {"case_id": key, "domain": scope, "case_ref": f"q/{key}", "critical": critical}


def observation(key, first, second):
    return {"case_id": key,
            "baseline": None if first is None else {"passed": first, "assessment_ref": f"r/{key}/baseline"},
            "candidate": None if second is None else {"passed": second, "assessment_ref": f"r/{key}/candidate"}}


def fixture():
    protocol = {"protocol_ref": "p/benchmark", "cases": [
        case("a", "general"), case("b", "general"), case("c", "general"),
        case("x", "tool"), case("y", "tool"),
    ]}
    raw = {"protocol": protocol, "results": [
        observation("a", True, False), observation("b", True, True), observation("c", False, False),
        observation("x", False, True), observation("y", False, True),
    ]}
    return raw, model.protocol_digest(protocol)


def domains(result):
    return {domain["domain"]: domain for domain in result["domains"]}


class ForgettingTests(unittest.TestCase):
    def test_general_drop_cannot_be_cancelled_by_a_larger_gain_elsewhere(self):
        report = model.screen(*fixture())
        self.assertEqual(report["status"], "hold")
        self.assertEqual(report["blocked_domains"], ["general"])
        general, tool = report["domains"]
        self.assertEqual(general["baseline_accuracy"], q(2, 3))
        self.assertEqual(general["candidate_accuracy"], q(1, 3))
        self.assertEqual(general["accuracy_delta"], q(-1, 3))
        self.assertEqual(general["reasons"], ["domain_accuracy_dropped"])
        self.assertEqual(tool["accuracy_delta"], q(1))
        self.assertEqual(general["counts"], {"retained": 1, "regressed": 1, "improved": 0, "both_failed": 1})

    def test_critical_loss_blocks_even_when_domain_accuracy_is_constant(self):
        raw, _ = fixture()
        raw["protocol"]["cases"][0]["critical"] = True
        raw["results"][2] = observation("c", False, True)
        result = model.screen(raw, model.protocol_digest(raw["protocol"]))
        general = domains(result)["general"]
        self.assertEqual(general["accuracy_delta"], q(0))
        self.assertEqual(general["critical_regressions"], ["a"])
        self.assertEqual(general["reasons"], ["critical_regression"])

    def test_equal_accuracy_is_reported_at_zero_with_named_case_swap(self):
        raw, digest = fixture()
        raw["results"][2] = observation("c", False, True)
        result = model.screen(raw, digest)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["blocked_domains"], [])
        general = result["domains"][0]
        self.assertEqual(general["accuracy_delta"], q(0))
        self.assertEqual(general["cases"][0]["status"], "regressed")
        self.assertEqual(general["cases"][2]["status"], "improved")

    def test_missing_result_and_single_missing_arm_are_explicit_and_unscored(self):
        raw, digest = fixture()
        raw["results"][1]["candidate"] = None
        raw["results"].pop(2)
        general = model.screen(raw, digest)["domains"][0]
        self.assertEqual(general["paired_cases"], 1)
        self.assertEqual(general["expected_cases"], 3)
        self.assertIsNone(general["baseline_accuracy"])
        self.assertIsNone(general["accuracy_delta"])
        self.assertEqual(general["reasons"], ["missing_assessments"])
        self.assertEqual(general["cases"][1]["missing"], ["candidate"])
        self.assertEqual(general["cases"][2]["missing"], ["baseline", "candidate"])

    def test_known_critical_regression_still_blocks_when_coverage_incomplete(self):
        raw, _ = fixture()
        raw["protocol"]["cases"][0]["critical"] = True
        raw["results"][2]["baseline"] = None
        report = model.screen(raw, model.protocol_digest(raw["protocol"]))
        self.assertEqual(report["domains"][0]["reasons"], ["missing_assessments", "critical_regression"])

    def test_case_judgements_and_protocol_are_all_traceable(self):
        report = model.screen(*fixture())
        row = report["domains"][0]["cases"][0]
        self.assertEqual(report["protocol_ref"], "p/benchmark")
        self.assertEqual(row["case_ref"], "q/a")
        self.assertEqual(row["baseline"]["assessment_ref"], "r/a/baseline")
        self.assertEqual(row["candidate"]["assessment_ref"], "r/a/candidate")

    def test_anchored_protocol_refuses_changed_case_domain_or_criticality(self):
        for change in ({"case_ref": "q/changed"}, {"domain": "reassigned"}, {"critical": True}):
            raw, expected = fixture()
            raw["protocol"]["cases"][0].update(change)
            with self.subTest(change=change), self.assertRaisesRegex(model.InputError, "komitmen"):
                model.screen(raw, expected)

    def test_duplicate_or_unknown_results_cannot_enter_pair_count(self):
        raw, digest = fixture()
        for new in (raw["results"][0], observation("new", True, True)):
            with self.subTest(new=new), self.assertRaisesRegex(model.InputError, "ganda|luar"):
                model.screen({**raw, "results": [*raw["results"], new]}, digest)

    def test_invalid_boolean_and_reused_assessment_ref_fail_closed(self):
        for change in ({"passed": 1}, {"assessment_ref": "r/a/baseline"}, {"assessment_ref": "q/a"}):
            raw, digest = fixture()
            raw["results"][0]["candidate"].update(change)
            with self.subTest(change=change), self.assertRaises(model.InputError):
                model.screen(raw, digest)

    def test_unregistered_domains_and_invalid_roster_cannot_publish_empty_pass(self):
        for added in (case("a", "again"), case("new", "tool", 1),
                      {"case_id": "new", "domain": "general", "case_ref": "q/a", "critical": False}):
            raw, _ = fixture()
            raw["protocol"]["cases"].append(added)
            with self.subTest(added=added), self.assertRaises(model.InputError):
                model.protocol_digest(raw["protocol"])
        with self.assertRaises(model.InputError):
            model.protocol_digest({"protocol_ref": "p/empty", "cases": []})

    def test_cli_canonical_output_and_exit_status_for_hold_and_pass(self):
        data, digest = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "guard.json"
        outputs = []
        for _ in range(2):
            path.write_text(json.dumps(data), encoding="utf-8")
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(model.main([str(path), "--expect-protocol-sha256", digest]), 1)
            outputs.append(output.getvalue())
            data["results"].reverse()
            data["protocol"]["cases"].reverse()
        self.assertEqual(outputs[0], outputs[1])
        data["results"][0] = observation("a", True, True)
        path.write_text(json.dumps(data), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(model.main([str(path), "--expect-protocol-sha256", digest]), 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "pass")

    def test_zero_baseline_is_distinct_from_no_comparable_fixture_data(self):
        raw, anchor = fixture()
        result = model.screen(raw, anchor)
        self.assertEqual(domains(result)["tool"]["baseline_accuracy"], q(0))
        raw["results"].clear()
        result = model.screen(raw, anchor)
        self.assertIsNone(domains(result)["tool"]["baseline_accuracy"])
        self.assertEqual(result["blocked_domains"], ["general", "tool"])

    def test_complete_all_fail_is_observed_zero_for_both_arms(self):
        raw, anchor = fixture()
        raw["results"] = [observation(case["case_id"], False, False) for case in raw["protocol"]["cases"]]
        report = model.screen(raw, anchor)
        self.assertEqual(report["status"], "pass")
        self.assertTrue(all(row["baseline_accuracy"] == q(0) and row["candidate_accuracy"] == q(0)
                            for row in report["domains"]))
