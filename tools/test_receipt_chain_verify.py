"""Tes regresi fixture-only untuk tools.receipt_chain_verify (AG53)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools import receipt_chain_verify


class ReceiptChainVerifyTest(unittest.TestCase):
    def test_clean_torn_tail_corrupt_middle_and_terminal_without_started(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            # 1. Clean: dua pasangan started -> completed/failed utuh berakhiran newline.
            clean_path = root / "clean.jsonl"
            clean_path.write_text(
                "\n".join(
                    [
                        json.dumps({"task_id": "t1", "status": "started", "at": "2026-11-20T01:00:00+00:00"}),
                        json.dumps({"task_id": "t1", "status": "completed", "at": "2026-11-20T01:01:00+00:00"}),
                        json.dumps({"task_id": "t2", "status": "started", "at": "2026-11-20T02:00:00+00:00"}),
                        json.dumps({"task_id": "t2", "status": "failed", "at": "2026-11-20T02:01:00+00:00"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            rep_clean = receipt_chain_verify.verify_receipts_file(clean_path)
            self.assertEqual(rep_clean["schema"], receipt_chain_verify.SCHEMA)
            self.assertEqual(rep_clean["status"], "clean")
            self.assertTrue(rep_clean["valid_sequence"])
            self.assertFalse(rep_clean["torn_tail"])
            self.assertEqual(rep_clean["summary"]["complete_pair_count"], 2)
            self.assertEqual(rep_clean["findings"], [])

            # 2. Torn tail: baris terakhir JSON terpotong tanpa newline penutup -> ditoleransi sebagai torn_tail_pending.
            torn_path = root / "torn.jsonl"
            torn_path.write_text(
                json.dumps({"task_id": "t1", "status": "started", "at": "2026-11-20T01:00:00+00:00"})
                + "\n"
                + json.dumps({"task_id": "t1", "status": "completed", "at": "2026-11-20T01:01:00+00:00"})
                + "\n"
                + '{"task_id": "t2", "status": "star',
                encoding="utf-8",
            )
            rep_torn = receipt_chain_verify.verify_receipts_file(torn_path)
            self.assertEqual(rep_torn["status"], "torn_tail_pending")
            self.assertTrue(rep_torn["valid_sequence"])
            self.assertTrue(rep_torn["torn_tail"])
            self.assertIn(receipt_chain_verify.TORN_SENTINEL, rep_torn["pending_tasks"])
            self.assertEqual(rep_torn["summary"]["complete_pair_count"], 1)
            self.assertEqual(rep_torn["findings"], [])

            # 3. Corrupt middle line: JSON rusak pada baris non-terakhir -> temuan corrupt_middle_line, exit code 1.
            mid_path = root / "corrupt_mid.jsonl"
            out_path = root / "out.json"
            mid_path.write_text(
                json.dumps({"task_id": "t1", "status": "started", "at": "2026-11-20T01:00:00+00:00"})
                + "\n"
                + "{bad json in middle\n"
                + json.dumps({"task_id": "t1", "status": "completed", "at": "2026-11-20T01:01:00+00:00"})
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(
                receipt_chain_verify.main(["--receipts", str(mid_path), "--out", str(out_path)]),
                1,
            )
            rep_mid = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(rep_mid["status"], "corrupt")
            self.assertFalse(rep_mid["valid_sequence"])
            self.assertEqual(rep_mid["summary"]["finding_codes"], ["corrupt_middle_line"])
            self.assertEqual(rep_mid["findings"][0]["line"], 2)

            # 4. Completed without started -> temuan terminal_without_started, exit code 1.
            orphan_term_path = root / "completed_no_start.jsonl"
            orphan_term_path.write_text(
                json.dumps({"task_id": "t-ghost", "status": "completed", "at": "2026-11-20T03:00:00+00:00"})
                + "\n",
                encoding="utf-8",
            )
            rep_orphan = receipt_chain_verify.verify_receipts_file(orphan_term_path)
            self.assertEqual(rep_orphan["status"], "corrupt")
            self.assertFalse(rep_orphan["valid_sequence"])
            self.assertEqual(rep_orphan["summary"]["finding_codes"], ["terminal_without_started"])
            self.assertEqual(rep_orphan["findings"][0]["task_id"], "t-ghost")


if __name__ == "__main__":
    unittest.main()
