"""Tes audit checkpoint dan branch dengan repositori Git sintetis."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.self_dev_git_audit import AuditError, GitRepository, diff_checkpoints, field_history, guard_branch


class SelfDevGitAuditTests(unittest.TestCase):
    PATH = "fixtures/checkpoint.json"
    SCRIPT = Path(__file__).with_name("self_dev_git_audit.py")

    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.file = self.root / self.PATH
        self.file.parent.mkdir()
        self.env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Fixture",
            "GIT_COMMITTER_NAME": "Fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.test",
            "GIT_COMMITTER_EMAIL": "fixture@example.test",
        }
        self.git("init", "-q", "-b", "fixture")
        self.repo = GitRepository(self.root)

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-c", "commit.gpgSign=false", "-c", "core.hooksPath=/dev/null", *args],
            cwd=self.root, env=self.env,
        ).decode().rstrip("\n")

    def record(self, state=None, *, raw=None, day=1):
        if raw is not None:
            self.file.write_text(raw, encoding="utf-8")
        elif state is None:
            self.file.unlink(missing_ok=True)
        else:
            self.file.write_text(json.dumps(state), encoding="utf-8")
        self.git("add", "--all")
        for key in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
            self.env[key] = f"2026-01-{day:02d}T09:00:00+00:00"
        self.git("commit", "-qm", f"Checkpoint fixture {day}", "--allow-empty")
        return self.git("rev-parse", "HEAD")

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, str(self.SCRIPT), "--repo", str(self.root), *args],
            capture_output=True, text=True, check=False,
        )

    def test_diff_counts_and_escapes_nested_fields_without_values(self):
        before = self.record({"phase": {"old": True, "a~/b": "token-fixture-1"}, "same": [1, {"x": 2}]})
        after = self.record({"phase": {"new": None, "a~/b": "token-fixture-2"}, "same": [1, {"x": 2}]},
                            day=2)
        report = diff_checkpoints(self.repo, before, after, self.PATH)
        self.assertEqual(report["counts"], {"added": 1, "removed": 1, "modified": 1})
        self.assertEqual([(c["field"], c["status"]) for c in report["changes"]], [
            ("/phase/a~0~1b", "modified"), ("/phase/new", "added"), ("/phase/old", "removed"),
        ])
        self.assertNotIn("token-fixture", json.dumps(report))

    def test_diff_ignores_reformatting_and_compares_number_exactly(self):
        first = self.record(raw='{"a":1,"b":0.12345678901234567890123}')
        second = self.record(raw='{ "b":0.12345678901234567890123, "a": 1.0 }', day=2)
        third = self.record(raw='{"a":true,"b":0.12345678901234567890124}', day=3)
        self.assertEqual(diff_checkpoints(self.repo, first, second, self.PATH)["changes"], [])
        self.assertEqual([c["field"] for c in diff_checkpoints(self.repo, second, third, self.PATH)["changes"]],
                         ["/a", "/b"])

    def test_diff_tracks_absence_and_ignores_worktree_changes(self):
        before = self.record()
        after = self.record({"cycle": 1}, day=2)
        self.file.write_text("uncommitted content", encoding="utf-8")
        status_before = self.git("status", "--porcelain")
        diff = diff_checkpoints(self.repo, before, after, self.PATH)
        self.assertFalse(diff["present_before"])
        self.assertTrue(diff["present_after"])
        self.assertEqual(diff["changes"], [
            {"field": "", "status": "added", "before_type": "missing", "after_type": "object"},
        ])
        self.assertEqual(status_before, self.git("status", "--porcelain"))
        self.assertEqual(self.file.read_text(encoding="utf-8"), "uncommitted content")

    def test_history_reports_exact_field_dates_and_null_vs_missing(self):
        base = self.record({"cycle": {"data": [{"counter": None}]}})
        switched = self.record({"cycle": {"data": [{"counter": False}]}}, day=2)
        self.record({"cycle": {"data": [{"counter": False}]}, "extra": 2}, day=3)
        removed = self.record({"cycle": {"data": []}}, day=4)
        report = field_history(self.repo, base, removed, self.PATH, "/cycle/data/0/counter")
        self.assertEqual(report["commits_examined"], 3)
        timeline = [{key: value for key, value in change.items() if key != "committed_at"}
                    for change in report["changes"]]
        self.assertEqual(timeline, [
            {"commit": switched, "field": "/cycle/data/0/counter",
             "status": "modified", "before_type": "null", "after_type": "boolean"},
            {"commit": removed, "field": "/cycle/data/0/counter",
             "status": "removed", "before_type": "boolean", "after_type": "missing"},
        ])
        self.assertEqual([datetime.fromisoformat(c["committed_at"]) for c in report["changes"]],
                         [datetime(2026, 1, day, 9, tzinfo=timezone.utc) for day in (2, 4)])

    def test_history_assigns_merged_field_to_merge_commit(self):
        base = self.record({"cycle": 1})
        self.git("switch", "-qc", "outside")
        side = self.record({"cycle": 2}, day=2)
        self.git("switch", "-q", "fixture")
        self.record({"cycle": 1}, day=3)
        self.git("merge", "--no-ff", "--no-edit", "outside")
        merged = self.git("rev-parse", "HEAD")
        report = field_history(self.repo, base, merged, self.PATH, "/cycle")
        self.assertEqual([c["commit"] for c in report["changes"]], [merged])
        with self.assertRaisesRegex(AuditError, "induk pertama"):
            field_history(self.repo, side, merged, self.PATH, "/cycle")

    def test_guard_finds_commits_from_all_parents_and_checks_stale_expectations(self):
        base = self.record({"cycle": 1})
        self.git("switch", "-qc", "outside")
        side = self.record({"cycle": 2}, day=2)
        self.git("switch", "-q", "fixture")
        work = self.record({"cycle": 1}, day=3)
        self.git("merge", "--no-ff", "--no-edit", "outside")
        merged = self.git("rev-parse", "HEAD")
        report = guard_branch(self.repo, base, merged, [work, merged, base])
        self.assertFalse(report["clean"])
        self.assertEqual(report["unexpected"], [side])
        self.assertEqual(report["missing_expected"], [base])
        self.assertTrue(guard_branch(self.repo, base, merged, [work, side, merged])["clean"])

    def test_guard_marks_wrong_base_and_bad_expectations(self):
        base = self.record({"cycle": 1})
        self.git("switch", "-qc", "outside")
        side = self.record({"cycle": 2}, day=2)
        self.git("switch", "-q", "fixture")
        work = self.record({"cycle": 1}, day=3)
        report = guard_branch(self.repo, side, work, [work])
        self.assertFalse(report["base_is_ancestor"])
        self.assertFalse(report["clean"])
        self.assertEqual(report["unexpected"], [])
        with self.assertRaisesRegex(AuditError, "ID objek Git penuh"):
            guard_branch(self.repo, base, work, [work[:8]])
        with self.assertRaisesRegex(AuditError, "commit ganda"):
            guard_branch(self.repo, base, work, [work, work])

    def test_guard_requires_complete_local_history(self):
        first = self.record({"cycle": 1})
        tip = self.record({"cycle": 2}, day=2)
        (self.root / ".git/shallow").write_text(tip + "\n", encoding="utf-8")
        with self.assertRaisesRegex(AuditError, "Git dangkal"):
            guard_branch(self.repo, first, tip, [tip])

    def test_audit_rejects_invalid_json_paths_and_git_options(self):
        base = self.record({"cycle": 1})
        for raw in ('{"secret-fixture":1,"secret-fixture":2}', '{"cycle":NaN}', "{"):
            tip = self.record(raw=raw)
            with self.assertRaisesRegex(AuditError, "bukan JSON") as caught:
                diff_checkpoints(self.repo, base, tip, self.PATH)
            self.assertNotIn("secret-fixture", str(caught.exception))
        with self.assertRaisesRegex(AuditError, "relatif"):
            diff_checkpoints(self.repo, base, base, "../private.json")
        with self.assertRaisesRegex(AuditError, "JSON Pointer"):
            field_history(self.repo, base, base, self.PATH, "/invalid~z")
        bad_option = self.cli("guard", "--base=--help", "--tip", "HEAD")
        self.assertEqual(bad_option.returncode, 2)
        self.assertFalse(bad_option.stdout)

    def test_symlink_checkpoint_is_rejected(self):
        base = self.record({"cycle": 1})
        self.file.unlink()
        self.file.symlink_to("fixture-private.json")
        self.git("add", self.PATH)
        self.git("commit", "-qm", "Fixture symlink")
        with self.assertRaisesRegex(AuditError, "berkas JSON reguler"):
            diff_checkpoints(self.repo, base, "HEAD", self.PATH)

    def test_cli_guard_exit_codes_and_no_worktree_changes(self):
        base = self.record({"cycle": 1})
        tip = self.record({"cycle": 2}, day=2)
        dirty = self.cli("guard", "--base", base, "--tip", "HEAD")
        clean = self.cli("guard", "--base", base, "--tip", "HEAD", "--expect", tip)
        self.assertEqual(dirty.returncode, 1, dirty.stderr)
        self.assertEqual(clean.returncode, 0, clean.stderr)
        self.assertEqual(json.loads(dirty.stdout)["unexpected"], [tip])
        self.assertTrue(json.loads(clean.stdout)["clean"])
        self.assertFalse(self.git("status", "--porcelain"))
        self.assertEqual(self.git("rev-parse", "HEAD"), tip)


if __name__ == "__main__":
    unittest.main()
