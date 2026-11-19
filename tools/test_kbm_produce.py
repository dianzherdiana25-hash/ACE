"""Fixture orkestrator produksi dari bahan lokal hingga ringkasan royalti."""
from __future__ import annotations

import json
from pathlib import Path
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.cover_check import PNG_SIGNATURE
from tools.kbm_produce import PRODUCE_SCHEMA

SCRIPT = Path(__file__).with_name("kbm_produce.py").resolve()


class KbmProduceTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.materials = self.root / "bahan.md"
        self.manuscript = self.root / "naskah.md"
        self.cover = self.root / "cover.png"
        self.bundle = self.root / "paket"
        self.royalty = self.root / "royalti.csv"
        self.materials.write_text(
            "# Bahan\n- Pola: Pembuka dialog\nCatatan bebas\nPola: pembuka  dialog\n",
            encoding="utf-8",
        )
        self.write_chapters([1, 2])
        self.cover.write_bytes(
            PNG_SIGNATURE + struct.pack(">I4sII", 13, b"IHDR", 800, 1200) + b"\0" * 1200
        )
        self.royalty.write_text(
            "serial,date,amount,currency\nFixture,2026-01-05,100.25,IDR\nFixture,2026-01-06,99.75,IDR\n",
            encoding="utf-8",
        )

    def write_chapters(self, numbers):
        self.manuscript.write_text(
            "\n".join(f"# Bab {number}: Judul\nIsi bab dengan lima kata." for number in numbers),
            encoding="utf-8",
        )

    def run_cli(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--materials", str(self.materials),
             "--manuscript", str(self.manuscript), "--cover", str(self.cover),
             "--bundle-dir", str(self.bundle), "--royalty-csv", str(self.royalty),
             "--chapter-count", "2", "--min-words", "5", "--min-bytes", "0"],
            capture_output=True, text=True,
        )
        self.assertIn(proc.returncode, (0, 1), proc.stderr)
        return proc.returncode, json.loads(proc.stdout)

    def test_full_five_stage_run_with_bundle_and_decimal_royalties(self):
        inputs = [self.materials, self.manuscript, self.cover, self.royalty]
        contents_before = {path: path.read_bytes() for path in inputs}
        code, report = self.run_cli()
        self.assertEqual(code, 0)
        self.assertEqual(report["schema"], PRODUCE_SCHEMA)
        self.assertTrue(report["passed"])
        self.assertIsNone(report["failed_stage"])
        stages = report["stages"]
        self.assertEqual(list(stages), ["research", "chapter_check", "cover_check", "package", "royalty"])
        self.assertEqual(stages["research"]["patterns"],
                         [{"label": "Pembuka dialog", "count": 2, "lines": [2, 4]}])
        self.assertEqual([ch["word_count"] for ch in stages["chapter_check"]["chapters"]], [5, 5])
        manifest_path = Path(stages["package"]["manifest_file"])
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["chapter_count"], 2)
        self.assertEqual(manifest["total_words"], 10)
        self.assertEqual(stages["royalty"]["totals_by_currency"], {"IDR": "200.00"})
        self.assertEqual({path: path.read_bytes() for path in inputs}, contents_before)
        self.assertEqual(set(self.root.iterdir()), {*inputs, self.bundle})

    def test_invalid_cover_stops_before_package_and_royalties(self):
        self.cover.write_bytes(b"cover has no PNG header")
        self.royalty.unlink()
        code, report = self.run_cli()
        self.assertEqual(code, 1)
        self.assertFalse(report["passed"])
        self.assertEqual(report["failed_stage"], "cover_check")
        self.assertEqual(list(report["stages"]), ["research", "chapter_check", "cover_check"])
        self.assertFalse(self.bundle.exists())

    def test_source_chapter_order_is_checked_before_cover(self):
        self.write_chapters([2, 1])
        code, report = self.run_cli()
        self.assertEqual(code, 1)
        self.assertEqual(report["failed_stage"], "chapter_check")
        self.assertFalse(report["stages"]["chapter_check"]["sequence_ok"])
        self.assertNotIn("cover_check", report["stages"])
        self.assertFalse(self.bundle.exists())

    def test_existing_bundle_is_preserved(self):
        self.bundle.mkdir()
        existing = self.bundle / "upload_manifest.json"
        existing.write_text("existing\n", encoding="utf-8")
        code, report = self.run_cli()
        self.assertEqual(code, 1)
        self.assertEqual(report["failed_stage"], "package")
        self.assertEqual(existing.read_text(), "existing\n")
        self.assertNotIn("royalty", report["stages"])

    def test_invalid_royalty_rows_fail_with_source_line_and_keep_staged_bundle(self):
        self.royalty.write_text("serial,date,amount\nFixture,2026-01-05,invalid\n", encoding="utf-8")
        code, report = self.run_cli()
        self.assertEqual(code, 1)
        self.assertEqual(report["failed_stage"], "royalty")
        royalty = report["stages"]["royalty"]
        self.assertFalse(royalty["valid"])
        self.assertEqual(royalty["invalid_locations"], [{"file": str(self.royalty), "line": 2}])
        self.assertEqual(royalty["totals_by_currency"], {})
        self.assertTrue((self.bundle / "upload_manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
