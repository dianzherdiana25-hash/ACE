"""Uji laporan pra-review branch terpin operator termasuk cherry-pick & merge commit di repo fixture."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.self_dev_git_audit import (
    AuditError,
    GitRepository,
    PREREVIEW_SCHEMA,
    pre_review_report,
)


SCRIPT = Path(__file__).with_name("self_dev_git_audit.py")


class SelfDevBranchPrereviewTests(unittest.TestCase):
    CP_PATH = "fixtures/checkpoint.json"

    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Fixture",
            "GIT_COMMITTER_NAME": "Fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.test",
            "GIT_COMMITTER_EMAIL": "fixture@example.test",
        }
        self.git("init", "-q", "-b", "main")
        self.repo = GitRepository(self.root)

    def git(self, *args: str) -> str:
        return subprocess.check_output(
            ["git", "-c", "commit.gpgSign=false", "-c", "core.hooksPath=/dev/null", *args],
            cwd=self.root,
            env=self.env,
        ).decode().rstrip("\n")

    def commit_files(self, files: dict[str, object], msg: str, *, day: int = 1) -> str:
        for rel, body in files.items():
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            content = body if isinstance(body, str) else json.dumps(body, sort_keys=True) + "\n"
            target.write_text(content, encoding="utf-8")
        self.git("add", "--all")
        for key in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
            self.env[key] = f"2026-02-{day:02d}T10:00:00+00:00"
        self.git("commit", "-qm", msg)
        return self.git("rev-parse", "HEAD")

    def cli(self, *args: str):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", str(self.root), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_linear_pinned_history_passes_strict_and_summarizes_checkpoint_diff(self):
        base = self.commit_files({self.CP_PATH: {"cycle": 1, "status": "draft"}}, "base", day=1)
        c1 = self.commit_files(
            {self.CP_PATH: {"cycle": 2, "status": "staged"}, "tools/note.txt": "step 1\n"},
            "work step 1",
            day=2,
        )
        c2 = self.commit_files(
            {self.CP_PATH: {"cycle": 3, "status": "ratified", "extra": True}, "tools/note.txt": "step 2\n"},
            "work step 2",
            day=3,
        )

        report = pre_review_report(self.repo, base, c2, [c1, c2], checkpoint_paths=[self.CP_PATH])
        self.assertEqual(report["schema"], PREREVIEW_SCHEMA)
        self.assertEqual(report["history_shape"], "linear_exact")
        self.assertTrue(report["strict_oid_clean"])
        self.assertTrue(report["patch_equivalent_clean"])
        self.assertEqual(report["matched_pinned"], [c1, c2])
        self.assertEqual(report["cherry_picked_equivalents"], [])
        self.assertEqual(report["merge_commits"], [])
        self.assertEqual(report["unexpected_commits"], [])
        self.assertEqual(report["missing_pinned_commits"], [])
        self.assertEqual([item["path"] for item in report["changed_files"]], [self.CP_PATH, "tools/note.txt"])
        self.assertEqual(report["checkpoint_diffs"][0]["counts"], {"added": 1, "removed": 0, "modified": 2})

        pin_file = self.root / "pins.json"
        pin_file.write_text(json.dumps({"pinned_commits": [c1, c2]}), encoding="utf-8")
        res = self.cli("prereview", "--base", base, "--tip", c2, "--pin-file", str(pin_file), "--checkpoint", self.CP_PATH)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(json.loads(res.stdout)["strict_oid_clean"])

    def test_cherry_picked_branch_identifies_patch_equivalence_vs_oid_change(self):
        base = self.commit_files({self.CP_PATH: {"cycle": 1}, "src/app.py": "v = 1\n"}, "base", day=1)

        # Build original operator branch and record original pinned commit OIDs
        self.git("switch", "-qc", "operator-origin")
        orig_a = self.commit_files({"src/feature_a.py": "def a():\n    return 1\n"}, "feat a", day=2)
        orig_b = self.commit_files(
            {self.CP_PATH: {"cycle": 2, "cherry": True}},
            "bump checkpoint",
            day=3,
        )

        # Recreate target review branch where base moved slightly and operator commits were cherry-picked
        self.git("switch", "-q", "main")
        moved_base = self.commit_files({"docs/changelog.md": "prep\n"}, "prep base", day=4)
        self.git("switch", "-qc", "gravity-review")
        self.env["GIT_AUTHOR_DATE"] = self.env["GIT_COMMITTER_DATE"] = "2026-02-05T10:00:00+00:00"
        self.git("cherry-pick", orig_a)
        picked_a = self.git("rev-parse", "HEAD")
        self.env["GIT_AUTHOR_DATE"] = self.env["GIT_COMMITTER_DATE"] = "2026-02-06T10:00:00+00:00"
        self.git("cherry-pick", orig_b)
        picked_b = self.git("rev-parse", "HEAD")
        self.assertNotEqual(orig_a, picked_a)
        self.assertNotEqual(orig_b, picked_b)

        report = pre_review_report(
            self.repo, moved_base, picked_b, [orig_a, orig_b], checkpoint_paths=[self.CP_PATH]
        )
        self.assertEqual(report["history_shape"], "cherry_pick_equivalent")
        self.assertFalse(report["strict_oid_clean"])
        self.assertTrue(report["patch_equivalent_clean"])
        self.assertEqual(report["missing_pinned_commits"], [])
        self.assertEqual(report["unexpected_commits"], [])
        self.assertEqual(
            {(e["actual_commit"], e["matched_pinned_commit"]) for e in report["cherry_picked_equivalents"]},
            {(picked_a, orig_a), (picked_b, orig_b)},
        )

        res = self.cli("prereview", "--base", moved_base, "--tip", picked_b, "--expect", orig_a, "--expect", orig_b)
        # Strict OID mismatch exits 1 with clear diagnostic report
        self.assertEqual(res.returncode, 1)
        self.assertEqual(json.loads(res.stdout)["history_shape"], "cherry_pick_equivalent")

    def test_merge_commit_history_tracks_all_parents_and_detects_rogue_side_commit(self):
        base = self.commit_files({self.CP_PATH: {"cycle": 1}}, "base", day=1)
        self.git("switch", "-qc", "side")
        side_commit = self.commit_files({"src/side.py": "x = 42\n"}, "side feature", day=2)
        self.git("switch", "-q", "main")
        main_commit = self.commit_files({self.CP_PATH: {"cycle": 2}}, "main update", day=3)
        self.env["GIT_AUTHOR_DATE"] = self.env["GIT_COMMITTER_DATE"] = "2026-02-04T10:00:00+00:00"
        self.git("merge", "--no-ff", "--no-edit", "side")
        merge_oid = self.git("rev-parse", "HEAD")

        # Exact pin including merge commit passes cleanly
        clean_rep = pre_review_report(self.repo, base, merge_oid, [main_commit, side_commit, merge_oid])
        self.assertTrue(clean_rep["strict_oid_clean"])
        self.assertEqual(clean_rep["history_shape"], "merge_clean")
        self.assertEqual(len(clean_rep["merge_commits"]), 1)
        self.assertTrue(clean_rep["merge_commits"][0]["pinned_exact"])
        self.assertEqual(clean_rep["merge_commits"][0]["parents"], [main_commit, side_commit])

        # Omitting rogue/unpinned side commit catches it via multi-parent traversal
        dirty_rep = pre_review_report(self.repo, base, merge_oid, [main_commit, merge_oid])
        self.assertFalse(dirty_rep["strict_oid_clean"])
        self.assertFalse(dirty_rep["patch_equivalent_clean"])
        self.assertEqual(dirty_rep["history_shape"], "merge_diverged")
        self.assertEqual([c["commit"] for c in dirty_rep["unexpected_commits"]], [side_commit])

    def test_rejects_short_or_duplicate_pinned_ids(self):
        base = self.commit_files({self.CP_PATH: {"cycle": 1}}, "base", day=1)
        tip = self.commit_files({self.CP_PATH: {"cycle": 2}}, "tip", day=2)
        with self.assertRaisesRegex(AuditError, "ID objek Git penuh"):
            pre_review_report(self.repo, base, tip, [tip[:8]])
        with self.assertRaisesRegex(AuditError, "ID ganda"):
            pre_review_report(self.repo, base, tip, [tip, tip])


if __name__ == "__main__":
    unittest.main()
