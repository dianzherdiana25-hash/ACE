"""Tes mode --receipt-format director_fold serta re-parse oleh receipt_chain_verify (AG72)."""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import director_fold, receipt_chain_verify
from tools.test_director_fold import triage_fixture


class DirectorFoldReceiptFormatTest(unittest.TestCase):
    def test_receipt_format_emits_one_jsonl_line_per_group_and_passes_receipt_chain_verify(self) -> None:
        proposals = triage_fixture()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            prop_path = root / "proposals.jsonl"
            receipts_path = root / "fold_receipts.jsonl"
            prop_path.write_text(
                "\n".join(json.dumps(row) for row in proposals) + "\n",
                encoding="utf-8",
            )
            before_bytes = prop_path.read_bytes()

            buf = StringIO()
            with redirect_stdout(buf):
                rc = director_fold.main(
                    [
                        str(prop_path),
                        "--receipt-format",
                        "--receipt-at",
                        "2026-11-20T12:00:00+00:00",
                    ]
                )
            self.assertEqual(rc, 0)
            # Pastikan ekspor proposal tidak diubah statusnya sama sekali.
            self.assertEqual(prop_path.read_bytes(), before_bytes)

            jsonl_text = buf.getvalue()
            receipts_path.write_text(jsonl_text, encoding="utf-8")
            lines = [json.loads(ln) for ln in jsonl_text.splitlines() if ln.strip()]

            expected_plan = director_fold.fold_proposals(proposals)
            self.assertEqual(len(lines), len(expected_plan["groups"]))
            for row, group in zip(lines, expected_plan["groups"]):
                self.assertEqual(row["task_id"], group["representative"])
                self.assertEqual(row["representative"], group["representative"])
                self.assertEqual(row["duplicates"], group["duplicates"])
                self.assertTrue(row["reason"])
                self.assertTrue(row["dry_run_plan_only"])

            # Output harus terparse bersih oleh receipt_chain_verify (AG53) tanpa temuan rusak!
            verify_rc = receipt_chain_verify.main(["--receipts", str(receipts_path)])
            self.assertEqual(verify_rc, 0)
            verify_rep = receipt_chain_verify.verify_receipts_file(receipts_path)
            self.assertTrue(verify_rep["valid_sequence"])
            self.assertEqual(verify_rep["findings"], [])
            self.assertEqual(verify_rep["summary"]["started_count"], len(lines))


if __name__ == "__main__":
    unittest.main()
