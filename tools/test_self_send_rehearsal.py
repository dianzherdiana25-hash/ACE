"""Buktikan mock sukses dan gagal dapat diperiksa dari log rehearsal."""
import unittest
from unittest.mock import patch

from tools import self_send_rehearsal


class RehearsalTests(unittest.TestCase):
    def test_prepared_and_sent_pair_audited(self):
        result = self_send_rehearsal.rehearse()
        self.assertTrue(result["remote_is_bare"])
        self.assertEqual(result["envelope"]["mode"], "dry_run")
        self.assertEqual(result["mock_argv"][:3], ["pr", "create", "--draft"])
        self.assertEqual([row["outcome"] for row in result["log"]], ["prepared", "sent"])
        self.assertEqual(result["audit"]["sent"], 1)
        self.assertEqual(result["audit"]["transitions"], [{
            "prepared": {"source": "audit.jsonl", "line": 1},
            "sent": {"source": "audit.jsonl", "line": 2},
        }])
        self.assertEqual(result["audit"]["findings"], [])
        self.assertEqual(result["audit"]["violation_count"], 0)

    def test_failed_mock_leaves_prepared_finding(self):
        with patch.dict("os.environ", {"GH_TOKEN": "fixture-must-not-inherit"}):
            result = self_send_rehearsal.rehearse(fail_mock_gh=True)
        self.assertEqual(result["mock_exit_code"], 1)
        self.assertEqual(result["audit"]["sent"], 0)
        self.assertEqual(result["audit"]["findings"], [
            {"source": "audit.jsonl", "line": 1, "reason": "prepared_without_terminal"},
        ])
        self.assertEqual(result["audit"]["violation_count"], 0)

    def test_batch_rejects_invalid_envelope_before_prepared_or_mock(self):
        result = self_send_rehearsal.rehearse_batch(4)
        first, rejected, third, fourth = result["envelopes"]
        self.assertEqual([item["status"] for item in (first, third, fourth)], ["sent"] * 3)
        self.assertEqual((rejected["branch"], rejected["status"]), ("main", "rejected"))
        self.assertEqual(rejected["envelope"]["checks"]["target_branch"],
                         {"passed": False, "reason": "branch_refused"})
        self.assertNotIn("mock_argv", rejected)
        self.assertEqual([(row["branch"], row["outcome"]) for row in result["log"]], [
            (item["branch"], event) for item in (first, third, fourth) for event in ("prepared", "sent")
        ])
        stamps = [row["ts"] for row in result["log"]]
        self.assertEqual(stamps, sorted(set(stamps)))
        self.assertEqual(result["audit"]["sent"], 3)
        self.assertEqual(result["audit"]["findings"], [])
        self.assertEqual(result["audit"]["violation_count"], 0)
        self.assertEqual(result["audit"]["transitions"], [
            {"prepared": {"source": "audit.jsonl", "line": line},
             "sent": {"source": "audit.jsonl", "line": line + 1}} for line in (1, 3, 5)
        ])

    def test_batch_needs_a_rejected_and_a_valid_envelope(self):
        with self.assertRaises(ValueError):
            self_send_rehearsal.rehearse_batch(1)
