"""Smoke test tingkat-dasar untuk tools/ace_real_world_cli.py (batch AG24)."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import ace_real_world_cli


SCRIPT = Path(__file__).resolve().with_name("ace_real_world_cli.py")


class AceRealWorldCliSmokeTests(unittest.TestCase):
    def test_import_help_and_no_args_exit_zero(self) -> None:
        self.assertTrue(callable(ace_real_world_cli.main))
        for flag in (("--help",), ()):
            with self.subTest(flag=flag):
                proc = subprocess.run(
                    [sys.executable, str(SCRIPT), *flag],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn("audit-repo", proc.stdout)

    def test_core_parse_log_demo_and_audit_repo_on_fixture(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "parse-log-demo"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Synthesized Pattern:", proc.stdout)
        self.assertIn("Captured Fields:", proc.stdout)

        with TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / "tools").mkdir(parents=True)
            (repo / "tools" / "sample.py").write_text("def hello():\n    return 1\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "add", "tools/sample.py"], check=True, capture_output=True)
            subprocess.run(
                [
                    "git", "-C", str(repo),
                    "-c", "user.name=Fixture",
                    "-c", "user.email=fixture@example.invalid",
                    "-c", "commit.gpgsign=false",
                    "commit", "-q", "-m", "fixture",
                ],
                check=True,
                capture_output=True,
            )

            buf = StringIO()
            with patch.object(ace_real_world_cli, "ROOT_DIR", repo), \
                    patch.object(sys, "argv", [str(SCRIPT), "audit-repo"]), \
                    redirect_stdout(buf):
                ace_real_world_cli.main()
            self.assertIn("ACE REPOSITORY ARCHITECTURE METRICS", buf.getvalue())
            self.assertIn("Total Python Files:   1", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
