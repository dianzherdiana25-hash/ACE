"""Unit & adversarial tests untuk tools/wiring_audit.py."""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools import wiring_audit as wa


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestWiringAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir(parents=True, exist_ok=True)

    def _seed_repo(self) -> None:
        _write(self.root / "ace.py", "from code.pkg_ok.wired_lib import run\n\nif __name__ == '__main__':\n    run()\n")
        _write(self.root / "tools" / "__init__.py", "")
        _write(self.root / "tools" / "cli_only.py", "def act():\n    return 1\n\nif __name__ == '__main__':\n    act()\n")
        _write(self.root / "tools" / "test_cli_only.py", "from tools import cli_only\n")
        _write(self.root / "tools" / "corpus_lint.py", "def lint_file():\n    return {}\n")
        _write(self.root / "code" / "pkg_ok" / "__init__.py", "")
        _write(self.root / "code" / "pkg_ok" / "wired_lib.py", "def run():\n    return 0\n")
        _write(self.root / "code" / "pkg_ok" / "orphan_mod.py", "def unused():\n    return 42\n")
        _write(self.root / "code" / "pkg_ok" / "test_orphan_mod.py", "from pkg_ok.orphan_mod import unused\n")
        # Modul wilayah terlarang dengan bom impor harus aman tidak pernah dieksekusi
        _write(self.root / "code" / "ace_operational" / "evo0007_run.py", "raise RuntimeError('MUST_NOT_EXECUTE')\n")
        _write(self.root / "tools" / "memory_writeback.py", "def wb():\n    return 1\n")

    def test_01_classifies_wired_cli_standalone_orphan_and_menunggu_engineer_utama(self):
        self._seed_repo()
        rep = wa.audit_wiring(self.root)
        by_path = {m["path"]: m for m in rep["modules"]}

        self.assertEqual(by_path["code/pkg_ok/wired_lib.py"]["status"], "WIRED")
        self.assertEqual(by_path["code/pkg_ok/wired_lib.py"]["non_test_callers"], ["ace.py"])

        # orphan_mod hanya diimpor oleh test_orphan_mod, bukan caller non-test -> tetap ORPHAN!
        self.assertEqual(by_path["code/pkg_ok/orphan_mod.py"]["status"], "ORPHAN")
        self.assertEqual(by_path["code/pkg_ok/orphan_mod.py"]["test_caller_count"], 1)
        self.assertEqual(by_path["code/pkg_ok/orphan_mod.py"]["non_test_caller_count"], 0)

        self.assertEqual(by_path["tools/cli_only.py"]["status"], "CLI_STANDALONE")
        self.assertTrue(by_path["tools/cli_only.py"]["has_main_guard"])

        for waiting_path in (
            "code/ace_operational/evo0007_run.py",
            "tools/memory_writeback.py",
            "tools/corpus_lint.py",
        ):
            self.assertEqual(by_path[waiting_path]["status"], "MENUNGGU_ENGINEER_UTAMA", waiting_path)

    def test_02_relative_imports_count_as_wired(self):
        _write(self.root / "code" / "pkg" / "__init__.py", "")
        _write(self.root / "code" / "pkg" / "helper.py", "def h():\n    return 1\n")
        _write(self.root / "code" / "pkg" / "caller.py", "from .helper import h\nif __name__ == '__main__':\n    h()\n")

        rep = wa.audit_wiring(self.root)
        by_path = {m["path"]: m for m in rep["modules"]}
        self.assertEqual(by_path["code/pkg/helper.py"]["status"], "WIRED")
        self.assertEqual(by_path["code/pkg/helper.py"]["non_test_callers"], ["code/pkg/caller.py"])

    def test_03_skips_symlinks_and_handles_syntax_errors_gracefully(self):
        _write(self.root / "tools" / "bad_syntax.py", "def broken(:\n    pass\n")
        outside = Path(self.tmp.name) / "outside.py"
        _write(outside, "def ext():\n    return 1\n")
        (self.root / "tools").mkdir(parents=True, exist_ok=True)
        os.symlink(outside, self.root / "tools" / "sym.py")

        rep = wa.audit_wiring(self.root)
        paths = {m["path"] for m in rep["modules"]}
        self.assertIn("tools/bad_syntax.py", paths)
        self.assertNotIn("tools/sym.py", paths)
        bad = next(m for m in rep["modules"] if m["path"] == "tools/bad_syntax.py")
        self.assertIsNotNone(bad["parse_error"])

    def test_04_cli_markdown_json_and_error_handling(self):
        self._seed_repo()
        md_path = self.root / "audit.md"
        rc = wa.main(["--root", str(self.root), "--format", "markdown", "--output", str(md_path)])
        self.assertEqual(rc, 0)
        text = md_path.read_text(encoding="utf-8")
        self.assertIn("MENUNGGU_ENGINEER_UTAMA", text)
        self.assertIn("code/pkg_ok/orphan_mod.py", text)

        out_buf = io.StringIO()
        with contextlib.redirect_stdout(out_buf):
            rc2 = wa.main(["--root", str(self.root), "--format", "json"])
        self.assertEqual(rc2, 0)
        self.assertEqual(json.loads(out_buf.getvalue())["schema"], wa.WIRING_SCHEMA)

        err_buf = io.StringIO()
        with contextlib.redirect_stderr(err_buf):
            rc_err = wa.main(["--root", str(self.root / "missing_dir")])
        self.assertEqual(rc_err, 1)


if __name__ == "__main__":
    unittest.main()
