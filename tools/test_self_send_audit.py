"""Uji hitungan kirim dan rujukan baris pelanggaran."""
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.self_send_audit import audit, main, markdown


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

    def test_mixed_plain_and_gzip_shards_match_uncompressed_numbers(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            plain_dir = root / "plain"
            mixed_dir = root / "mixed"
            plain_dir.mkdir()
            mixed_dir.mkdir()
            shard_a = json.dumps({**ROW, "outcome": "prepared"}) + "\n"
            shard_b = json.dumps({**ROW, "outcome": "sent"}) + "\n"
            (plain_dir / "01.jsonl").write_text(shard_a, encoding="utf-8")
            (plain_dir / "02.jsonl").write_text(shard_b, encoding="utf-8")

            (mixed_dir / "01.jsonl").write_text(shard_a, encoding="utf-8")
            (mixed_dir / "02.jsonl.gz").write_bytes(gzip.compress(shard_b.encode("utf-8")))

            r_plain = audit(plain_dir)
            r_mixed = audit(mixed_dir)
            self.assertEqual(r_mixed["sent"], r_plain["sent"])
            self.assertEqual(r_mixed["by_day_and_target"], r_plain["by_day_and_target"])
            self.assertEqual(r_mixed["violation_count"], r_plain["violation_count"])
            self.assertEqual(len(r_mixed["transitions"]), len(r_plain["transitions"]))
            self.assertEqual(r_mixed["findings"], r_plain["findings"])

    def test_corrupt_gzip_shard_reported_as_finding_not_crash(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "01.jsonl").write_text(json.dumps(ROW) + "\n", encoding="utf-8")
            corrupt = root / "02-corrupt.jsonl.gz"
            corrupt.write_bytes(b"bukan-gzip-sama-sekali")

            report = audit(root)
            self.assertEqual(report["sent"], 1)
            self.assertEqual(report["violation_count"], 1)
            self.assertEqual(report["violations"], [{"line": 0, "reason": "corrupt_gzip_shard"}])
            self.assertIn(
                {"source": str(corrupt), "line": 0, "reason": "corrupt_gzip_shard"},
                report["findings"],
            )
            self.assertEqual(main([str(corrupt)]), 1)


if __name__ == "__main__":
    unittest.main()
