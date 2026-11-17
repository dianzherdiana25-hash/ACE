"""Uji unit untuk skrip pembangkit indeks docs/REPO_INDEX.md dan tools/refresh_repo_index.sh."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.repo_index import INDEX_SCHEMA

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_DOC = REPO_ROOT / "docs" / "REPO_INDEX.md"
REFRESH_SCRIPT = REPO_ROOT / "tools" / "refresh_repo_index.sh"
INDEX_TOOL = REPO_ROOT / "tools" / "repo_index.py"


class RepoIndexDocTests(unittest.TestCase):
    """Memastikan docs/REPO_INDEX.md dan tools/refresh_repo_index.sh valid dan deterministik."""

    def test_refresh_script_exists_and_is_executable(self) -> None:
        self.assertTrue(REFRESH_SCRIPT.is_file(), "tools/refresh_repo_index.sh harus ada")
        self.assertTrue(os.access(REFRESH_SCRIPT, os.X_OK), "tools/refresh_repo_index.sh harus executable")

    def test_generated_doc_contains_expected_sections_and_tools(self) -> None:
        self.assertTrue(INDEX_DOC.is_file(), "docs/REPO_INDEX.md harus ada")
        content = INDEX_DOC.read_text(encoding="utf-8")
        self.assertIn("# Indeks Repositori", content)
        self.assertIn(f"`{INDEX_SCHEMA}`", content)
        self.assertIn("## Daftar Berkas per Direktori", content)
        self.assertIn("## Peta Modul Python", content)
        self.assertIn("`tools/repo_index.py`", content)
        self.assertIn("`refresh_repo_index.sh`", content)

    def test_refresh_script_runs_deterministically_on_isolated_repo_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_repo = Path(tmp) / "ACE"
            (fake_repo / "tools").mkdir(parents=True)
            shutil.copy2(INDEX_TOOL, fake_repo / "tools" / "repo_index.py")
            shutil.copy2(REFRESH_SCRIPT, fake_repo / "tools" / "refresh_repo_index.sh")
            (fake_repo / "pkg").mkdir()
            (fake_repo / "pkg" / "mod.py").write_text('"""Contoh modul."""\n', encoding="utf-8")

            script_copy = fake_repo / "tools" / "refresh_repo_index.sh"
            doc_copy = fake_repo / "docs" / "REPO_INDEX.md"

            p1 = subprocess.run(["bash", str(script_copy)], capture_output=True, text=True)
            self.assertEqual(p1.returncode, 0, p1.stderr)
            self.assertTrue(doc_copy.is_file())
            first_bytes = doc_copy.read_bytes()

            p2 = subprocess.run(["bash", str(script_copy)], capture_output=True, text=True)
            self.assertEqual(p2.returncode, 0, p2.stderr)
            second_bytes = doc_copy.read_bytes()

            # Jalankan ketiga kali untuk memverifikasi idempotensi setelah docs/REPO_INDEX.md ada.
            p3 = subprocess.run(["bash", str(script_copy)], capture_output=True, text=True)
            self.assertEqual(p3.returncode, 0, p3.stderr)
            third_bytes = doc_copy.read_bytes()

            self.assertEqual(second_bytes, third_bytes)
            self.assertIn(b"REPO_INDEX.md", second_bytes)
            self.assertNotEqual(len(first_bytes), 0)


if __name__ == "__main__":
    unittest.main()
