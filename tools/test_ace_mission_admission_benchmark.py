"""Smoke test tingkat-dasar untuk tools/ace_mission_admission_benchmark.py (batch AG24)."""
from __future__ import annotations

from contextlib import redirect_stdout
import gzip
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import ace_mission_admission_benchmark as benchmark


SCRIPT = Path(__file__).resolve().with_name("ace_mission_admission_benchmark.py")


class AceMissionAdmissionBenchmarkSmokeTests(unittest.TestCase):
    def test_import_and_cli_help_exit_zero(self) -> None:
        self.assertTrue(callable(benchmark.main))
        self.assertTrue(callable(benchmark.run))
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--raw-receipts", proc.stdout)

    def test_core_single_rule_seed_fixture_writes_report_profile_and_receipts(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_json = root / "report.json"
            profile_json = root / "profile.json"
            receipts_gz = root / "receipts.json.gz"

            with patch.object(benchmark, "RULES", benchmark.RULES[:1]), \
                    patch.object(benchmark, "SEEDS", benchmark.SEEDS[:1]), \
                    patch.object(
                        sys,
                        "argv",
                        [
                            str(SCRIPT),
                            "--output", str(out_json),
                            "--profile", str(profile_json),
                            "--raw-receipts", str(receipts_gz),
                        ],
                    ), \
                    redirect_stdout(StringIO()):
                benchmark.main()

            report = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(report["schema"], "ace.mission.admission.public.v1")
            self.assertEqual(report["summary"]["tasks"], 1)
            self.assertEqual(len(report["cells"]), 1)

            profile = json.loads(profile_json.read_text(encoding="utf-8"))
            self.assertIn("raw_receipts_sha256", profile)
            raw_receipts = json.loads(gzip.decompress(receipts_gz.read_bytes()).decode("utf-8"))
            self.assertEqual(len(raw_receipts), 1)


if __name__ == "__main__":
    unittest.main()
