#!/usr/bin/env python3
"""Unit tests untuk tools/storage_debt.py (WS-E #14)."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.storage_debt import STORAGE_DEBT_SCHEMA, StorageDebtError, main, scan_storage_debt


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    )


class TestStorageDebt(unittest.TestCase):
    def test_detects_untracked_and_modified_grouped_by_program(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir) / "ws"
            repo.mkdir()
            _git(repo, "init")
            _git(repo, "config", "user.name", "Test")
            _git(repo, "config", "user.email", "test@example.com")

            (repo / "tools").mkdir()
            (repo / "tools" / "clean.py").write_text("x = 1\n", encoding="utf-8")
            (repo / "tools" / "dirty.py").write_text("y = 1\n", encoding="utf-8")
            _git(repo, "add", ".")
            _git(repo, "commit", "-m", "init")

            # Modifikasi tracked file + tambah untracked di area berbeda.
            (repo / "tools" / "dirty.py").write_text("y = 999\n", encoding="utf-8")
            (repo / "kbm").mkdir()
            (repo / "kbm" / "bab1.md").write_text("Bab satu\n", encoding="utf-8")
            (repo / "code" / "ace_demo").mkdir(parents=True)
            (repo / "code" / "ace_demo" / "scratch.py").write_text("z = 0\n", encoding="utf-8")

            out_json = Path(tmpdir) / "debt.json"
            rc = main(["--workspace", str(repo), "--out", str(out_json)])
            self.assertEqual(rc, 0)
            rep = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(rep["schema"], STORAGE_DEBT_SCHEMA)
            self.assertEqual(rep["summary"]["tracked_clean_count"], 1)
            self.assertEqual(rep["summary"]["modified_count"], 1)
            self.assertEqual(rep["summary"]["untracked_count"], 2)
            self.assertEqual(rep["summary"]["total_debt_files"], 3)
            self.assertIn("tools", rep["programs"])
            self.assertIn("kbm", rep["programs"])
            self.assertIn("code/ace_demo", rep["programs"])
            self.assertEqual(rep["programs"]["tools"]["files"][0]["status"], "modified")

    def test_program_map_and_invalid_repo_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            non_git = tmp / "plain_dir"
            non_git.mkdir()
            with self.assertRaises(StorageDebtError):
                scan_storage_debt(non_git)
            self.assertEqual(main(["--workspace", str(non_git)]), 2)

            repo = tmp / "repo"
            repo.mkdir()
            _git(repo, "init")
            _git(repo, "config", "user.name", "Test")
            _git(repo, "config", "user.email", "test@example.com")
            (repo / "README.md").write_text("hi\n", encoding="utf-8")
            _git(repo, "add", ".")
            _git(repo, "commit", "-m", "init")
            (repo / "staging" / "evo7").mkdir(parents=True)
            (repo / "staging" / "evo7" / "p.jsonl").write_text("{}\n", encoding="utf-8")

            pmap_path = tmp / "pmap.json"
            pmap_path.write_text(json.dumps({"staging/evo7/": "EVO_0007"}), encoding="utf-8")
            rc = main(["--workspace", str(repo), "--program-map", str(pmap_path)])
            self.assertEqual(rc, 0)
            rep = scan_storage_debt(repo, program_map={"staging/evo7/": "EVO_0007"})
            self.assertIn("EVO_0007", rep["programs"])


if __name__ == "__main__":
    unittest.main()
