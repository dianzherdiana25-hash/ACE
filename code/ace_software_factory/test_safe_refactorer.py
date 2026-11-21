"""Verifier binding privat pada snapshot, tanpa mengubah checkout fixture."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import safe_refactorer
from ace_software_factory._contracts import ContractError, identity
from ace_software_factory.build_loop import _description
from ace_software_factory.repo_scaffolder import materialize


class RefactorTests(unittest.TestCase):
    def setUp(self):
        self.destination = Path(self.enterContext(TemporaryDirectory())) / "source"
        self.files = {"app.py": b"def _total(value):\n    return value + 2\n\ndef run(value):\n    return _total(value)\n",
                      "tests/test_app.py": b'''import unittest
from app import run
class Product(unittest.TestCase):
    def test_total(self):
        self.assertEqual(run(4), 6)
'''}

    def run_fixture(self):
        materialize(self.destination, self.files)
        plan = {"schema": "ace.factory-refactor-plan.v1", "source_ref": "fixture/refactor",
                "files": _description(self.files), "path": "app.py", "old": "_total", "new": "_add_offset",
                "timeout_seconds": 5, "test_count": 1}
        return safe_refactorer.refactor(self.destination, plan, identity(plan))

    def test_renamed_def_and_call_preserve_fixture_behavior_in_sandbox(self):
        output, report = self.run_fixture()
        if report["before"]["status"] == "sandbox_unavailable":
            self.skipTest("bubblewrap atau user namespaces tidak tersedia")
        self.assertEqual(report["name_changes"], 2)
        self.assertEqual(report["status"], "verified_refactor")
        self.assertEqual((report["before"]["tests"], report["after"]["tests"]), (1, 1))
        self.assertEqual(output["app.py"].count(b"_add_offset"), 2)
        self.assertEqual((self.destination / "app.py").read_bytes(), self.files["app.py"])

    def test_rejects_reference_in_other_module(self):
        self.files["external.py"] = b"from app import _total\n"
        with self.assertRaisesRegex(ContractError, "luar modul"):
            self.run_fixture()

    def test_refuses_dynamic_binding_and_local_shadow(self):
        source = self.files["app.py"]
        for extra in (b"other = globals()\n", b"def another(_total):\n    return _total\n"):
            with self.subTest(extra=extra):
                with self.assertRaises(ContractError):
                    safe_refactorer._replacement(source + b"\n" + extra, "_total", "_add_offset", "app.py")
