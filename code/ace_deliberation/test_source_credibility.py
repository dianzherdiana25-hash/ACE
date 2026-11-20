"""Uji kredibilitas per topik, pewaktuan, dan konflik hasil audit."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_deliberation import source_credibility as credibility


def audit(name, claim, verdict, day, *, topic="logic", source="agency"):
    return {"source": source, "topic": topic, "claim_id": claim, "verdict": verdict,
            "at": f"2026-11-{day}T00:00:00Z", "source_ref": f"fixture/audit/{name}"}


def fixture():
    return {
        "as_of": "2026-11-20T00:00:00Z", "topic": "logic", "window_days": 15,
        "half_weight_after_days": 3, "minimum_cases": 2,
        "sources": [{"id": "agency", "source_ref": "fixture/agency"},
                    {"id": "other", "source_ref": "fixture/other"}],
        "assessments": [
            audit("w1", "support", "supported", "19"),
            audit("w2", "support", "supported", "20"),
            audit("w3", "counter", "contradicted", "12"),
            audit("w4", "ambiguous", "supported", "18"),
            audit("w5", "ambiguous", "contradicted", "19"),
            audit("w6", "pending", "unresolved", "20"),
            audit("w7", "old", "supported", "04"),
            audit("w8", "outside", "supported", "20", topic="different"),
        ],
    }


def exact(a, b=1):
    return {"numerator": a, "denominator": b}


class CredibilityTests(unittest.TestCase):
    def test_posterior_uses_one_claim_even_with_multiple_approvals(self):
        report = credibility.assess(fixture())
        subject, other = report["sources"]
        self.assertEqual(subject["estimate"], exact(4, 7))
        self.assertEqual(subject["resolved_case_count"], 2)
        self.assertEqual(subject["support_weight"], exact(1))
        self.assertEqual(subject["contradiction_weight"], exact(1, 2))
        self.assertIsNone(other["estimate"])
        self.assertEqual(other["status"], "insufficient_history")

    def test_unresolved_and_contested_keep_provenance_without_affecting_score(self):
        row = credibility.assess(fixture())["sources"][0]
        cases = {case["claim_id"]: case for case in row["claims"]}
        self.assertEqual(cases["pending"]["state"], "unresolved")
        self.assertEqual(cases["ambiguous"]["state"], "contested")
        self.assertEqual(cases["ambiguous"]["assessment_refs"], ["fixture/audit/w4", "fixture/audit/w5"])
        self.assertEqual(cases["ambiguous"]["weight"], exact(0))

    def test_exclusion_window_and_domain_are_counted_separately(self):
        report = credibility.assess(fixture())
        self.assertEqual(report["excluded"], [
            {"source_ref": "fixture/audit/w7", "reason": "outside_window"},
            {"source_ref": "fixture/audit/w8", "reason": "other_topic"},
        ])

    def test_insufficient_history_does_not_publish_smoothed_prior(self):
        report = credibility.assess({**fixture(), "minimum_cases": 3})
        self.assertIsNone(report["sources"][0]["estimate"])
        self.assertEqual(report["sources"][0]["resolved_case_count"], 2)

    def test_age_at_threshold_still_has_full_weight(self):
        raw = fixture()
        raw["assessments"][2].update(at="2026-11-17T00:00:00Z")
        self.assertEqual(credibility.assess(raw)["sources"][0]["estimate"], exact(1, 2))

    def test_repeat_recent_assessment_does_not_refresh_first_resolution(self):
        raw = fixture()
        raw["assessments"].append(audit("fresh", "counter", "contradicted", "20"))
        self.assertEqual(credibility.assess(raw)["sources"][0]["estimate"], exact(4, 7))

    def test_rejects_duplicate_reference_future_rows_and_unknown_source(self):
        for bad in (audit("w1", "different", "supported", "19"), audit("future", "x", "supported", "21"),
                    audit("foreign", "x", "supported", "19", source="missing")):
            raw = fixture()
            with self.subTest(bad=bad), self.assertRaises(credibility.CredibilityError):
                credibility.assess({**raw, "assessments": [*raw["assessments"], bad]})

    def test_order_independent_and_cli_matches_python(self):
        raw = fixture()
        target = credibility.assess(raw)
        raw["sources"].reverse()
        raw["assessments"].reverse()
        path = Path(self.enterContext(TemporaryDirectory())) / "judgment.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(credibility.main([str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue()), target)

    def test_sensitivity_identifies_which_audited_claim_moves_estimate(self):
        raw = {**fixture(), "minimum_cases": 1}
        result = credibility.assess(raw)["sources"][0]
        self.assertEqual(result["leave_one_case_out"], {
            "minimum": {"estimate": exact(2, 5), "claim_removed": "support"},
            "maximum": {"estimate": exact(2, 3), "claim_removed": "counter"},
        })

    def test_sensitivity_stays_absent_when_removal_loses_minimum_history(self):
        row = credibility.assess(fixture())["sources"][0]
        self.assertIsNone(row["leave_one_case_out"])
        self.assertEqual(row["status"], "scored")

    def test_minimum_history_cannot_be_set_to_zero(self):
        with self.assertRaises(credibility.CredibilityError):
            credibility.assess({**fixture(), "minimum_cases": 0})

    def test_present_catalog_with_no_checks_reports_unknown_for_each_source(self):
        report = credibility.assess({**fixture(), "assessments": []})
        self.assertTrue(all(row["status"] == "insufficient_history" for row in report["sources"]))
        self.assertTrue(all(row["estimate"] is None for row in report["sources"]))
        self.assertTrue(all(row["claims"] == [] for row in report["sources"]))

    def test_window_boundary_is_inclusive_and_does_not_drift_with_time_zone(self):
        raw = fixture()
        raw["assessments"].append(audit("boundary", "boundary", "supported", "05"))
        raw["as_of"] = "2026-11-20T07:00:00+07:00"
        counted = {row["claim_id"]: row for row in credibility.assess(raw)["sources"][0]["claims"]}
        self.assertEqual(counted["boundary"]["weight"], exact(1, 2))

    def test_other_sources_same_claim_remain_separate_audit_records(self):
        raw = fixture()
        raw["assessments"].append(audit("p", "support", "contradicted", "19", source="other"))
        first, second = credibility.assess(raw)["sources"]
        self.assertEqual(first["estimate"], exact(4, 7))
        self.assertEqual(second["contradiction_weight"], exact(1))

    def test_second_source_can_reach_threshold_without_merging_first_sources_reviews(self):
        raw = fixture()
        raw["assessments"].extend([audit("x", "alpha", "supported", "20", source="other"),
                                   audit("y", "beta", "supported", "20", source="other")])
        self.assertEqual(credibility.assess(raw)["sources"][1]["estimate"], exact(3, 4))
