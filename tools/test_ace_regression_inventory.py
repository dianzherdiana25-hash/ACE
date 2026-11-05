"""Tests for read-only regression module inventory."""
import tempfile
import unittest
from pathlib import Path
from tools.ace_regression_inventory import inspect, main


class InventoryTests(unittest.TestCase):
    def make_root(self, manifest):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "tools").mkdir()
        (root / "tools" / "ace_e15_regression.py").write_text(manifest)
        return temp, root

    def test_missing_module_blocks_without_importing(self):
        t, root = self.make_root("TESTS={'u':['e14.test_e14u_algebra_union']}\n")
        with t:
            report = inspect(root)
            self.assertEqual("BLOCK_MISSING_MODULES", report["decision"])
            self.assertEqual(1, report["missing"])
            self.assertEqual("code/e14/test_e14u_algebra_union.py", report["records"][0]["path"])
            self.assertEqual(2, main(["--root", str(root)]))

    def test_present_code_and_tools_modules(self):
        t, root = self.make_root("TESTS={'u':['e14.test_a'],'tooling':['tools.test_b']}\n")
        with t:
            (root / "code" / "e14").mkdir(parents=True)
            (root / "code" / "e14" / "test_a.py").write_text("raise RuntimeError('do not import')")
            (root / "tools" / "test_b.py").write_text("raise RuntimeError('do not import')")
            self.assertEqual("INVENTORY_COMPLETE_NOT_TESTED", inspect(root)["decision"])

    def test_reject_nonliteral_manifest(self):
        t, root = self.make_root("TESTS=eval('[]')\n")
        with t, self.assertRaises(ValueError):
            inspect(root)

    def test_reject_invalid_module_name(self):
        t, root = self.make_root("TESTS={'u':['../secret']}\n")
        with t, self.assertRaises(ValueError):
            inspect(root)

    def test_reject_missing_manifest(self):
        with tempfile.TemporaryDirectory() as temp, self.assertRaises(ValueError):
            inspect(Path(temp))


if __name__ == "__main__":
    unittest.main()
