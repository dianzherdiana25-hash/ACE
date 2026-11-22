from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ProductionError, identity
from .code_tutor import grade_program
from .test_tabular_engine import save


class CodeTutorTests(unittest.TestCase):
    def test_small_interpreted_program_and_out_of_subset_are_distinct(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            clean = b"def f(items):\n    total = 0\n    for item in items:\n        if item > 0:\n            total = total + item\n    return total\n"
            plan = {"schema": "ace.teaching.code-plan.v1", "submission": save(root, "code.py", clean),
                    "function": "f", "step_cap": 1000, "tests": [
                        {"id": "mix", "arguments": [[1, -2, 3]], "expected": 4, "source_ref": "fixture:cases"},
                        {"id": "none", "arguments": [[]], "expected": 0, "source_ref": "fixture:empty"}]}
            report = grade_program(plan, identity(plan), root)
            self.assertEqual(report["pass_count"], 2)
            plan["step_cap"] = 10
            limited = grade_program(plan, identity(plan), root)
            self.assertEqual(limited["cases"][0]["error"], "ProductionError")
            plan["submission"] = save(root, "code.py", b"def f(items):\n    import sys\n    return 0\n")
            with self.assertRaisesRegex(ProductionError, "subset"):
                grade_program(plan, identity(plan), root)
