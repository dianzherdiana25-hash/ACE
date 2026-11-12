"""Unit tests for Autonomous Multi-Agent Software Factory."""
import sys
from pathlib import Path

# Ensure code directory is at head of sys.path
_code_dir = Path(__file__).resolve().parent.parent
if str(_code_dir) not in sys.path:
    sys.path.insert(0, str(_code_dir))

import unittest
from ace_operational.models_backend import ModelRouter
from ace_operational.software_factory import SoftwareFactory
from ace_operational.store import OperationalStore


class TestSoftwareFactory(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path("/tmp/test_factory_workspace")
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.store = OperationalStore(workspace=self.tmp_dir)
        self.router = ModelRouter(self.store)
        self.factory = SoftwareFactory(self.store, self.router)

    def test_plan_architecture(self):
        plan = self.factory.plan_architecture(
            project_name="Mini CRM",
            spec_id="Sistem manajemen kontak pelanggan dengan SQLite",
        )
        self.assertEqual(plan["project_name"], "Mini CRM")
        # A missing model must not fabricate an architecture overview.
        if plan["success"]:
            self.assertTrue(plan["architecture_overview"])
        else:
            self.assertEqual(plan["architecture_overview"], "")

    def test_synthesize_module_ast_check(self):
        valid_py = "def tambah(a: int, b: int) -> int:\n    return a + b\n"
        res_ok = self.factory.synthesize_module(self.tmp_dir / "valid.py", valid_py, is_python=True)
        self.assertTrue(res_ok["success"])

        invalid_py = "def tambah(a: int, b: int) -> int:\n    return a + \n"
        res_fail = self.factory.synthesize_module(self.tmp_dir / "invalid.py", invalid_py, is_python=True)
        self.assertFalse(res_fail["success"])
        self.assertIn("SyntaxError", res_fail["error"])

    def test_execute_test_suite_and_auto_repair(self):
        # Target module
        target_py = self.tmp_dir / "calc.py"
        target_code = "def kali(a, b):\n    return a * b\n"
        self.factory.synthesize_module(target_py, target_code)

        # Test module
        test_py = self.tmp_dir / "test_calc.py"
        test_code = (
            "import unittest\n"
            "from calc import kali\n"
            "class TestCalc(unittest.TestCase):\n"
            "    def test_kali(self):\n"
            "        self.assertEqual(kali(3, 4), 12)\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )
        self.factory.synthesize_module(test_py, test_code)

        qa_res = self.factory.execute_test_suite(test_py)
        self.assertTrue(qa_res["passed"])
        self.assertEqual(qa_res["exit_code"], 0)

    def test_build_project_end_to_end(self):
        project_dir = self.tmp_dir / "sample_project"
        files = {
            "greeter.py": "def sapa(nama: str) -> str:\n    return f'Halo, {nama}!'\n",
            "README.md": "# Sample Project\nDokumentasi proyek pengujian.\n",
        }
        test_spec = (
            "test_greeter.py",
            (
                "import unittest\n"
                "from greeter import sapa\n"
                "class TestGreeter(unittest.TestCase):\n"
                "    def test_sapa(self):\n"
                "        self.assertEqual(sapa('Budi'), 'Halo, Budi!')\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            ),
        )
        result = self.factory.build_project(
            project_name="Sample Project",
            specification_id="Modul sapaan ramah",
            target_dir=project_dir,
            files_spec=files,
            test_spec=test_spec,
        )
        self.assertTrue(result["success"])
        self.assertTrue((project_dir / "greeter.py").exists())
        self.assertTrue((project_dir / "test_greeter.py").exists())
        self.assertTrue((project_dir / "README.md").exists())
        self.assertTrue(result["receipt_id"].startswith("rcpt_"))


if __name__ == "__main__":
    unittest.main()
