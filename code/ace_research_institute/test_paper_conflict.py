from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .paper_conflict import compare_papers
from .test_source_collector import source, source_plan


class ConflictTests(unittest.TestCase):
    def test_normalized_intervals_and_unit_checks(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = source_plan([source(root, "a", "aa", "| x | panel | cahaya | lab | 24 | pct | 38 | 21 | 29 |"),
                                    source(root, "b", "bb", "| y | panel | cahaya | lab | 0.48 | ratio | 31 | 0.43 | 0.51 |")])
            comparison = {"id": "one", "left": {"paper": "a", "measurement": "x"},
                          "right": {"paper": "b", "measurement": "y"}, "material_value": "4", "material_unit": "pct"}
            plan = {"schema": "ace.institute.paper-conflict-plan.v1", "source_plan": registry, "pairs": [comparison]}
            observed = compare_papers(plan, identity(plan), root)["findings"][0]
            self.assertEqual(observed["status"], "material_difference_disjoint_intervals")
            self.assertEqual(observed["comparison"]["delta"], "0.24")
            comparison["material_unit"] = "lux"
            self.assertEqual(compare_papers(plan, identity(plan), root)["findings"][0]["status"], "incompatible_scope")
