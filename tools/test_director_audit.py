"""Fixture audit direktur pada snapshot Git sintetis."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools._director_sources import GitSnapshot, SourceError
from tools.director_asset_check import verify_assets
from tools.director_cycle_record import record_cycles
from tools.director_value_check import verify_values


TOOLS = Path(__file__).resolve().parent


class DirectorAuditTests(unittest.TestCase):
    def setUp(self):
        workspace = TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name)
        self.git("init", "-q")
        self.git("config", "core.hooksPath", "/dev/null")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True)

    def snapshot(self, files):
        for name, content in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content if isinstance(content, str) else json.dumps(content),
                            encoding="utf-8")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "-qm", "fixture")
        return GitSnapshot(self.root)

    def test_assets_verify_existence_for_every_kind_without_imports(self):
        repo = self.snapshot({
            "code/ace_demo/tool.py": "raise AssertionError('never import')\n\nasync def job(): pass\n",
            "README.md": "# Fixture",
            "prs.json": {"repository": "demo/repo", "pull_requests": [15]},
            "product.json": {"assets": [
                {"kind": "file", "target": "README.md"},
                {"kind": "module", "target": "ace_demo.tool"},
                {"kind": "function", "target": "ace_demo.tool::job"},
                {"kind": "pr", "target": "https://github.com/demo/repo/pull/15"},
                {"kind": "file", "target": "imaginary.py"},
                {"kind": "function", "target": "ace_demo.tool::hallucination"},
                {"kind": "pr", "target": "#99"},
            ]},
        })
        result = verify_assets(repo, "product.json", pr_snapshot_path="prs.json")
        self.assertEqual([row["status"] for row in result["assets"]],
                         ["verified"] * 4 + ["not_found"] * 3)
        self.assertEqual(result["assets"][2]["matches"], ["code/ace_demo/tool.py:3"])
        self.assertEqual(result["commit"], repo.commit)
        self.assertEqual(result["assets"][4]["location"], "/assets/4")

    def test_asset_markdown_reports_pr_without_snapshot_and_ambiguous_names(self):
        repo = self.snapshot({
            "tools/check.py": "def job(): pass\n",
            "code/demo/check.py": "def job(): pass\n",
            "product.md": "# Audit\n- `module:check` + tools/check.py + #15\n"
                          "- **Kombinasi aset:** klaim umum + `function:tools/check.py::job`\n",
        })
        rows = verify_assets(repo, "product.md")["assets"]
        actual = {(row["kind"], row["target"]): row["status"] for row in rows}
        self.assertEqual(actual, {
            ("file", "tools/check.py"): "verified",
            ("module", "check"): "ambiguous",
            ("pr", "#15"): "ambiguous",
            ("label", "klaim umum"): "ambiguous",
            ("function", "tools/check.py::job"): "verified",
        })

    def test_snapshot_reads_track_content_and_does_not_follow_symlinks(self):
        (self.root / "linked.py").symlink_to("/outside.py")
        repo = self.snapshot({
            "task.py": "def real(): pass\n",
            "product.json": {"assets": [
                {"kind": "function", "target": "task.py::real"},
                {"kind": "function", "target": "task.py::dirty"},
                {"kind": "file", "target": "linked.py"},
                {"kind": "file", "target": "../outside.py"},
            ]},
        })
        (self.root / "task.py").write_text("def dirty(): pass\n", encoding="utf-8")
        states = [row["status"] for row in verify_assets(repo, "product.json")["assets"]]
        self.assertEqual(states, ["verified", "not_found", "ambiguous", "ambiguous"])

    def test_numeric_values_compare_decimals_and_follow_escaped_pointers(self):
        repo = self.snapshot({
            "numbers.json": '{"a/b": [{"x~y": 0.300000000000000000001}], "yes": true}',
            "product.json": """{"numeric_claims": [
                {"label":"exact","source":"numbers.json","pointer":"/a~1b/0/x~0y","value":0.300000000000000000001},
                {"label":"round","source":"numbers.json","pointer":"/a~1b/0/x~0y","value":0.3},
                {"label":"missing","source":"numbers.json","pointer":"/missing","value":4},
                {"label":"bool","source":"numbers.json","pointer":"/yes","value":1},
                {"label":"file","source":"missing.json","pointer":"/count","value":1}
            ]}""",
        })
        claims = verify_values(repo, "product.json")["claims"]
        self.assertEqual([row["status"] for row in claims],
                         ["verified", "mismatch", "not_found", "ambiguous", "not_found"])
        self.assertEqual(claims[0]["observed"], "0.300000000000000000001")

    def test_numeric_claim_validation_rejects_invalid_pointer_and_number(self):
        repo = self.snapshot({
            "number.json": {"n": 123},
            "product.json": {"numeric_claims": [{
                "label": "claim", "value": 123, "source": "number.json", "pointer": "/~x",
            }]},
            "bad.json": '{"numeric_claims":[{"label":"bad","value":NaN}]}',
        })
        with self.assertRaisesRegex(SourceError, "Pointer|pointer"):
            verify_values(repo, "product.json")
        with self.assertRaisesRegex(SourceError, "berhingga"):
            verify_values(repo, "bad.json")

    def test_cycles_use_existing_cycle_fields_and_flag_legacy_gaps(self):
        repo = self.snapshot({
            "old.json": {"cycle": 1, "status": "accepted", "proposals": [{}],
                         "raw_reply": "ignore this"},
            "new.json": {"cycle": 2, "status": "accepted", "origin": "brain_fixture",
                         "decisions": [{"id": "task-42", "decision": "deferred"}]},
        })
        result = record_cycles(repo, ["new.json", "old.json"])
        old, new = result["cycles"]
        self.assertEqual((old["cycle"], new["cycle"]), (1, 2))
        self.assertEqual(old["issues"], ["missing_origin", "missing_decisions"])
        self.assertIsNone(old["origin"])
        self.assertEqual(old["decisions"], [])
        self.assertNotIn("raw_reply", old)
        self.assertEqual(new["origin"], "brain_fixture")
        self.assertEqual(new["source"], "new.json")
        self.assertEqual(new["decisions"], [{"id": "task-42", "decision": "deferred",
                                            "source_pointer": "/decisions/0"}])
        self.assertEqual(new["issues"], [])
        with self.assertRaisesRegex(SourceError, "unik"):
            record_cycles(repo, ["new.json", "new.json"])

    def test_cli_reads_pinned_git_source_and_leaves_fixture_clean(self):
        repo = self.snapshot({
            "numbers.json": {"count": 2},
            "product.md": ('# Catatan\n- claim: '
                           '{"label":"count","value":2,"source":"numbers.json","pointer":"/count"}\n'),
        })
        raw = subprocess.check_output([sys.executable, str(TOOLS / "director_value_check.py"),
                                       "product.md", "--repo", str(self.root),
                                       "--revision", repo.commit], cwd=self.root)
        row, = json.loads(raw)["claims"]
        self.assertEqual(row["location"], "L2")
        self.assertEqual(row["status"], "verified")
        self.assertEqual(self.git("status", "--porcelain"), "")


if __name__ == "__main__":
    unittest.main()
