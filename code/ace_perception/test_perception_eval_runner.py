"""Verifier kalender benchmark, delta, dan celah bukti antarjendela."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_perception import perception_eval_runner as model
from ace_perception.test_perception_bench import bytes_observations, q, raw_plan


class EvalSeriesTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.protocol = raw_plan()
        self.series = {"schema": "ace.perception-eval-series.v1", "series_ref": "fixture/monthly",
                       "first_window_at": "2026-11-01T00:00:00Z", "as_of": "2026-11-23T00:00:00Z",
                       "period_days": 7, "windows": 4, "protocol_sha256": model._sha(self.protocol),
                       "document_min_bp": 8500, "table_min_bp": 8000, "rounds": []}

    def save(self, name, stamp, payload):
        (self.root/name).write_bytes(payload)
        self.series["rounds"].append({"source_ref": f"fixture/{name}", "at": stamp, "path": name,
                                      "sha256": sha256(payload).hexdigest(), "bytes": len(payload)})

    def run_series(self):
        return model.evaluate(self.root, model._canonical(self.protocol), model._canonical(self.series), model._sha(self.series))

    def test_thresholds_boundaries_regression_overdue_and_pending(self):
        self.save("good.json", "2026-11-02T00:00:00Z", bytes_observations(audio="hello the white cat"))
        self.save("worse.json", "2026-11-08T07:00:00+07:00", bytes_observations(
            doc={"first": "Alpha"}, table=[[1, 2]], audio="hello the white"))
        first, second, third, fourth = self.run_series()["windows"]
        self.assertEqual([row["status"] for row in (first, second, third, fourth)],
                         ["thresholds_met", "below_threshold", "overdue", "pending"])
        self.assertEqual(second["rates"], {"document": q(1, 3), "table": q(1, 2), "asr": q(1, 4)})
        self.assertEqual(second["delta_since_previous"], {"document": q(-2, 3), "table": q(-1, 2), "asr": q(1, 4)})
        self.assertEqual(second["below_threshold"], ["document", "table"])
        self.assertEqual(second["receipt_ref"], "fixture/worse.json")
        self.assertIsNone(third["rates"])
        self.assertEqual(fourth["starts_at"], "2026-11-22T00:00:00+00:00")

    def test_tampered_source_keeps_failure_and_later_valid_round_can_report(self):
        self.save("changed.json", "2026-11-03T00:00:00Z", bytes_observations())
        self.save("good.json", "2026-11-08T00:00:00Z", bytes_observations())
        (self.root/"changed.json").write_bytes(b"bad")
        first, second, *_ = self.run_series()["windows"]
        self.assertEqual(first["status"], "invalid_receipt")
        self.assertEqual(first["expected_receipts_sha256"], self.series["rounds"][0]["sha256"])
        self.assertEqual(second["status"], "thresholds_met")
        self.assertEqual(second["delta_since_previous"], {"document": None, "table": None, "asr": None})

    def test_future_or_duplicate_round_rejected_and_protocol_stable(self):
        self.save("one.json", "2026-11-08T01:00:00Z", bytes_observations())
        self.save("two.json", "2026-11-08T03:00:00Z", bytes_observations())
        with self.assertRaisesRegex(ValueError, "Putaran ganda"):
            self.run_series()
        self.series["rounds"].pop()
        self.protocol["protocol_ref"] = "fixture/changed"
        with self.assertRaisesRegex(ValueError, "held-out"):
            self.run_series()
