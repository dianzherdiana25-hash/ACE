"""Cek stabilitas nama laporan saat nama checkout berbeda dari remote."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.repo_status_dashboard import collect_repo_status
from tools.wiring_audit import audit_wiring


class ReportRepoNameTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory())) / "checkout-berbeda"
        self.root.mkdir()

    def git(self, *argv):
        subprocess.run(["git", "-C", str(self.root), *argv], check=True, capture_output=True)

    def check_name(self, expected):
        self.assertEqual(audit_wiring(self.root)["repo_name"], expected)
        self.assertEqual(collect_repo_status(self.root)["repo_name"], expected)

    def test_origin_name_for_checkout_using_gitfile(self):
        self.git("init", "-q", "--separate-git-dir", str(self.root.parent / "git-metadata"))
        self.git("remote", "add", "origin", "https://example.invalid/owner/Repo-Kanon.git")
        self.check_name("Repo-Kanon")

        tools_dir = Path(__file__).resolve().parent
        result = subprocess.run(
            [sys.executable, str(tools_dir / "wiring_audit.py"), "--root", str(self.root), "--format", "json"],
            check=True, capture_output=True, text=True, cwd=self.root,
        )
        self.assertEqual(json.loads(result.stdout)["repo_name"], "Repo-Kanon")

    def test_scp_remote_without_namespace(self):
        self.git("init", "-q")
        self.git("remote", "add", "origin", "git@example.invalid:Repo-Ssh.git")
        self.check_name("Repo-Ssh")

    def test_directory_fallback_without_git_or_origin(self):
        self.check_name(self.root.name)
        self.git("init", "-q")
        self.check_name(self.root.name)


if __name__ == "__main__":
    unittest.main()
