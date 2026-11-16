"""Tests for ace_operational.self_send (governed self-send).

The governance is the product: marker gate, branch namespace,
path allowlist/denylist, non-force push, draft-only PRs,
duplicate refusal, fail-closed audit. A scripted fake runner
stands in for git/gh so every argv is inspectable; no network,
no real remote, no credentials anywhere near these tests.
"""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from ace_operational import self_send as ss

TODAY = date(2026, 11, 16)
PR_URL = "https://github.com/dianzherdiana25-hash/ACE/pull/999"


class FakeRunner:
    def __init__(self, *, auth_ok=True, branch_local=False,
                 branch_remote=False, fail_at=None):
        self.calls = []
        self.auth_ok = auth_ok
        self.branch_local = branch_local
        self.branch_remote = branch_remote
        self.fail_at = fail_at

    def __call__(self, argv, cwd):
        self.calls.append(list(argv))
        joined = " ".join(argv)
        if self.fail_at and self.fail_at in joined:
            return 1, "", f"injected failure at {self.fail_at}"
        if argv[:3] == ["gh", "auth", "status"]:
            return (0, "", "") if self.auth_ok else (1, "", "no auth")
        if argv[:2] == ["git", "rev-parse"]:
            return (0, "abc\n", "") if self.branch_local else (1, "", "")
        if argv[:2] == ["git", "ls-remote"]:
            if self.branch_remote:
                return 0, f"abc\trefs/heads/{argv[-1]}\n", ""
            return 0, "", ""
        if argv[:3] == ["git", "branch", "--show-current"]:
            return 0, "main\n", ""
        if argv[:3] == ["gh", "pr", "create"]:
            return 0, PR_URL + "\n", ""
        if argv[:3] == ["gh", "pr", "view"]:
            return 0, json.dumps({
                "number": 999, "url": PR_URL,
                "state": "OPEN", "isDraft": True}), ""
        return 0, "", ""

    def argv_text(self):
        return "\n".join(" ".join(c) for c in self.calls)


class SelfSendCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo = root / "repo"
        self.repo.mkdir()
        self.home = root / "home"
        self.home.mkdir()
        self.files = {"handover/NOTE.md": b"# harmless test note\n"}

    def tearDown(self):
        self.tmp.cleanup()

    def arm_marker(self):
        (self.home / ss.MARKER_NAME).write_text("enabled\n")

    def send(self, runner, **kw):
        kw.setdefault("slug", "test-note")
        kw.setdefault("trigger", "manual_cli")
        kw.setdefault("today", TODAY)
        return ss.send(self.repo, self.home, files=self.files,
                       runner=runner, **kw)

    def audit_rows(self):
        path = self.home / "self_send_audit.jsonl"
        if not path.exists():
            return []
        return [json.loads(l) for l in
                path.read_text().splitlines() if l.strip()]


class TestGates(SelfSendCase):
    def test_marker_absent_refuses_before_any_command(self):
        runner = FakeRunner()
        result = self.send(runner)
        self.assertFalse(result.sent)
        self.assertEqual(result.reason, "marker_absent")
        self.assertEqual(runner.calls, [])
        self.assertEqual(self.audit_rows()[0]["outcome"],
                         "refused:marker_absent")

    def test_gh_auth_unhealthy_refuses(self):
        self.arm_marker()
        result = self.send(FakeRunner(auth_ok=False))
        self.assertEqual(result.reason, "gh_auth_unhealthy")

    def test_duplicate_local_branch_refuses(self):
        self.arm_marker()
        result = self.send(FakeRunner(branch_local=True))
        self.assertEqual(result.reason, "duplicate_branch")

    def test_duplicate_remote_branch_refuses(self):
        self.arm_marker()
        result = self.send(FakeRunner(branch_remote=True))
        self.assertEqual(result.reason, "duplicate_branch")

    def test_disallowed_path_refuses(self):
        self.arm_marker()
        self.files = {"code/ace_operational/x.py": b"x"}
        result = self.send(FakeRunner())
        self.assertTrue(result.reason.startswith("governance:"))

    def test_denylisted_path_refuses_even_under_allowlist(self):
        self.arm_marker()
        self.files = {"handover/LEDGER_PENGHASILAN.md": b"x"}
        result = self.send(FakeRunner())
        self.assertFalse(result.sent)
        self.assertTrue(result.reason.startswith("governance:"))

    def test_bad_slug_refuses(self):
        self.arm_marker()
        result = self.send(FakeRunner(), slug="Bad Slug!")
        self.assertTrue(result.reason.startswith("governance:"))


class TestHappyPath(SelfSendCase):
    def test_send_creates_draft_pr_without_force(self):
        self.arm_marker()
        runner = FakeRunner()
        result = self.send(runner)
        self.assertTrue(result.sent, result.reason)
        self.assertEqual(result.branch, "ace-auto/20261116-test-note")
        self.assertEqual(result.pr_number, 999)
        text = runner.argv_text()
        self.assertIn("--draft", text)
        self.assertNotIn("--force", text)
        self.assertIn("git push -u origin ace-auto/20261116-test-note",
                      text)
        # The file and the committed audit row landed in the repo.
        self.assertEqual(
            (self.repo / "handover/NOTE.md").read_bytes(),
            b"# harmless test note\n")
        committed = (self.repo / ss.AUDIT_REPO_PATH).read_text()
        row = json.loads(committed.strip().splitlines()[-1])
        self.assertEqual(row["branch"], result.branch)
        self.assertEqual(row["content_digest"],
                         result.content_digest)
        local = self.audit_rows()
        self.assertEqual(local[-1]["outcome"], "sent")
        self.assertEqual(local[-1]["pr_number"], 999)

    def test_pr_create_failure_records_pushed_branch(self):
        self.arm_marker()
        runner = FakeRunner(fail_at="pr create")
        result = self.send(runner)
        self.assertFalse(result.sent)
        self.assertTrue(result.reason.startswith("pr_create_failed"))
        self.assertEqual(self.audit_rows()[-1]["outcome"],
                         "pushed_pr_failed")
        self.assertNotIn("--force", runner.argv_text())

    def test_push_failure_stops_before_pr(self):
        self.arm_marker()
        runner = FakeRunner(fail_at="git push")
        result = self.send(runner)
        self.assertTrue(result.reason.startswith("push_failed"))
        self.assertNotIn("pr create", runner.argv_text())


class TestPathsAndNames(unittest.TestCase):
    def test_branch_name_shape(self):
        self.assertEqual(ss.branch_name_for(TODAY, "abc-1"),
                         "ace-auto/20261116-abc-1")
        self.assertTrue(
            ss.validate_branch_name("ace-auto/20261116-abc-1"))
        self.assertFalse(ss.validate_branch_name("main"))
        self.assertFalse(
            ss.validate_branch_name("ace-dev/20261116-abc"))

    def test_path_rules(self):
        self.assertTrue(ss.path_allowed("handover/x.md"))
        self.assertTrue(ss.path_allowed("evidence/a/b.json"))
        self.assertTrue(ss.path_allowed(ss.AUDIT_REPO_PATH))
        self.assertFalse(ss.path_allowed("code/x.py"))
        self.assertFalse(ss.path_allowed("../handover/x.md"))
        self.assertFalse(ss.path_allowed("/handover/x.md"))
        self.assertFalse(ss.path_allowed("handover/.env"))
        self.assertFalse(ss.path_allowed("evidence/UTANG_AWAL_x.jpg"))

    def test_content_digest_stable_and_order_free(self):
        a = ss.content_digest({"b": b"2", "a": b"1"})
        b = ss.content_digest({"a": b"1", "b": b"2"})
        self.assertEqual(a, b)
        self.assertNotEqual(a, ss.content_digest({"a": b"1"}))


class TestRatificationBatch(SelfSendCase):
    def write_store(self, records):
        root = Path(self.tmp.name) / "memory"
        root.mkdir()
        (root / "memory.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in records))
        return root

    def rec(self, rid, cls):
        return {"id": rid, "kind": "semantic",
                "content": {"event": f"e-{rid}", "class": cls},
                "source": {"kind": "evidence", "ref": "d" * 8}}

    def test_export_filters_and_is_deterministic(self):
        root = self.write_store([
            self.rec("r2", "verdict_sealed"),
            self.rec("r1", "skill_verified"),
            self.rec("r3", "finding_high_opened"),
            self.rec("r4", "mission_ratified"),
        ])
        out1 = Path(self.tmp.name) / "o1.jsonl"
        out2 = Path(self.tmp.name) / "o2.jsonl"
        n1, d1 = ss.export_ratification_batch(root, out1)
        n2, d2 = ss.export_ratification_batch(root, out2)
        self.assertEqual(n1, 3)
        self.assertEqual((n1, d1), (n2, d2))
        ids = [json.loads(l)["id"]
               for l in out1.read_text().splitlines()]
        self.assertEqual(ids, ["r1", "r2", "r4"])

    def test_flush_empty_batch_is_recorded_noop(self):
        root = self.write_store([self.rec("r9", "finding_high_opened")])
        self.arm_marker()
        runner = FakeRunner()
        result = ss.flush(root, self.repo, self.home, today=TODAY,
                          runner=runner)
        self.assertFalse(result.sent)
        self.assertEqual(result.reason, "no_ratification_records")
        self.assertEqual(runner.calls, [])

    def test_flush_sends_batch_as_draft(self):
        root = self.write_store([self.rec("r1", "verdict_sealed")])
        self.arm_marker()
        runner = FakeRunner()
        result = ss.flush(root, self.repo, self.home, today=TODAY,
                          runner=runner)
        self.assertTrue(result.sent, result.reason)
        self.assertEqual(
            result.files,
            ["handover/memory_writeback/"
             "20261116-ratification-batch.jsonl"])
        self.assertIn("--draft", runner.argv_text())


if __name__ == "__main__":
    unittest.main()
