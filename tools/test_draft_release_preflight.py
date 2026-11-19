import copy
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.draft_release_preflight import prepare, validate


class DraftPreflightTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture author")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", "/dev/null")
        self.git("commit", "-qm", "base", "--allow-empty")
        self.base = self.git("rev-parse", "HEAD")
        self.repository = "fixture/ace"
        self.branch = "ace-auto/20261118-fixture"

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True).strip()

    def commit(self, path, data):
        destination = self.root / path
        destination.parent.mkdir(exist_ok=True, parents=True)
        destination.write_bytes(data)
        self.git("add", "--", path)
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def prepare(self, head, **options):
        params = dict(repository=self.repository, branch=self.branch, base=self.base, head=head)
        return prepare(self.root, **(params | options))

    def validate(self, envelope):
        return validate(self.root, envelope, repository=self.repository, base=self.base)

    def test_roundtrip_reports_review_only(self):
        head = self.commit("handover/note.txt", b"synthetic\n")
        envelope = self.prepare(head)
        report = self.validate(envelope)
        self.assertTrue(report["ready_for_human_review"])
        self.assertIs(report["send_authorized"], False)
        self.assertEqual(envelope["files"][0]["bytes"], 10)

    def test_forged_source_binding_and_flags_rejected(self):
        envelope = self.prepare(self.commit("handover/note.txt", b"synthetic"))
        for field, value in (("draft", 1), ("human_approval_required", False), ("repository", "other/ace")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.validate(envelope | {field: value})
        changed = copy.deepcopy(envelope)
        changed["files"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "pinned local diff"):
            self.validate(changed)

    def test_ineligible_changed_path_rejected(self):
        head = self.commit("code/fixture.py", b"pass\n")
        with self.assertRaisesRegex(ValueError, "outside offline"):
            self.prepare(head)

    def test_invalid_branch_and_wrong_ancestry_rejected(self):
        first = self.commit("handover/note.txt", b"first")
        with self.assertRaises(ValueError):
            self.prepare(first, branch="ace-auto/20260230-fixture")
        self.git("checkout", "--detach", self.base)
        second = self.commit("handover/other.txt", b"second")
        with self.assertRaisesRegex(ValueError, "merge-base"):
            self.prepare(second, base=first)

    def test_symlink_is_not_an_eligible_blob(self):
        folder = self.root / "evidence"
        folder.mkdir()
        (folder / "link").symlink_to("missing")
        self.git("add", "--", "evidence/link")
        self.git("commit", "-qm", "link")
        with self.assertRaisesRegex(ValueError, "ordinary file"):
            self.prepare(self.git("rev-parse", "HEAD"))
