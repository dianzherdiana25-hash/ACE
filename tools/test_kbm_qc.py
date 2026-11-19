"""Pastikan QC menunjukkan bab yang memerlukan perbaikan editorial."""

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.kbm_qc import QC_SCHEMA, audit_manuscript


SCRIPT = Path(__file__).with_name("kbm_qc.py")


class KbmQcTests(unittest.TestCase):
    def setUp(self) -> None:
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.manuscript = self.root / "naskah.md"
        self.config = self.root / "judul.json"
        self.config.write_text(
            json.dumps({"characters": ["Sora"], "name_variants": {"Sorra": "Sora"}}),
            encoding="utf-8",
        )

    def _cli(self, output_format: str, minimum: str = "4") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable, str(SCRIPT), str(self.manuscript),
                "--title-config", str(self.config), "--format", output_format, "--min-words", minimum,
            ],
            capture_output=True, text=True, encoding="utf-8", timeout=10,
        )

    def test_flags_name_and_short_body_in_the_correct_chapters(self) -> None:
        self.manuscript.write_text(
            "# Bab 1: Judul dengan banyak kata\nSora membuka pintu lama.\n"
            "# Bab 2: Penanda\nSorra menutup pintu lama.\n"
            "# Bab 3: Penutup panjang dengan banyak kata\nSora pergi.\n**TAMAT**\n",
            encoding="utf-8",
        )
        proc = self._cli("json")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report["schema"], QC_SCHEMA)
        self.assertFalse(report["valid"])
        self.assertEqual(report["issue_count"], 2)
        first, second, third = report["chapters"]
        self.assertFalse(first["issues"])
        self.assertEqual(second["chapter_number"], 2)
        self.assertEqual(second["issues"], [{
            "code": "character_name_variant", "found": "Sorra", "expected": "Sora", "count": 1,
        }])
        self.assertEqual(third["chapter_number"], 3)
        self.assertEqual(third["word_count"], 2)
        self.assertEqual(third["issues"], [{"code": "chapter_too_short", "min_words": 4}])
        self.assertEqual(third["end_marker_count"], 1)
        self.assertEqual(set(self.root.iterdir()), {self.manuscript, self.config})

        markdown = self._cli("markdown")
        self.assertEqual(markdown.returncode, 1)
        self.assertIn("Bab 2 (posisi 2) — 4 kata. GAGAL.", markdown.stdout)
        self.assertIn("Bab 3 (posisi 3) — 2 kata. GAGAL.", markdown.stdout)

    def test_numbering_duplicate_and_early_end_marker(self) -> None:
        self.manuscript.write_text(
            "# Bab 1\nSora datang.\n## TAMAT\n"
            "# Bab 3\nSora mendengar kata tamat di tengah kalimat.\n"
            "# Bab 3\nSora pulang.\nTAMAT.\n",
            encoding="utf-8",
        )
        report = audit_manuscript(self.manuscript, self.config, min_words=1)
        first, duplicate_before, duplicate_last = report["chapters"]
        self.assertEqual(first["issues"], [{"code": "early_end_marker", "body_lines": [2]}])
        self.assertEqual(duplicate_before["issues"], [
            {"code": "chapter_out_of_sequence", "expected_number": 2},
            {"code": "duplicate_chapter_number"},
        ])
        self.assertEqual(duplicate_last["issues"], [{"code": "duplicate_chapter_number"}])

    def test_unicode_names_are_exact_and_inputs_remain_identical(self) -> None:
        self.config.write_text(
            json.dumps({"characters": ["Éda", "Sora Sini"], "name_variants": {"Sorra": "Sora Sini"}}),
            encoding="utf-8",
        )
        self.manuscript.write_text(
            "# Chapter 1\nE\u0301da bertemu SORA SINI. Sorraya menyapa.\n",
            encoding="utf-8",
        )
        paths = (self.config, self.manuscript)
        before = [path.read_bytes() for path in paths]
        proc = self._cli("json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(proc.stdout)
        self.assertTrue(report["valid"])
        self.assertCountEqual(report["chapters"][0]["characters_seen"], ["Éda", "Sora Sini"])
        self.assertEqual([path.read_bytes() for path in paths], before)
        self.assertEqual(set(self.root.iterdir()), set(paths))

    def test_invalid_title_config_is_a_visible_input_error(self) -> None:
        self.manuscript.write_text("# Bab 1\nSora berjalan.\n", encoding="utf-8")
        self.config.write_text(
            json.dumps({"characters": ["Sora"], "name_variants": {"Sorra": "Nama lain"}}),
            encoding="utf-8",
        )
        proc = self._cli("json", "1")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Target name_variants wajib tercantum", proc.stderr)
        self.assertFalse(proc.stdout)


if __name__ == "__main__":
    unittest.main()
