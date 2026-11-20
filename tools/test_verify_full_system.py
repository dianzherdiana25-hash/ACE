"""Smoke test tingkat-dasar untuk tools/verify_full_system.py (batch AG24)."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools import verify_full_system


SCRIPT = Path(__file__).resolve().with_name("verify_full_system.py")


class VerifyFullSystemSmokeTests(unittest.TestCase):
    def test_import_and_cli_help_exit_zero(self) -> None:
        self.assertTrue(callable(verify_full_system.main))
        self.assertTrue(callable(verify_full_system.run_test_module))
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--group", proc.stdout)

    def test_core_run_test_module_and_sha256_on_fixture(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = root / "sample.bin"
            sample.write_bytes(b"ace-verify-fixture")
            self.assertEqual(
                verify_full_system._sha256(sample),
                hashlib.sha256(b"ace-verify-fixture").hexdigest(),
            )

            mod_file = root / "temp_smoke_unittest_mod.py"
            mod_file.write_text(
                "import unittest\n"
                "class SmokeFixtureTest(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        self.assertEqual(1 + 1, 2)\n",
                encoding="utf-8",
            )
            sys.path.insert(0, str(root))
            try:
                res = verify_full_system.run_test_module("temp_smoke_unittest_mod")
            finally:
                sys.path.remove(str(root))
                sys.modules.pop("temp_smoke_unittest_mod", None)

            self.assertTrue(res["success"])
            self.assertEqual((res["tests"], res["errors"], res["failures"]), (1, 0, 0))


if __name__ == "__main__":
    unittest.main()
