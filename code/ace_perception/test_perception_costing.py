"""Verifier estimasi unit internal, nol tercatat, dan receipt kurang."""
import unittest

from ace_perception import perception_costing as model


def usage(t, b=8, units=0):
    return {"runtime_us": t, "processed_bytes": b, "input_units": units}


def receipt(ref, **overrides):
    data = {"class": "ocr", "organ": "local", "ref": f"fixture/{ref}", "at": "2026-11-21T00:20:00Z", "usage": usage(2)}
    return {**data, **overrides}


def run(receipts):
    plan = {"schema": "ace.perception-costing-plan.v1", "plan_ref": "fixture/tariffs",
            "from_utc": "2026-11-21T00:00:00Z", "to_utc": "2026-11-21T01:00:00Z",
            "tariffs": [{"class": "ocr", "organ": "local", "ref": "fixture/ocr", "internal_cost_per_unit": usage(1, 2, 3)}]}
    data = {"schema": "ace.perception-cost-receipts.v1", "receipts": receipts}
    return model.report(model._canonical(plan), model._canonical(data), model._sha(plan))["classes"][0]


class CostingTests(unittest.TestCase):
    def test_cost_equals_receipt_sum_when_coverage_complete_in_half_open_window(self):
        report = run([receipt("zero", usage=usage(0, 0)), receipt("charged", usage=usage(2, 8, 6)),
                      receipt("late", at="2026-11-21T01:00:00Z")])
        self.assertEqual(report["within_window"], 2)
        self.assertEqual(report["estimated_receipts"], 2)
        self.assertEqual(report["complete_estimated_units"], 36)
        self.assertEqual([item["estimated_internal_units"] for item in report["rows"]], [36, 0, None])
        self.assertEqual(report["rows"][-1]["status"], "outside_window")

    def test_unpriced_or_missing_is_unknown_not_zero(self):
        report = run([receipt("unknown", organ="unpriced"), receipt("incomplete", usage=usage(None)),
                      receipt("observed")])
        self.assertEqual(report["observed_estimated_units"], 18)
        self.assertIsNone(report["complete_estimated_units"])
        self.assertEqual([row["status"] for row in report["rows"]], ["missing_usage", "estimated", "unpriced"])
