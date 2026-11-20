"""Tes end-to-end arena praktik repo multi-berkas pada mode verify & practice (AG67)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import repo_arena


class RepoArenaEndToEndTest(unittest.TestCase):
    def test_verify_with_patch_passes_all_and_practice_without_patch_shares_shape(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            verify_out = root / "verify.json"
            practice_out = root / "practice.json"

            self.assertEqual(
                repo_arena.main(["--mode", "verify", "--out", str(verify_out)]), 0
            )
            self.assertEqual(
                repo_arena.main(["--mode", "practice", "--out", str(practice_out)]), 0
            )
            rep_verify = json.loads(verify_out.read_text(encoding="utf-8"))
            rep_practice = json.loads(practice_out.read_text(encoding="utf-8"))

        self.assertEqual(rep_verify["schema"], repo_arena.SCHEMA)
        self.assertEqual(set(rep_verify.keys()), set(rep_practice.keys()))
        self.assertEqual(set(rep_verify["summary"].keys()), set(rep_practice["summary"].keys()))
        self.assertEqual(
            set(rep_verify["test_files"][0].keys()),
            set(rep_practice["test_files"][0].keys()),
        )

        # Mode verify (dengan patch referensi): semua berkas tes lulus.
        self.assertEqual(rep_verify["mode"], "verify")
        self.assertTrue(rep_verify["patch_applied"])
        self.assertTrue(rep_verify["all_passed"])
        self.assertEqual(rep_verify["summary"]["passed_files"], 2)
        self.assertEqual(rep_verify["summary"]["failed_files"], 0)
        self.assertEqual(
            {f["file"]: f["status"] for f in rep_verify["test_files"]},
            {"tests/test_dedup.py": "PASS", "tests/test_tax.py": "PASS"},
        )

        # Mode practice (tanpa patch): bentuk identik, test_dedup FAIL dan test_tax PASS.
        self.assertEqual(rep_practice["mode"], "practice")
        self.assertFalse(rep_practice["patch_applied"])
        self.assertFalse(rep_practice["all_passed"])
        self.assertEqual(rep_practice["summary"]["passed_files"], 1)
        self.assertEqual(rep_practice["summary"]["failed_files"], 1)
        self.assertEqual(
            {f["file"]: f["status"] for f in rep_practice["test_files"]},
            {"tests/test_dedup.py": "FAIL", "tests/test_tax.py": "PASS"},
        )


if __name__ == "__main__":
    unittest.main()
