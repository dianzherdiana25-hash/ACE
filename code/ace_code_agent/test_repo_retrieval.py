"""Public disposable-fixture tests for ACE FR-01 retrieval (not sealed holdouts)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from .repo_retrieval import BoundedRepositoryRetriever


class TestBoundedRepositoryRetriever(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="ace-fr01-")
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.write(".gitignore", "vendor/\n*.secret.py\n")
        self.write("a/noise.py", "# release lock release lock release lock\nVALUE = 2\n")
        self.write("src/lease.py", "import os\nclass LeaseManager:\n    def release_lock(self, token: str) -> bool:\n        return check_owner(token)\n")
        self.write("src/checks.py", "def validate_owner(token: str) -> bool:\n    return bool(token)\n")
        self.write("src/router.py", "async def handle_request(item: str) -> str:\n    return item\n")
        self.write("tests/test_lease.py", "from src.lease import LeaseManager\n")
        self.write("vendor/ignored.py", "def release_lock(): return True\n")
        self.write("hidden.secret.py", "def release_lock(): return True\n")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, path: str, value: str) -> None:
        full = self.root / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(value, encoding="utf-8")

    def build(self, **kwargs):
        return BoundedRepositoryRetriever(self.root, **kwargs).build_index()

    def test_preregistered_three_cases_recall_at_one(self) -> None:
        cases = (
            ("release_lock", "src/lease.py", "LeaseManager.release_lock"),
            ("validate_owner", "src/checks.py", "validate_owner"),
            ("handle_request", "src/router.py", "handle_request"),
        )
        index = self.build()
        for query, path, symbol in cases:
            with self.subTest(query=query):
                results = BoundedRepositoryRetriever.search(index, query, mode="hybrid")
                self.assertTrue(results)
                self.assertEqual(results[0]["path"], path)
                self.assertEqual(results[0]["symbol"]["qualname"], symbol)

    def test_lexical_decoy_and_structural_control(self) -> None:
        index = self.build()
        baseline = BoundedRepositoryRetriever.search(index, "release_lock", mode="lexical")
        structural = BoundedRepositoryRetriever.search(index, "release_lock", mode="structural")
        hybrid = BoundedRepositoryRetriever.search(index, "release_lock", mode="hybrid")
        self.assertEqual(baseline[0]["path"], "a/noise.py")
        self.assertEqual(structural[0]["path"], "src/lease.py")
        self.assertEqual(hybrid[0]["path"], "src/lease.py")
        self.assertEqual(hybrid[0]["structural_score"], 10.0)

    def test_index_contains_signatures_imports_calls_and_lines(self) -> None:
        index = self.build()
        entry = next(f for f in index["files"] if f["path"] == "src/lease.py")
        self.assertIn("os", entry["imports"])
        method = next(s for s in entry["symbols"] if s["name"] == "release_lock")
        self.assertIn("token: str", method["signature"])
        self.assertIn("check_owner", method["calls"])
        self.assertEqual((method["line"], method["end_line"]), (3, 4))

    def test_gitignore_and_depth_limit(self) -> None:
        paths = {f["path"] for f in self.build()["files"]}
        self.assertNotIn("vendor/ignored.py", paths)
        self.assertNotIn("hidden.secret.py", paths)
        shallow = self.build(max_depth=0)
        self.assertEqual(shallow["file_count"], 0)
        self.assertGreater(shallow["skipped"].get("DEPTH_LIMIT", 0), 0)

    def test_file_limit_and_oversize(self) -> None:
        limited = self.build(max_files=1)
        self.assertEqual(limited["files"][0]["path"], "a/noise.py")
        self.assertGreaterEqual(limited["skipped"].get("FILE_LIMIT", 0), 1)
        self.write("large.py", "X = '" + "x" * 500 + "'\n")
        indexed = self.build(max_file_bytes=256)
        self.assertNotIn("large.py", [f["path"] for f in indexed["files"]])
        self.assertGreater(indexed["skipped"].get("FILE_SIZE", 0), 0)

    def test_syntax_error_does_not_execute_file(self) -> None:
        self.write("bad.py", "def broken(:\n")
        self.write("src/evil.py", "raise RuntimeError('must not execute')\ndef risky(): pass\n")
        index = self.build()
        self.assertIn({"path": "bad.py", "error_type": "SyntaxError"}, index["parse_errors"])
        self.assertIn("src/evil.py", [f["path"] for f in index["files"]])

    def test_symlink_outside_repo_is_excluded(self) -> None:
        outside = self.root.parent / (self.root.name + "-outside.py")
        try:
            outside.write_text("def release_lock(): return False\n", encoding="utf-8")
            (self.root / "escaping.py").symlink_to(outside)
            paths = {f["path"] for f in self.build()["files"]}
            self.assertNotIn("escaping.py", paths)
        finally:
            outside.unlink(missing_ok=True)

    def test_repeat_new_index_instance_is_deterministic(self) -> None:
        first = self.build()
        second = self.build()
        first.pop("elapsed_ms")
        second.pop("elapsed_ms")
        self.assertEqual(first, second)

    def test_invalid_limits_and_unsupported_semantic_mode(self) -> None:
        with self.assertRaises(ValueError):
            BoundedRepositoryRetriever(self.root, max_depth=33)
        with self.assertRaises(ValueError):
            BoundedRepositoryRetriever(self.root, max_files=0)
        with self.assertRaises(ValueError):
            BoundedRepositoryRetriever.search(self.build(), "release_lock", mode="semantic")

    def test_cli_output_reports_read_only_status(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
        result = subprocess.run(
            [sys.executable, "-m", "ace_code_agent.repo_retrieval",
             "--repo", str(self.root), "--query", "release_lock", "--limit", "2"],
            check=True, capture_output=True, text=True, timeout=15, env=env,
        )
        data = json.loads(result.stdout)
        self.assertEqual(data["results"][0]["path"], "src/lease.py")
        self.assertEqual(data["provider_calls"], 0)
        self.assertFalse(data["candidate_code_executed"])
        self.assertEqual(data["scientific_status"], "NOT_ASSESSED")


if __name__ == "__main__":
    unittest.main()
