"""Verifier benchmark berpasangan, artefak dan diagnosis domain."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_forge import brain_bench as model
from ace_forge.test_forgetting_guard import case, q


BEFORE, AFTER = "1" * 64, "2" * 64


def observation(key, arm, values):
    score, duration, peak = values
    return {"artifact_sha256": BEFORE if arm == "before" else AFTER,
            "score_bp": score, "elapsed_us": duration, "peak_bytes": peak,
            "assessment_ref": f"score/{key}/{arm}", "measurement_ref": f"usage/{key}/{arm}"}


def record(key, before, after):
    return {"case_id": key, "before": observation(key, "before", before) if before is not None else None,
            "after": observation(key, "after", after) if after is not None else None}


def fixture():
    raw = {"protocol": {"protocol_ref": "p/test", "cases": [
        case("a", "reading"), case("b", "reading"), case("c", "writing"), case("d", "writing"),
    ]}, "rubric_ref": "p/rubric", "before_sha256": BEFORE, "after_sha256": AFTER, "minimum_paired": 1,
        "results": [record("a", (5000, 4, 200), (7000, 1, 300)),
                    record("b", (7000, 1, 250), (6000, 2, 260)),
                    record("c", (8000, 3, 320), (9000, 5, 240)),
                    record("d", (1000, 4, 320), (1000, 8, 260))]}
    return raw, model.bench_digest(raw)


class BenchTests(unittest.TestCase):
    def test_exact_paired_delta_and_two_sided_median(self):
        report = model.report(*fixture())
        overall = report["aggregate"]
        self.assertEqual(overall["compared"], 4)
        self.assertEqual(overall["registered"], 4)
        self.assertEqual(overall["before_mean"], {"score_bp": q(5250), "elapsed_us": q(3), "peak_bytes": q(545, 2)})
        self.assertEqual(overall["after_mean"], {"score_bp": q(5750), "elapsed_us": q(4), "peak_bytes": q(265)})
        self.assertEqual(overall["mean_delta"], {"score_bp": q(500), "elapsed_us": q(1), "peak_bytes": q(-15, 2)})
        self.assertEqual(overall["median_delta"], {"score_bp": q(500), "elapsed_us": q(3, 2), "peak_bytes": q(-25)})
        self.assertEqual(overall["quality_signs"], {"better": 2, "tie": 1, "worse": 1})
        self.assertEqual(overall["lowest_quality_delta"], {"score_bp": -1000, "case_ids": ["b"]})

    def test_reports_cost_and_quality_regressions_with_specific_refs(self):
        reading, writing = model.report(*fixture())["domains"]
        self.assertEqual((reading["domain"], writing["domain"]), ("reading", "writing"))
        self.assertEqual(reading["mean_delta"]["elapsed_us"], q(-1))
        self.assertEqual(writing["mean_delta"]["elapsed_us"], q(3))
        bad = reading["cases"][1]
        self.assertEqual(bad["delta"], {"score_bp": -1000, "elapsed_us": 1, "peak_bytes": 10})
        self.assertEqual(bad["before"]["assessment_ref"], "score/b/before")
        self.assertEqual(bad["after"]["measurement_ref"], "usage/b/after")
        self.assertEqual(bad["case_ref"], "q/b")

    def test_partial_domain_and_overall_are_unscored_and_independent_domain_remains_visible(self):
        raw, expected = fixture()
        raw["results"][0]["after"] = None
        raw["results"].pop(1)
        value = model.report(raw, expected)
        reading, writing = value["domains"]
        self.assertEqual(value["aggregate"]["status"], "incomplete")
        self.assertEqual(reading["status"], "too_few_pairs")
        self.assertEqual(writing["status"], "complete")
        self.assertIsNone(value["aggregate"]["mean_delta"])
        self.assertIsNone(reading["lowest_quality_delta"])
        self.assertEqual(reading["cases"][0]["missing"], ["after"])
        self.assertEqual(reading["cases"][1]["missing"], ["before", "after"])
        self.assertEqual(writing["compared"], 2)

    def test_minimum_paired_can_withhold_domains_without_discarding_rows(self):
        raw, _ = fixture()
        raw["minimum_paired"] = 3
        report = model.report(raw, model.bench_digest(raw))
        self.assertEqual(report["aggregate"]["status"], "complete")
        self.assertTrue(all(row["status"] == "too_few_pairs" for row in report["domains"]))
        self.assertEqual(len(report["domains"][0]["cases"]), 2)

    def test_artifact_hash_not_matching_before_or_after_is_an_error(self):
        raw, expected = fixture()
        raw["results"][0]["after"]["artifact_sha256"] = BEFORE
        with self.assertRaisesRegex(model.InputError, "Hash artefak"):
            model.report(raw, expected)

    def test_bench_anchor_binds_metric_rubric_roster_and_artifact(self):
        for change in ({"rubric_ref": "p/new"}, {"after_sha256": "3" * 64}, {"minimum_paired": 2}):
            raw, expected = fixture()
            with self.subTest(change=change), self.assertRaisesRegex(model.InputError, "anchor"):
                model.report({**raw, **change}, expected)
        raw, expected = fixture()
        raw["protocol"]["cases"].pop()
        with self.assertRaisesRegex(model.InputError, "anchor"):
            model.report(raw, expected)

    def test_unregistered_repeated_and_impossible_measurements_fail_closed(self):
        raw, expected = fixture()
        for extra in (record("unknown", None, None), raw["results"][0]):
            with self.subTest(extra=extra), self.assertRaises(model.InputError):
                model.report({**raw, "results": [*raw["results"], extra]}, expected)
        for key, invalid in (("score_bp", True), ("score_bp", 10_001), ("elapsed_us", -3), ("peak_bytes", -1),
                             ("assessment_ref", "usage/a/before"), ("measurement_ref", "q/a")):
            raw, expected = fixture()
            raw["results"][0]["after"][key] = invalid
            with self.subTest(key=key), self.assertRaises(model.InputError):
                model.report(raw, expected)

    def test_preserves_ties_in_lowest_case_and_zero_delta(self):
        raw, expected = fixture()
        for item in raw["results"]:
            item["after"]["score_bp"] = item["before"]["score_bp"]
        report = model.report(raw, expected)["aggregate"]
        self.assertEqual(report["mean_delta"]["score_bp"], q(0))
        self.assertEqual(report["lowest_quality_delta"], {"score_bp": 0, "case_ids": ["a", "b", "c", "d"]})
        self.assertEqual(report["quality_signs"], {"better": 0, "tie": 4, "worse": 0})

    def test_cli_bytes_match_on_roster_and_result_permutation(self):
        raw, expected = fixture()
        path = Path(self.enterContext(TemporaryDirectory())) / "bench.json"
        observed = []
        for _ in range(2):
            path.write_text(json.dumps(raw), encoding="utf-8")
            with redirect_stdout(StringIO()) as output:
                self.assertEqual(model.main([str(path), "--expect-bench-sha256", expected]), 0)
            observed.append(output.getvalue())
            raw["protocol"]["cases"].reverse()
            raw["results"].reverse()
        self.assertEqual(observed[0], observed[1])
        self.assertEqual(json.loads(observed[0])["before_sha256"], BEFORE)

    def test_identical_artifact_identifiers_are_not_two_independent_arms(self):
        raw, _ = fixture()
        with self.assertRaisesRegex(model.InputError, "berbeda"):
            model.bench_digest({**raw, "after_sha256": BEFORE})

    def test_zero_quality_and_cost_are_valid_measurements(self):
        raw, expected = fixture()
        for item in raw["results"]:
            for label in ("before", "after"):
                item[label].update(score_bp=0, elapsed_us=0, peak_bytes=0)
        result = model.report(raw, expected)["aggregate"]
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["mean_delta"], dict.fromkeys(("score_bp", "elapsed_us", "peak_bytes"), q(0)))

    def test_missing_or_malformed_external_anchor_is_rejected(self):
        raw, _ = fixture()
        for bad in (None, "b" * 63, "b" * 64):
            with self.subTest(bad=bad), self.assertRaises(model.InputError):
                model.report(raw, bad)

    def test_all_missing_cases_return_coverage_without_a_fabricated_average(self):
        raw, expected = fixture()
        value = model.report({**raw, "results": []}, expected)["aggregate"]
        self.assertEqual((value["compared"], value["registered"]), (0, 4))
        self.assertEqual(value["status"], "too_few_pairs")
        self.assertIsNone(value["before_mean"])
        self.assertIsNone(value["quality_signs"])
