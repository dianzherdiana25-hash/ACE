import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.kbm_pack_check import KbmPackCheckError, check_package
from tools.test_cover_check import _make_png


class CoverWiringTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "bab_001.md").write_text("Synthetic chapter.", encoding="utf-8")

    def test_cli_strict_mode_rejects_small_dimensions(self):
        (self.root / "cover.png").write_bytes(_make_png(100, 150))
        script = Path(__file__).with_name("kbm_pack_check.py")
        result = subprocess.run(
            [sys.executable, str(script), str(self.root), "--min-bytes", "1", "--strict-cover"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(result.stdout)
        self.assertIn("min_width", report["cover"]["validation"]["failed_rules"])
        self.assertTrue(check_package(self.root, min_bytes=1)["valid"])

    def test_valid_cover_delegates_to_dimension_validator(self):
        (self.root / "cover.png").write_bytes(_make_png(800, 1200))
        report = check_package(self.root, min_bytes=1, strict_cover=True)
        self.assertTrue(report["valid"])
        self.assertEqual(report["cover"]["validation"]["decoded"]["width"], 800)

    def test_strict_mode_rejects_external_cover_path(self):
        with self.assertRaises(KbmPackCheckError):
            check_package(self.root, cover_name="../cover.png", strict_cover=True)
