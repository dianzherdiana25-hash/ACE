"""Uji unit untuk generator indeks repo otomatis tools/repo_index.py."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.repo_index import build_repo_index, render_markdown_index

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "repo_index.py"


class RepoIndexTests(unittest.TestCase):
    """Menguji determinisme keluaran serta ekstraksi docstring dan dependensi internal."""

    def test_deterministic_markdown_and_module_map_on_tree_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "sample_repo"
            (root / "docs").mkdir(parents=True)
            (root / "tools").mkdir(parents=True)
            (root / "code" / "pkg").mkdir(parents=True)
            (root / "__pycache__").mkdir(parents=True)

            (root / "README.md").write_text("# Sample\n", encoding="utf-8")
            (root / "docs" / "notes.json").write_text("{}\n", encoding="utf-8")
            (root / "__pycache__" / "junk.pyc").write_bytes(b"pyc")

            (root / "tools" / "__init__.py").write_text("", encoding="utf-8")
            (root / "tools" / "helper.py").write_text(
                '"""Pembantu pemrosesan data.\n\nDetail lanjutan.\n"""\nimport json\n',
                encoding="utf-8",
            )
            (root / "tools" / "runner.py").write_text(
                '"""Penggerak utama."""\nimport sys\nfrom tools import helper\nfrom pkg import core\n',
                encoding="utf-8",
            )
            (root / "code" / "pkg" / "__init__.py").write_text('"""Paket inti."""\n', encoding="utf-8")
            (root / "code" / "pkg" / "core.py").write_text(
                '"""Logika inti domain."""\nfrom .util import fmt\n',
                encoding="utf-8",
            )
            (root / "code" / "pkg" / "util.py").write_text(
                '"""Utilitas pemformatan."""\n',
                encoding="utf-8",
            )

            idx1 = build_repo_index(root)
            idx2 = build_repo_index(root)
            self.assertEqual(idx1, idx2)

            md1 = render_markdown_index(idx1)
            md2 = render_markdown_index(idx2)
            self.assertEqual(md1, md2)

            # __pycache__ tidak boleh terindeks
            self.assertNotIn("__pycache__", md1)
            self.assertEqual(idx1["file_count"], 8)
            self.assertEqual(idx1["module_count"], 6)

            by_mod = {m["module"]: m for m in idx1["python_modules"]}
            self.assertEqual(by_mod["tools.helper"]["docstring"], "Pembantu pemrosesan data.")
            self.assertEqual(by_mod["tools.helper"]["internal_deps"], [])
            self.assertEqual(by_mod["tools.runner"]["internal_deps"], ["pkg.core", "tools.helper"])
            self.assertEqual(by_mod["pkg.core"]["internal_deps"], ["pkg.util"])

            self.assertIn("| `tools.runner` | `tools/runner.py` | Penggerak utama. | `pkg.core`, `tools.helper` |", md1)

    def test_cli_json_and_invalid_root_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "tiny"
            root.mkdir()
            (root / "a.py").write_text('"""Satu."""\n', encoding="utf-8")
            out_md = Path(tmp) / "INDEX.md"
            p_md = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(root), "--output", str(out_md)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(p_md.returncode, 0, p_md.stderr)
            self.assertIn("# Indeks Repositori — tiny", out_md.read_text(encoding="utf-8"))

            p_json = subprocess.run(
                [sys.executable, str(SCRIPT), "--root", str(root), "--format", "json"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(p_json.returncode, 0, p_json.stderr)
            self.assertEqual(json.loads(p_json.stdout)["module_count"], 1)

        p_bad = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", "/tmp/tidak_ada_repo_idx"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(p_bad.returncode, 2)
        self.assertIn("Error:", p_bad.stderr)


if __name__ == "__main__":
    unittest.main()
