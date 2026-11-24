"""Tests for Autonomous Git & GitHub Delivery (`git_ops.py`) against a real local bare repo + mock gh CLI."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from ace_operational.git_ops import prepare_branch_and_commit, push_and_open_pr, verify_checks_and_merge_pr
from ace_operational.store import OperationalStore


class GitOpsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ace-git-ops-")
        root = Path(self._tmp.name)
        self.ws = root / "ws"
        self.bare = root / "origin.git"
        self.repo = root / "repo"

        subprocess.run(["git", "init", "--bare", "-b", "main", str(self.bare)], check=True, capture_output=True)
        subprocess.run(["git", "init", "-b", "main", str(self.repo)], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@local"], cwd=self.repo, check=True)
        (self.repo / "README.md").write_text("# Demo\n", encoding="utf-8")
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "UPSTREAM_SOURCES.json").write_text('{"files":[{"path":"frozen.py"}]}', encoding="utf-8")
        (self.repo / "frozen.py").write_text("# frozen\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-m", "initial main"], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", str(self.bare)], cwd=self.repo, check=True)
        subprocess.run(["git", "push", "-u", "origin", "main"], cwd=self.repo, check=True, capture_output=True)

        self.store = OperationalStore(self.ws)
        self.task = self.store.create_task(title_id="Fix feature", user_request="fix", normalized_goal="fix")
        self.good_rcpt = self.store.record_receipt(
            task_id=self.task["task_id"],
            action_kind="work_order_verified",
            input_data="in",
            output_data="out",
            command_or_operation="unittest",
            exit_code=0,
            passed=True,
        )

    def tearDown(self) -> None:
        self.store.close()
        self._tmp.cleanup()

    def _set_policy(self, *, git_auto_pr: bool, git_auto_merge: bool, min_score_bp: int = 8500) -> None:
        (self.ws / ".ace_policy.json").write_text(
            json.dumps({
                "git_auto_pr": git_auto_pr,
                "git_auto_merge": git_auto_merge,
                "min_quality_score_bp": min_score_bp,
            }),
            encoding="utf-8",
        )

    def test_blocks_below_bar_frozen_files_and_secret_leaks(self) -> None:
        self._set_policy(git_auto_pr=True, git_auto_merge=True, min_score_bp=8500)
        (self.repo / "app.py").write_text("VALUE = 42\n", encoding="utf-8")

        # 1. Below-bar score rejected strictly!
        low = prepare_branch_and_commit(
            self.repo, self.store,
            task_id=self.task["task_id"],
            receipt_id=self.good_rcpt["receipt_id"],
            order_id="ord_low",
            slug="low-score",
            target_files=["app.py"],
            commit_message="fix: below bar",
            score_bp=7900,
        )
        self.assertFalse(low["ok"])
        self.assertEqual(low["verdict"], "REJECTED_BELOW_BAR")

        # 2. Frozen upstream file rejected!
        frozen = prepare_branch_and_commit(
            self.repo, self.store,
            task_id=self.task["task_id"],
            receipt_id=self.good_rcpt["receipt_id"],
            order_id="ord_frz",
            slug="touch-frozen",
            target_files=["frozen.py"],
            commit_message="bad touch",
            score_bp=9500,
        )
        self.assertFalse(frozen["ok"])
        self.assertEqual(frozen["verdict"], "CUSTODY_OR_SECRET_BLOCK")

        # 3. File containing secret pattern rejected!
        (self.repo / "leak.py").write_text("TOKEN = 'EAAG1234567890ABCDEFGHIJ'\n", encoding="utf-8")
        sec = prepare_branch_and_commit(
            self.repo, self.store,
            task_id=self.task["task_id"],
            receipt_id=self.good_rcpt["receipt_id"],
            order_id="ord_sec",
            slug="secret-leak",
            target_files=["leak.py"],
            commit_message="oops",
            score_bp=9500,
        )
        self.assertFalse(sec["ok"])
        self.assertEqual(sec["verdict"], "CUSTODY_OR_SECRET_BLOCK")

    def test_full_e2e_branch_commit_push_pr_anti_toctou_and_merge_to_main(self) -> None:
        # Policy disabled first -> PR refused cleanly
        self._set_policy(git_auto_pr=False, git_auto_merge=False)
        (self.repo / "feature.py").write_text("def greet():\n    return 'halo ACE'\n", encoding="utf-8")
        c_res = prepare_branch_and_commit(
            self.repo, self.store,
            task_id=self.task["task_id"],
            receipt_id=self.good_rcpt["receipt_id"],
            order_id="ord_1",
            slug="add-greet",
            target_files=["feature.py"],
            commit_message="feat: add greet helper",
            score_bp=9200,
        )
        self.assertTrue(c_res["ok"], c_res)
        self.assertTrue(c_res["branch"].startswith("ace-auto/"))

        blocked_pr = push_and_open_pr(
            self.repo, self.store,
            task_id=self.task["task_id"],
            receipt_id=self.good_rcpt["receipt_id"],
            branch=c_res["branch"],
            title="Add greet helper",
            body="Tested.",
            score_bp=9200,
        )
        self.assertFalse(blocked_pr["ok"])
        self.assertEqual(blocked_pr["verdict"], "POLICY_DISABLED")

        # Enable full policy -> custom runner handles git natively and simulates gh CLI merging branch into main in bare repo!
        self._set_policy(git_auto_pr=True, git_auto_merge=True)
        head_sha = c_res["head_sha"]

        def fake_runner(cmd, *, cwd, timeout=60):
            if cmd[0].endswith("gh"):
                sub = cmd[1:3]
                if sub == ["pr", "create"]:
                    return subprocess.CompletedProcess(cmd, 0, "https://github.com/test/repo/pull/42\n", "")
                if sub == ["pr", "view"]:
                    if getattr(fake_runner, "bad_sha", False):
                        oid = "0" * 40
                    else:
                        oid = head_sha
                    rollup = [{"conclusion": "FAILURE"}] if getattr(fake_runner, "ci_fail", False) else [{"conclusion": "SUCCESS"}]
                    return subprocess.CompletedProcess(
                        cmd, 0,
                        json.dumps({
                            "number": 42,
                            "url": "https://github.com/test/repo/pull/42",
                            "state": "OPEN",
                            "mergeable": "MERGEABLE",
                            "headRefOid": oid,
                            "headRefName": c_res["branch"],
                            "statusCheckRollup": rollup,
                        }),
                        "",
                    )
                if sub == ["pr", "merge"]:
                    # Perform real git merge on main + delete remote branch in local bare repo!
                    subprocess.run(["git", "checkout", "main"], cwd=cwd, check=True, capture_output=True)
                    subprocess.run(["git", "merge", "--squash", c_res["branch"]], cwd=cwd, check=True, capture_output=True)
                    subprocess.run(["git", "commit", "-m", "Add greet helper (#42)"], cwd=cwd, check=True, capture_output=True)
                    subprocess.run(["git", "push", "origin", "main"], cwd=cwd, check=True, capture_output=True)
                    subprocess.run(["git", "push", "origin", "--delete", c_res["branch"]], cwd=cwd, check=True, capture_output=True)
                    return subprocess.CompletedProcess(cmd, 0, "Merged PR #42\n", "")
            return subprocess.run(list(cmd), cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False)

        pr_res = push_and_open_pr(
            self.repo, self.store,
            task_id=self.task["task_id"],
            receipt_id=self.good_rcpt["receipt_id"],
            branch=c_res["branch"],
            title="Add greet helper",
            body="Verified PR",
            score_bp=9200,
            gh_bin="gh",
            runner=fake_runner,
        )
        self.assertTrue(pr_res["ok"], pr_res)
        self.assertEqual(pr_res["pr_number"], 42)

        # Anti-TOCTOU check: mismatching headRefOid must refuse merge!
        fake_runner.bad_sha = True
        toctou = verify_checks_and_merge_pr(
            self.repo, self.store,
            task_id=self.task["task_id"],
            receipt_id=self.good_rcpt["receipt_id"],
            pr_number=42,
            expected_head_sha=head_sha,
            score_bp=9200,
            gh_bin="gh",
            runner=fake_runner,
        )
        self.assertFalse(toctou["ok"])
        self.assertEqual(toctou["verdict"], "HEAD_SHA_MISMATCH")
        fake_runner.bad_sha = False

        # Failing CI check must refuse merge!
        fake_runner.ci_fail = True
        ci_block = verify_checks_and_merge_pr(
            self.repo, self.store,
            task_id=self.task["task_id"],
            receipt_id=self.good_rcpt["receipt_id"],
            pr_number=42,
            expected_head_sha=head_sha,
            score_bp=9200,
            gh_bin="gh",
            runner=fake_runner,
        )
        self.assertFalse(ci_block["ok"])
        self.assertEqual(ci_block["verdict"], "CI_NOT_GREEN")
        fake_runner.ci_fail = False

        # High quality + matching SHA + green CI -> merges into main & syncs main!
        merged = verify_checks_and_merge_pr(
            self.repo, self.store,
            task_id=self.task["task_id"],
            receipt_id=self.good_rcpt["receipt_id"],
            pr_number=42,
            expected_head_sha=head_sha,
            score_bp=9200,
            gh_bin="gh",
            runner=fake_runner,
        )
        self.assertTrue(merged["ok"], merged)
        self.assertEqual(merged["verdict"], "MERGED")
        self.assertTrue((self.repo / "feature.py").is_file())
        log_out = subprocess.run(["git", "log", "-n", "1", "--oneline", "main"], cwd=self.repo, capture_output=True, text=True).stdout
        self.assertIn("Add greet helper", log_out)


if __name__ == "__main__":
    unittest.main()
