"""Unit & adversarial tests untuk tools/program_glossary.py (I2)."""
from __future__ import annotations

import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest import mock

from tools import program_glossary as pg

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestProgramGlossary(unittest.TestCase):
    def test_01_extracts_markdown_defs_and_ast_without_executing_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            secret = base / "secret.md"
            secret.write_text("- **Leak**: Rahasia", encoding="utf-8")

            repo = base / "repo"
            (repo / "docs").mkdir(parents=True)
            (repo / "tools").mkdir(parents=True)
            os.symlink(secret, repo / "docs" / "sym.md")

            (repo / "docs" / "GLOSSARY_SRC.md").write_text(
                "- **OAIE**: Open Agent Improvement Environment versi riset.\n"
                "- `evo0007`: Evolusi recall pola katalog fase 7.\n"
                "## Gate 4 — Staged Self-Dev\n"
                "Gerbang evaluasi pembaruan diri berbasis sandbox.\n",
                encoding="utf-8",
            )
            (repo / "tools" / "sample_tool.py").write_text(
                '"""Perkakas contoh aman."""\n'
                'TOOL_SCHEMA = "ace.sample.v1"\n'
                "class SampleRunner:\n"
                '    """Menjalankan evaluasi statis fixture."""\n'
                'raise RuntimeError("MUST NOT IMPORT")\n',
                encoding="utf-8",
            )

            with mock.patch.object(socket, "create_connection", side_effect=AssertionError("offline")):
                gl = pg.build_glossary(repo)

            self.assertEqual(gl["schema"], pg.GLOSSARY_SCHEMA)
            self.assertEqual(gl["summary"]["markdown_files_scanned"], 1)
            self.assertEqual(gl["summary"]["python_files_scanned"], 1)

            terms = {(t["term"], t["source_kind"]): t for t in gl["terms"]}
            self.assertIn(("OAIE", "markdown_def"), terms)
            self.assertIn(("evo0007", "markdown_def"), terms)
            self.assertIn(("Gate 4 — Staged Self-Dev", "markdown_heading"), terms)
            self.assertIn(("tools.sample_tool", "ast_module"), terms)
            self.assertIn(("SampleRunner", "ast_class"), terms)
            self.assertIn(("ace.sample.v1", "ast_schema"), terms)

    def test_02_check_fresh_stale_and_error_handling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / "docs").mkdir(parents=True)
            (repo / "docs" / "A.md").write_text("- **Alpha**: Istilah awal sistem.\n", encoding="utf-8")
            out = repo / "docs" / "PROGRAM_GLOSSARY.md"

            self.assertEqual(pg.main(["--root", str(repo), "--output", str(out)]), 0)
            self.assertEqual(pg.main(["--root", str(repo), "--check", str(out)]), 0)

            (repo / "docs" / "B.md").write_text("- **Beta**: Istilah tambahan kedua.\n", encoding="utf-8")
            self.assertEqual(pg.main(["--root", str(repo), "--check", str(out)]), 1)
            self.assertEqual(pg.main(["--root", "/tmp/does_not_exist_ace_gl"]), 2)

    def test_03_live_repo_generated_glossary_fresh_and_cited(self) -> None:
        target = REPO_ROOT / "docs" / "PROGRAM_GLOSSARY.md"
        self.assertTrue(target.is_file(), "docs/PROGRAM_GLOSSARY.md wajib ada dan mutakhir")
        fresh, msg = pg.check_glossary_doc(REPO_ROOT, target)
        self.assertTrue(fresh, msg)

        gl = pg.build_glossary(REPO_ROOT)
        self.assertGreater(gl["summary"]["total_terms_kept"], 100)
        for item in gl["terms"]:
            self.assertTrue((REPO_ROOT / item["path"]).is_file())


if __name__ == "__main__":
    unittest.main()
