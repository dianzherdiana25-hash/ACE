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
