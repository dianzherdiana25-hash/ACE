"""Reproduksi bug fixture sebelum memperbaiki satu literal dan uji lagi."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import bug_fixer
from ace_software_factory._contracts import ContractError, identity
from ace_software_factory.build_loop import _description, _runner
from ace_software_factory.repo_scaffolder import materialize


class BugFixTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory())) / "source"
        self.code = 'def capacity():\n    return {"ruáng": 2}\n'.encode()
        self.files = {"capacity.py": self.code, "tests/test_capacity.py": b'''import unittest
from capacity import capacity

class Capacity(unittest.TestCase):
    def test_count(self):
        self.assertEqual(next(iter(capacity().values())), 3)

    def test_shape(self):
        self.assertEqual(len(capacity()), 1)
'''}
        materialize(self.root, self.files)
        self.report = {"schema": "ace.factory-bug-report.v1", "source_ref": "fixture/bug",
                       "files": _description(self.files), "regression_test": "test_capacity.Capacity.test_count",
                       "expected_tests": 2, "timeout_seconds": 6,
                       "change": {"path": "capacity.py", "source_sha256": sha256(self.code).hexdigest(),
                                  "line": 2, "column": self.code.splitlines()[1].index(b"2"), "before": 2, "after": 3}}

    def test_exact_failure_then_repair_with_original_source_unchanged(self):
        files, audit = bug_fixer.fix(self.root, self.report, identity(self.report))
        if audit["before"]["status"] == "sandbox_unavailable":
            self.skipTest("bubblewrap atau user namespaces tidak tersedia")
        self.assertEqual(audit["status"], "verified_repair")
        self.assertEqual(audit["before"]["failures"], ["test_capacity.Capacity.test_count"])
        self.assertEqual(audit["after"]["tests"], 2)
        self.assertEqual(files["capacity.py"], self.code.replace(b"2", b"3"))
        self.assertEqual((self.root / "capacity.py").read_bytes(), self.code)

    def test_unrelated_failure_or_remaining_red_tests_holds_artifact(self):
        other = lambda target, timeout: {"status": "failed", "failures": ["test_other.Test.test_no"], "tests": 2}
        payload, audit = bug_fixer.fix(self.root, self.report, identity(self.report), runner=other)
        self.assertIsNone(payload)
        self.assertIsNone(audit["after"])
        self.assertEqual(audit["status"], "not_reproduced")
        expected = lambda target, timeout: {"status": "failed", "failures": [self.report["regression_test"]], "tests": 2}
        payload, audit = bug_fixer.fix(self.root, self.report, identity(self.report), runner=expected)
        self.assertIsNone(payload)
        self.assertEqual(audit["status"], "repair_unverified")

    def test_verifier_files_are_immutable_and_skipped_suite_is_not_green(self):
        self.report["change"]["path"] = "tests/test_capacity.py"
        with self.assertRaisesRegex(ContractError, "file Python produk"):
            bug_fixer.fix(self.root, self.report, identity(self.report))
        path = self.root.parent / "skipped"
        materialize(path, {"tests/test_empty.py": b'''import unittest
class AllSkipped(unittest.TestCase):
    @unittest.skip("fixture")
    def test_one(self):
        self.fail()
'''})
        result = _runner(path, 6)
        if result["status"] == "sandbox_unavailable":
            self.skipTest("bubblewrap atau user namespaces tidak tersedia")
        self.assertEqual((result["status"], result["tests"], result["skipped"]), ("no_tests", 1, 1))
