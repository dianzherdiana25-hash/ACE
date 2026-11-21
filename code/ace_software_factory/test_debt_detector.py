"""Verifier graf impor, kompleksitas dan laporan sumber tak terurai."""
import unittest

from ace_software_factory import debt_detector
from ace_software_factory._contracts import ContractError, identity
from ace_software_factory.test_self_reviewer import fixture


class DebtTests(unittest.TestCase):
    def test_discovers_cycle_and_priority_when_dirty_file_exists(self):
        root, manifest = fixture(self, {
            "app/__init__.py": b"",
            "app/lane_a.py": b"from . import lane_b\n",
            "app/lane_b.py": b"from .lane_a import run\nimport outsider\n"
                             b"def dispatch(a, b):\n    if a and b:\n        return [v for v in a if v]\n    return None\n",
            "broken.py": b"def invalid(",
        })
        result = debt_detector.analyze(root, manifest, identity(manifest), max_complexity=4, max_lines=3)
        self.assertEqual(result["cycles"], [{"modules": ["app.lane_a", "app.lane_b"],
                                             "paths": ["app/lane_a.py", "app/lane_b.py"]}])
        self.assertEqual(result["functions"][0]["complexity"], 5)
        self.assertEqual(result["functions"][0]["reasons"], ["complexity", "length"])
        self.assertEqual(result["parse_failures"][0]["path"], "broken.py")
        self.assertNotIn("outsider", result["dependencies"]["app.lane_b"])

    def test_nested_function_has_own_complexity_budget(self):
        root, manifest = fixture(self, {"app.py": b"def outer():\n    def inner(x):\n        if x:\n            return x\n"
                                                 b"    return inner\n"})
        report = debt_detector.analyze(root, manifest, identity(manifest), max_complexity=1)
        self.assertEqual([(item["function"], item["complexity"]) for item in report["functions"]], [("inner", 2)])

    def test_ambiguous_module_is_rejected(self):
        root, manifest = fixture(self, {"app/__init__.py": b"", "app.py": b""})
        with self.assertRaisesRegex(ContractError, "nama modul"):
            debt_detector.analyze(root, manifest, identity(manifest))
