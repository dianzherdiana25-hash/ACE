"""Verifier cakupan nyata dari unittest sandbox termasuk modul dingin."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import coverage_tracker
from ace_software_factory._contracts import ContractError,identity
from ace_software_factory.build_loop import _description
from ace_software_factory.repo_scaffolder import materialize


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(TemporaryDirectory()))/"source"
        self.files={"ready.py":b"def result(flag):\n    if flag:\n        return 4\n    return -2\n",
                    "unused.py":b"def never_used():\n    return 9\n",
                    "tests/test_data.py":b"import unittest\nfrom ready import result\nclass Fixture(unittest.TestCase):\n"
                                         b"    def test_one(self):\n        self.assertEqual(result(True),4)\n"}
        materialize(self.root,self.files)
        self.raw={"schema":"ace.factory-coverage-plan.v1","source_ref":"fixture/tests",
                  "files":_description(self.files),"modules":["unused.py","ready.py"],
                  "expected_tests":1,"timeout_seconds":5}

    def measure(self):
        return coverage_tracker.track(self.root,self.raw,identity(self.raw))

    def test_sandbox_captures_used_branch_without_hiding_unused_module(self):
        report=self.measure()
        if report["status"]=="sandbox_unavailable":
            self.skipTest("bubblewrap atau user namespaces tidak tersedia")
        self.assertEqual(report["status"],"measured")
        live,cold=report["modules"]
        self.assertEqual((live["path"],live["covered"],live["missing_lines"]),("ready.py",3,[4]))
        self.assertEqual((cold["path"],cold["ratio_bp"]),("unused.py",0))
        self.assertEqual(report["test_count"],1)

    def test_refuses_missing_module_and_holds_mismatch_number_of_tests(self):
        self.raw["expected_tests"]=2
        report=self.measure()
        if report["status"]=="sandbox_unavailable":
            self.skipTest("bubblewrap atau user namespaces tidak tersedia")
        self.assertEqual(report["status"],"tests_failed")
        self.raw["modules"].append("absent.py")
        with self.assertRaisesRegex(ContractError,"terdaftar"):
            self.measure()
