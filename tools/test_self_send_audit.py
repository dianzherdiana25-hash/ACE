"""Uji hitungan kirim dan rujukan baris pelanggaran."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.self_send_audit import audit, markdown


ROW = {"ts": "2026-11-20T10:00:00+00:00", "branch": "ace-auto/20261120-fixture",
       "trigger": "fixture", "content_digest": "a" * 64, "files": [], "outcome": "sent"}


class SelfSendAuditTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(self.enterContext(TemporaryDirectory())) / "audit.jsonl"

    def write(self, *rows):
        self.path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    def test_clean_log_counts_only_sent(self):
        self.write({**ROW, "outcome": "prepared"}, ROW)
        result = audit(self.path)
        self.assertEqual(result["violation_count"], 0)
        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["by_day_and_target"], {"2026-11-20": {ROW["branch"]: 1}})

    def test_main_and_authority_violation_cite_line(self):
        self.write(ROW, {**ROW, "outcome": "sent", "branch": "main", "merge_authority": True})
        result = audit(self.path)
        self.assertEqual(result["violations"], [{"line": 2, "reason": "merge_authority_not_absent"},
                                               {"line": 2, "reason": "target_branch_refused"}])
        self.assertIn("Baris 2", markdown(result))


if __name__ == "__main__":
    unittest.main()
