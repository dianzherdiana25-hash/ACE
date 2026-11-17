#!/usr/bin/env python3
"""Unit tests untuk tools/daily_digest.py (WS-E #15)."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import daily_digest


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _init_sample_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.com")
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "chore: initial commit")
    (repo / "tools").mkdir()
    (repo / "tools" / "alpha.py").write_text("print('ok')\n", encoding="utf-8")
    _git(repo, "add", "tools/alpha.py")
    _git(repo, "commit", "-m", "feat: add alpha tool")


class TestDailyDigest(unittest.TestCase):
    def test_build_digest_with_dirty_workspace_and_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = tmp_path / "repo"
            _init_sample_repo(repo)

            # Buat perubahan lokal yang belum di-commit
            (repo / "README.md").write_text("# Demo updated\n", encoding="utf-8")
            (repo / "notes.tmp").write_text("draft\n", encoding="utf-8")

            stage_json = tmp_path / "stage.json"
            stage_json.write_text(
                json.dumps({"schema": "ace.stage-verify.v1", "stage": "stage-1", "ok": True}),
                encoding="utf-8",
            )
            debt_json = tmp_path / "debt.json"
            debt_json.write_text(
                json.dumps(
                    {
                        "schema": "ace.storage-debt.v1",
                        "summary": {
                            "total_debt_files": 2,
                            "total_debt_bytes": 21,
                            "unpushed_commit_count": 0,
                        },
                    }
                ),
                encoding="utf-8",
            )
            bad_json = tmp_path / "bad.json"
            bad_json.write_text("{not-json", encoding="utf-8")

            digest = daily_digest.build_daily_digest(
                repo,
                digest_date="2026-11-17",
                stage_file=str(stage_json),
                storage_debt_file=str(debt_json),
                royalty_file=str(bad_json),
                schedule_file=str(tmp_path / "missing.json"),
            )

            self.assertEqual(digest["schema"], "ace.daily-digest.v1")
            self.assertIs(digest["authoritative"], False)
            self.assertEqual(digest["summary"]["commit_count"], 2)
            self.assertEqual(digest["commits"][0]["subject"], "feat: add alpha tool")
            self.assertIn("tools/alpha.py", digest["touched_files"])
            self.assertFalse(digest["workspace"]["clean"])
            self.assertEqual(digest["workspace"]["modified_paths"], ["README.md"])
            self.assertEqual(digest["workspace"]["untracked_paths"], ["notes.tmp"])
            self.assertEqual(digest["signals"]["stage"]["stage"], "stage-1")
            self.assertEqual(digest["signals"]["storage_debt"]["total_debt_files"], 2)
            self.assertEqual(len(digest["warnings"]), 2)

            md = daily_digest.render_markdown(digest)
            self.assertIn("NON-OTORITATIF", md)
            self.assertIn("feat: add alpha tool", md)
            self.assertIn("notes.tmp", md)
            self.assertIn("storage_debt", md)

    def test_cli_outputs_files_and_rejects_non_git_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo = tmp_path / "repo"
            _init_sample_repo(repo)
            out_json = tmp_path / "digest.json"
            out_md = tmp_path / "digest.md"

            rc = daily_digest.main(
                [
                    "--repo-dir",
                    str(repo),
                    "--date",
                    "2026-11-17",
                    "--max-commits",
                    "1",
                    "--out-json",
                    str(out_json),
                    "--out-md",
                    str(out_md),
                    "--format",
                    "md",
                ]
            )
            self.assertEqual(rc, 0)
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["commit_count"], 1)
            self.assertIn("NON-OTORITATIF", out_md.read_text(encoding="utf-8"))

            plain = tmp_path / "not_git"
            plain.mkdir()
            rc_err = daily_digest.main(["--repo-dir", str(plain)])
            self.assertEqual(rc_err, 2)


if __name__ == "__main__":
    unittest.main()
