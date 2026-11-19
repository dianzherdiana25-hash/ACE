"""Tests for ace_operational.self_send (governed self-send).

The governance is the product: marker gate, branch namespace,
path allowlist/denylist, non-force push, draft-only PRs,
duplicate refusal, fail-closed audit. A scripted fake runner
stands in for git/gh so every argv is inspectable; no network,
no real remote, no credentials anywhere near these tests.

TestRealGit goes further: a REAL git index in a temp repo.
Transport reaches a local bare repo through a GIT_SSH_COMMAND
pipe, so the origin keeps its true ACE identity
(git@github.com:...) and `git remote get-url` tells the
truth. Only the network pipe and `gh` are stubbed — NOTHING
about the mechanism under test (URL gates, the module's own
fetch refspec, the controlled basis ref, push refspecs, tag
behaviour) is stubbed or rewritten. (Round 3's harness
rewrote the fetch verb itself and thereby hid the basis
poisoning the reviewer later proved; that seam is gone.)
"""
import json
import os
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path

from ace_operational import self_send as ss

TODAY = date(2026, 11, 16)
PR_URL = "https://github.com/dianzherdiana25-hash/ACE/pull/999"
ACE_HTTPS = "https://github.com/dianzherdiana25-hash/ACE.git"


class FakeRunner:
    """Scripted git/gh stand-in for the gate tests. Stateful
    in exactly one place: it remembers the paths of the last
    `git add` so `git diff --cached --name-only` can answer
    like a real index (the module verifies the staged set).

    URL gates (round 4): the module asks git itself via
    `git remote get-url [--push] --all origin`; the fake
    answers with fetch_urls / push_urls verbatim (default:
    the configured origin for both)."""

    def __init__(self, *, auth_ok=True, branch_local=False,
                 branch_remote=False, fail_at=None,
                 origin=ACE_HTTPS, dirty=False,
                 fetch_urls=None, push_urls=None, fail_on=None):
        self.calls = []
        self.auth_ok = auth_ok
        self.branch_local = branch_local
        self.branch_remote = branch_remote
        self.fail_at = fail_at
        self.origin = origin
        self.dirty = dirty
        self.fetch_urls = fetch_urls
        self.push_urls = push_urls
        self.fail_on = fail_on
        self._needle_count = 0
        self.staged = []
        self.all_staged = set()

    def __call__(self, argv, cwd):
        self.calls.append(list(argv))
        joined = " ".join(argv)
        if self.fail_on and self.fail_on[0] in joined:
            self._needle_count += 1
            if self._needle_count == self.fail_on[1]:
                return 1, "", "injected nth failure"
        if self.fail_at and self.fail_at in joined:
            return 1, "", f"injected failure at {self.fail_at}"
        if argv[:3] == ["gh", "auth", "status"]:
            return (0, "", "") if self.auth_ok else (1, "", "no auth")
        if argv[:5] == ["git", "remote", "get-url", "--push",
                        "--all"]:
            urls = self.push_urls
            if urls is None:
                urls = self.fetch_urls
            if urls is None:
                urls = [self.origin]
            return 0, "".join(u + "\n" for u in urls), ""
        if argv[:4] == ["git", "remote", "get-url", "--all"]:
            urls = self.fetch_urls
            if urls is None:
                urls = [self.origin]
            return 0, "".join(u + "\n" for u in urls), ""
        if argv[:3] == ["git", "status", "--porcelain"]:
            return 0, (" M junk.txt\n" if self.dirty else ""), ""
        if argv[:2] == ["git", "add"]:
            self.staged = sorted(argv[argv.index("--") + 1:])
            self.all_staged.update(self.staged)
            return 0, "", ""
        if argv[:4] == ["git", "diff", "--cached", "--name-only"]:
            return 0, "".join(p + "\n" for p in self.staged), ""
        if argv[:3] == ["git", "diff", "--name-only"] and \
                any(".." in a for a in argv):
            return 0, "".join(
                p + "\n" for p in sorted(self.all_staged)), ""
        if argv[:2] == ["git", "merge-base"]:
            return 0, "abc123\n", ""
        if argv[:2] == ["git", "rev-parse"]:
            if "refs/ace-self-send/base" in joined:
                return 0, "abc123\n", ""
            if "refs/remotes/origin/main" in joined:
                return 0, "abc123\n", ""
            if "refs/heads/main" in joined:
                return 0, "abc\n", ""
            return (0, "abc\n", "") if self.branch_local \
                else (1, "", "")
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

    def test_wrong_origin_refuses(self):
        self.arm_marker()
        runner = FakeRunner(
            origin="https://github.com/someone/else.git")
        result = self.send(runner)
        self.assertEqual(result.reason, "fetch_target_mismatch")
        self.assertFalse((self.repo / "handover/NOTE.md").exists())

    def test_dirty_worktree_refuses(self):
        self.arm_marker()
        result = self.send(FakeRunner(dirty=True))
        self.assertEqual(result.reason, "worktree_dirty")

    def test_runner_exception_is_audited(self):
        self.arm_marker()

        def boom(argv, cwd):
            if argv[:2] == ["git", "remote"]:
                raise TimeoutError("simulated timeout")
            return FakeRunner()(argv, cwd)

        result = self.send(boom)
        self.assertFalse(result.sent)
        self.assertTrue(result.reason.startswith("error:"))
        self.assertEqual(self.audit_rows()[-1]["outcome"],
                         "error:TimeoutError")

    def test_pushurl_redirect_refuses(self):
        # Round-3 regression 1a / round-4 gate: the push URL
        # list (git's own answer) points elsewhere.
        self.arm_marker()
        runner = FakeRunner(push_urls=["/tmp/evil-bare.git"])
        result = self.send(runner)
        self.assertFalse(result.sent)
        self.assertEqual(result.reason, "push_target_mismatch")
        self.assertNotIn("git push", runner.argv_text())

    def test_fetch_redirect_refuses(self):
        # Round-4: the FETCH target is validated too — an
        # insteadOf-style rewrite of the fetch URL must refuse
        # before any fetch happens.
        self.arm_marker()
        runner = FakeRunner(fetch_urls=["/tmp/evil-bare.git"])
        result = self.send(runner)
        self.assertFalse(result.sent)
        self.assertEqual(result.reason, "fetch_target_mismatch")
        self.assertNotIn("git fetch", runner.argv_text())
        self.assertNotIn("git push", runner.argv_text())

    def test_multi_valued_push_url_refuses(self):
        # Round-4 regression: origin.url is multi-valued; the
        # first value is ACE, the second is not. Validating
        # only the first (the old urls[:1] slice) let the
        # second become a push target.
        self.arm_marker()
        runner = FakeRunner(push_urls=[
            ACE_HTTPS, "https://evil.example/x.git"])
        result = self.send(runner)
        self.assertFalse(result.sent)
        self.assertEqual(result.reason, "push_target_mismatch")
        self.assertNotIn("git push", runner.argv_text())

    def test_multi_valued_fetch_url_refuses(self):
        self.arm_marker()
        runner = FakeRunner(fetch_urls=[
            ACE_HTTPS, "https://evil.example/x.git"])
        result = self.send(runner)
        self.assertFalse(result.sent)
        self.assertEqual(result.reason, "fetch_target_mismatch")
        self.assertNotIn("git fetch", runner.argv_text())

    def test_finalize_push_failure_is_not_sent(self):
        # Round-3 plus: the PR exists, but the final audit push
        # failed — partial success must not read as sent.
        self.arm_marker()
        runner = FakeRunner(fail_on=("git push", 2))
        result = self.send(runner)
        self.assertFalse(result.sent)
        self.assertEqual(result.reason, "audit_finalize_failed")
        self.assertEqual(result.pr_number, 999)
        self.assertEqual(self.audit_rows()[-1]["outcome"],
                         "sent_audit_finalize_failed")


class TestHappyPath(SelfSendCase):
    def test_send_creates_draft_pr_without_force(self):
        self.arm_marker()
        runner = FakeRunner()
        result = self.send(runner)
        self.assertTrue(result.sent, result.reason)
        self.assertEqual(result.branch,
                         "ace-auto/20261116-test-note")
        self.assertEqual(result.pr_number, 999)
        text = runner.argv_text()
        self.assertIn("--draft", text)
        self.assertIn("--repo dianzherdiana25-hash/ACE", text)
        self.assertNotIn("--force", text)
        # Round 4: every push carries --no-follow-tags and a
        # full branch-to-branch refspec.
        pushes = [c for c in runner.calls
                  if c[:2] == ["git", "push"]]
        self.assertTrue(pushes)
        for call in pushes:
            self.assertIn("--no-follow-tags", call)
            self.assertIn(
                "refs/heads/ace-auto/20261116-test-note:"
                "refs/heads/ace-auto/20261116-test-note", call)
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
        root.mkdir(exist_ok=True)
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
        n1, d1, ids1 = ss.export_ratification_batch(root, out1)
        n2, d2, _ids2 = ss.export_ratification_batch(root, out2)
        self.assertEqual(n1, 3)
        self.assertEqual((n1, d1), (n2, d2))
        self.assertEqual(ids1, ["r1", "r2", "r4"])
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

    def test_flush_without_marker_writes_no_staging(self):
        root = self.write_store([self.rec("r1", "verdict_sealed")])
        runner = FakeRunner()
        result = ss.flush(root, self.repo, self.home, today=TODAY,
                          runner=runner)
        self.assertEqual(result.reason, "marker_absent")
        self.assertEqual(runner.calls, [])
        self.assertFalse((self.home / "self_send_staging").exists())
        self.assertEqual(self.audit_rows()[-1]["outcome"],
                         "refused:marker_absent")

    def test_flush_dedups_acked_records(self):
        root = self.write_store([self.rec("r1", "verdict_sealed")])
        self.arm_marker()
        first = ss.flush(root, self.repo, self.home, today=TODAY,
                         runner=FakeRunner())
        self.assertTrue(first.sent, first.reason)
        acked = json.loads(
            (self.home / ss.ACK_NAME).read_text())
        self.assertIn("r1", acked)
        second = ss.flush(root, self.repo, self.home, today=TODAY,
                          runner=FakeRunner())
        self.assertEqual(second.reason, "no_ratification_records")

    def test_flush_second_batch_same_day_takes_suffix(self):
        root = self.write_store([self.rec("r1", "verdict_sealed")])
        self.arm_marker()
        first = ss.flush(root, self.repo, self.home, today=TODAY,
                         runner=FakeRunner())
        self.assertTrue(first.sent, first.reason)
        self.assertTrue(first.branch.endswith("memory-writeback"))
        root = self.write_store([self.rec("r1", "verdict_sealed"),
                                 self.rec("r2", "skill_verified")])
        second = ss.flush(root, self.repo, self.home, today=TODAY,
                          runner=FakeRunner())
        self.assertTrue(second.sent, second.reason)
        self.assertTrue(
            second.branch.endswith("memory-writeback-2"),
            second.branch)
        self.assertEqual(
            second.files,
            ["handover/memory_writeback/"
             "20261116-ratification-batch.jsonl"])

    def test_flush_corrupt_store_is_audited(self):
        # Round-3 regression 4: a corrupt memory.jsonl used to
        # raise out of flush() with no audit row at all.
        root = Path(self.tmp.name) / "memory"
        root.mkdir(exist_ok=True)
        (root / "memory.jsonl").write_text("{not json\n")
        self.arm_marker()
        runner = FakeRunner()
        result = ss.flush(root, self.repo, self.home, today=TODAY,
                          runner=runner)
        self.assertFalse(result.sent)
        self.assertTrue(result.reason.startswith("error:"),
                        result.reason)
        self.assertTrue(self.audit_rows()[-1]["outcome"].startswith(
            "error:"))
        self.assertNotIn("git push", runner.argv_text())

    def test_flush_corrupt_ack_refuses_audited(self):
        # Round-3 plus: a corrupt ack file must NOT be read as
        # an empty ack set (that would re-send everything).
        root = self.write_store([self.rec("r1", "verdict_sealed")])
        self.arm_marker()
        (self.home / ss.ACK_NAME).write_text("garbage{{{")
        runner = FakeRunner()
        result = ss.flush(root, self.repo, self.home, today=TODAY,
                          runner=runner)
        self.assertFalse(result.sent)
        self.assertTrue(result.reason.startswith("error:"),
                        result.reason)
        self.assertNotIn("git push", runner.argv_text())


FAKE_SSH = '''#!/usr/bin/env python3
"""Test transport pipe: git invokes the ssh command with
git-(upload|receive)-pack '<path>' as the last argument; map
the path onto the local bare under ACE_TEST_BARE_ROOT and
exec the real git service. Only the network pipe is faked.
"""
import os
import re
import sys

m = re.match(r"(git-(?:upload|receive)-pack) '([^']+)'",
             sys.argv[-1])
if not m:
    sys.exit(255)
bare = os.path.join(os.environ["ACE_TEST_BARE_ROOT"],
                    os.path.basename(m.group(2)))
os.execvp(m.group(1), [m.group(1), bare])
'''


def _git(cwd, *args, env=None):
    full_env = None
    if env is not None:
        full_env = {**os.environ, **env}
    proc = subprocess.run(["git", *args], cwd=str(cwd),
                          capture_output=True, text=True,
                          env=full_env)
    if proc.returncode != 0:
        raise AssertionError(
            f"git {args} failed: {proc.stderr.strip()}")
    return proc.stdout


class PipeRunner:
    """Real git via subprocess; stubbed gh. Transport goes
    through the GIT_SSH_COMMAND pipe onto a local bare repo,
    so origin keeps its true ACE identity and every git
    mechanism the module relies on runs for real."""

    def __init__(self, bare_root, ssh_script):
        self.env = {"GIT_SSH_COMMAND": str(ssh_script),
                    "ACE_TEST_BARE_ROOT": str(bare_root)}

    def __call__(self, argv, cwd):
        if argv[0] == "gh":
            if argv[:3] == ["gh", "auth", "status"]:
                return 0, "", ""
            if argv[:3] == ["gh", "pr", "create"]:
                return 0, PR_URL + "\n", ""
            if argv[:3] == ["gh", "pr", "view"]:
                return 0, json.dumps({
                    "number": 999, "url": PR_URL,
                    "state": "OPEN", "isDraft": True}), ""
            return 0, "", ""
        proc = subprocess.run(
            argv, cwd=str(cwd), capture_output=True, text=True,
            env={**os.environ, **self.env})
        return proc.returncode, proc.stdout, proc.stderr


class TestRealGit(unittest.TestCase):
    ACE_URL = "git@github.com:dianzherdiana25-hash/ACE.git"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.home = root / "home"
        self.home.mkdir()
        (self.home / ss.MARKER_NAME).write_text("enabled\n")
        self.ssh_script = root / "fakessh.py"
        self.ssh_script.write_text(FAKE_SSH)
        self.ssh_script.chmod(0o755)
        self.bare_root = root / "bares"
        self.bare_root.mkdir()
        self.bare = self.bare_root / "ACE.git"
        _git(root, "init", "--bare", "-b", "main", str(self.bare))
        self.pipe_env = {"GIT_SSH_COMMAND": str(self.ssh_script),
                         "ACE_TEST_BARE_ROOT": str(self.bare_root)}
        self.repo = root / "repo"
        _git(root, "init", "-b", "main", str(self.repo))
        _git(self.repo, "config", "user.name", "Test")
        _git(self.repo, "config", "user.email", "test@local")
        (self.repo / "README.md").write_text("base\n")
        _git(self.repo, "add", "README.md")
        _git(self.repo, "commit", "-m", "base")
        _git(self.repo, "remote", "add", "origin", self.ACE_URL)
        _git(self.repo, "push", "origin", "main", env=self.pipe_env)
        self.runner = PipeRunner(self.bare_root, self.ssh_script)

    def tearDown(self):
        self.tmp.cleanup()

    def send(self, **kw):
        kw.setdefault("slug", "real")
        kw.setdefault("trigger", "manual_cli")
        kw.setdefault("today", TODAY)
        kw.setdefault("runner", self.runner)
        kw.setdefault("files", {"handover/NOTE.md": b"# note\n"})
        return ss.send(self.repo, self.home, **kw)

    def tree(self, ref):
        return _git(self.repo, "ls-tree", "-r", "--name-only",
                    ref).splitlines()

    def bare_refs(self, bare=None):
        return _git(bare or self.bare, "for-each-ref",
                    "--format=%(refname)")

    def bare_tip(self):
        return _git(self.bare, "rev-parse", "main").strip()

    def test_real_send_end_to_end(self):
        result = self.send()
        self.assertTrue(result.sent, result.reason)
        branch = "ace-auto/20261116-real"
        self.assertEqual(result.branch, branch)
        names = self.tree(branch)
        self.assertIn("handover/NOTE.md", names)
        self.assertIn(ss.AUDIT_REPO_PATH, names)
        audit = _git(self.repo, "show",
                     f"{branch}:{ss.AUDIT_REPO_PATH}")
        rows = [json.loads(l) for l in audit.splitlines()]
        self.assertEqual(rows[0]["outcome"], "prepared")
        self.assertEqual(rows[-1]["outcome"], "sent")
        self.assertEqual(rows[-1]["pr_number"], 999)
        self.assertIn(f"refs/heads/{branch}", self.bare_refs())
        self.assertNotIn("refs/tags/", self.bare_refs())
        self.assertEqual(
            _git(self.repo, "branch", "--show-current").strip(),
            "main")
        self.assertEqual(
            _git(self.repo, "status", "--porcelain"), "")

    def test_real_head_non_main_still_bases_on_main(self):
        _git(self.repo, "checkout", "-b", "feature")
        (self.repo / "feature.txt").write_text("f\n")
        _git(self.repo, "add", "feature.txt")
        _git(self.repo, "commit", "-m", "feature work")
        result = self.send()
        self.assertTrue(result.sent, result.reason)
        self.assertNotIn("feature.txt", self.tree(result.branch))
        base = _git(self.repo, "merge-base",
                    "refs/ace-self-send/base",
                    result.branch).strip()
        self.assertEqual(base, self.bare_tip())
        self.assertEqual(
            _git(self.repo, "branch", "--show-current").strip(),
            "feature")

    def test_real_wrong_origin_refused(self):
        _git(self.repo, "remote", "set-url", "origin",
             "git@github.com:someone/else.git")
        result = self.send()
        self.assertEqual(result.reason, "fetch_target_mismatch")
        self.assertFalse((self.repo / "handover/NOTE.md").exists())
        self.assertEqual(
            _git(self.repo, "branch", "--list", "ace-auto/*"), "")

    def test_real_dirty_worktree_refused(self):
        (self.repo / "junk.txt").write_text("x\n")
        result = self.send()
        self.assertEqual(result.reason, "worktree_dirty")
        self.assertEqual(
            _git(self.repo, "branch", "--list", "ace-auto/*"), "")

    def test_real_symlink_escape_refused(self):
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (self.repo / "handover").mkdir()
        os.symlink(outside, self.repo / "handover" / "link")
        result = self.send(files={"handover/link/evil.md": b"x"})
        self.assertFalse(result.sent)
        self.assertTrue(result.reason.startswith("governance:"),
                        result.reason)
        self.assertFalse((outside / "evil.md").exists())

    def write_store(self, records):
        root = Path(self.tmp.name) / "memory"
        root.mkdir(exist_ok=True)
        (root / "memory.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in records))
        return root

    def rec(self, rid, cls):
        return {"id": rid, "kind": "semantic",
                "content": {"event": f"e-{rid}", "class": cls},
                "source": {"kind": "evidence", "ref": "d" * 8}}

    def test_real_flush_marker_absent_writes_no_staging(self):
        (self.home / ss.MARKER_NAME).unlink()
        root = self.write_store([self.rec("r1", "verdict_sealed")])
        result = ss.flush(root, self.repo, self.home, today=TODAY,
                          runner=self.runner)
        self.assertEqual(result.reason, "marker_absent")
        self.assertFalse((self.home / "self_send_staging").exists())

    def test_real_flush_dedup_and_suffix(self):
        root = self.write_store([self.rec("r1", "verdict_sealed")])
        first = ss.flush(root, self.repo, self.home, today=TODAY,
                         runner=self.runner)
        self.assertTrue(first.sent, first.reason)
        self.assertTrue(first.branch.endswith("memory-writeback"))
        acked = json.loads((self.home / ss.ACK_NAME).read_text())
        self.assertEqual(acked["r1"]["pr_number"], 999)
        second = ss.flush(root, self.repo, self.home, today=TODAY,
                          runner=self.runner)
        self.assertEqual(second.reason, "no_ratification_records")
        root = self.write_store([self.rec("r1", "verdict_sealed"),
                                 self.rec("r2", "skill_verified")])
        third = ss.flush(root, self.repo, self.home, today=TODAY,
                         runner=self.runner)
        self.assertTrue(third.sent, third.reason)
        self.assertTrue(
            third.branch.endswith("memory-writeback-2"),
            third.branch)
        payload = _git(self.repo, "show",
                       f"{third.branch}:handover/memory_writeback/"
                       "20261116-ratification-batch.jsonl")
        ids = [json.loads(l)["id"]
               for l in payload.splitlines() if l.strip()]
        self.assertEqual(ids, ["r2"])

    def test_real_pushurl_redirect_refuses(self):
        # Honest url, hostile pushurl — git's own get-url
        # answer exposes it; nothing may land anywhere.
        evil = Path(self.tmp.name) / "evil.git"
        _git(Path(self.tmp.name), "init", "--bare", "-b", "main",
             str(evil))
        _git(self.repo, "config", "remote.origin.pushurl",
             str(evil))
        result = self.send()
        self.assertFalse(result.sent)
        self.assertEqual(result.reason, "push_target_mismatch")
        self.assertNotIn("ace-auto", self.bare_refs(evil))
        self.assertNotIn("ace-auto", self.bare_refs())

    def test_real_multi_valued_origin_url_refuses(self):
        # Round-4 regression 1: a second origin.url value is
        # also a push/fetch target for git. Validating only
        # the first value (the old slice) let it through.
        _git(self.repo, "remote", "set-url", "--add", "origin",
             "https://evil.example/x.git")
        result = self.send()
        self.assertFalse(result.sent)
        self.assertEqual(result.reason, "fetch_target_mismatch")
        self.assertNotIn("ace-auto", self.bare_refs())

    def test_real_basis_poison_via_tracking_ref(self):
        # Round-4 regression 2 (the reviewer's real-git
        # probe): refs/remotes/origin/main is poisoned with a
        # synthetic commit carrying private.txt, and the
        # configured fetch refspec does NOT map main — so a
        # plain `git fetch origin main` leaves the poisoned
        # tracking ref in place, and a basis read from it
        # sends the poison. The module must fetch with its
        # OWN explicit refspec into its OWN controlled ref
        # and take the basis from there.
        _git(self.repo, "config", "remote.origin.fetch",
             "+refs/heads/dev:refs/remotes/origin/dev")
        _git(self.repo, "checkout", "-b", "poison")
        (self.repo / "private.txt").write_text("poison\n")
        _git(self.repo, "add", "private.txt")
        _git(self.repo, "commit", "-m", "synthetic poison")
        poison = _git(self.repo, "rev-parse", "HEAD").strip()
        _git(self.repo, "update-ref",
             "refs/remotes/origin/main", poison)
        _git(self.repo, "checkout", "main")
        _git(self.repo, "branch", "-D", "poison")
        result = self.send()
        self.assertTrue(result.sent, result.reason)
        self.assertNotIn("private.txt", self.tree(result.branch))
        base = _git(self.repo, "merge-base",
                    "refs/ace-self-send/base",
                    result.branch).strip()
        self.assertEqual(base, self.bare_tip())
        # The poisoned tracking ref was never consulted: it
        # still holds the poison, untouched by the send.
        self.assertEqual(
            _git(self.repo, "rev-parse",
                 "refs/remotes/origin/main").strip(), poison)

    def test_real_local_main_poison_not_sent(self):
        # A synthetic commit on LOCAL main (never pushed)
        # carries a file outside the allowlist. The basis is
        # fetched, so the poison must not enter the branch.
        (self.repo / "private.txt").write_text("poison\n")
        _git(self.repo, "add", "private.txt")
        _git(self.repo, "commit", "-m", "synthetic poison")
        result = self.send()
        self.assertTrue(result.sent, result.reason)
        self.assertNotIn("private.txt", self.tree(result.branch))
        base = _git(self.repo, "merge-base",
                    "refs/ace-self-send/base",
                    result.branch).strip()
        self.assertEqual(base, self.bare_tip())

    def test_real_followtags_tag_not_sent(self):
        # Round-4 regression 3: with push.followTags=true a
        # plain branch push also sends reachable annotated
        # tags — a local tag carrying a secret canary would
        # leave the ace-auto/* namespace. Every push must
        # carry --no-follow-tags and a full refspec.
        _git(self.repo, "tag", "-a", "private-tag",
             "-m", "SECRET CANARY")
        _git(self.repo, "config", "push.followTags", "true")
        result = self.send()
        self.assertTrue(result.sent, result.reason)
        self.assertNotIn("private-tag", self.bare_refs())
        self.assertNotIn("refs/tags/", self.bare_refs())

    def test_real_committed_symlink_refused_before_write(self):
        # Round-3 regression 3: a symlink committed INTO main
        # (handover/note.md -> ../code/fixture.py) passes the
        # resolved-path check (target still inside the repo)
        # but must be refused before any write touches the
        # fixture.
        (self.repo / "code").mkdir()
        (self.repo / "code" / "fixture.py").write_text(
            "ORIGINAL\n")
        (self.repo / "handover").mkdir()
        os.symlink("../code/fixture.py",
                   self.repo / "handover" / "note.md")
        _git(self.repo, "add", "code/fixture.py",
             "handover/note.md")
        _git(self.repo, "commit", "-m", "plant symlink")
        _git(self.repo, "push", "origin", "main",
             env=self.pipe_env)
        # Rest on the pre-symlink commit: the pre-checkout
        # validation sees no symlink at all — only the
        # post-checkout re-validation (on the fetched basis
        # tree, which carries the symlink) can catch it.
        _git(self.repo, "checkout", "HEAD~1")
        result = self.send(files={"handover/note.md": b"evil\n"})
        self.assertFalse(result.sent)
        self.assertIn("symlink", result.reason)
        self.assertEqual(
            (self.repo / "code" / "fixture.py").read_text(),
            "ORIGINAL\n")
        self.assertNotIn("ace-auto", self.bare_refs())


if __name__ == "__main__":
    unittest.main()
