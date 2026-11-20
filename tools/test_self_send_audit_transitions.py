"""Kunci hari kirim UTC dan penunjuk sumber transisi log."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.self_send_audit import audit, markdown


class TransitionTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(self.enterContext(TemporaryDirectory())) / "log.jsonl"
        self.branch = "ace-auto/20261119-fixture"

    def write_rows(self, *events):
        rows = [
            {"ts": stamp, "branch": self.branch, "outcome": outcome, "trigger": "fixture",
             "content_digest": digest} for stamp, outcome, digest in events
        ]
        self.path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def test_prepared_before_midnight_only_counts_sent_day_utc(self):
        self.write_rows(("2026-11-19T23:58:00+00:00", "prepared", "x"),
                        ("2026-11-20T07:02:00+07:00", "sent", "x"))
        report = audit(self.path)
        self.assertEqual(report["by_day_and_target"], {"2026-11-20": {self.branch: 1}})
        self.assertEqual(report["transitions"], [{
            "prepared": {"source": str(self.path), "line": 1},
            "sent": {"source": str(self.path), "line": 2},
        }])
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["violation_count"], 0)

    def test_sent_for_another_digest_is_a_finding_not_envelope_violation(self):
        self.write_rows(("2026-11-19T23:58:00+00:00", "prepared", "unrelated"),
                        ("2026-11-20T00:02:00+00:00", "sent", "orphan"))
        report = audit(self.path)
        self.assertEqual(report["transitions"], [])
        self.assertEqual(report["findings"], [{
            "source": str(self.path), "line": 2, "reason": "sent_without_prepared",
        }])
        self.assertEqual(report["violation_count"], 0)
        self.assertIn("Baris 2 · sent_without_prepared", markdown(report))


if __name__ == "__main__":
    unittest.main()
