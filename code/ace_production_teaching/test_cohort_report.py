from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .cohort_report import summarize_cohorts
from .test_tabular_engine import save


class CohortTests(unittest.TestCase):
    def test_paired_gain_and_small_cell_suppression_preserve_privacy(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            outcomes = [{"learner": label, "cohort": group, "phase": phase, "date": when, "earned": value,
                         "possible": 10, "source_ref": "fixture:grade"}
                        for label, group in (("one", "reportable"), ("two", "reportable"), ("three", "reportable"),
                                             ("single", "small"))
                        for phase, when, value in (("before", "2025-06-01", 4), ("after", "2025-06-03", 7))]
            plan = {"schema": "ace.teaching.cohort-plan.v1", "input": save(root, "grades", b"\n".join(map(canonical, outcomes))),
                    "through": "2025-06-10", "minimum_group": 3}
            result = summarize_cohorts(plan, identity(plan), root)
            self.assertEqual(result["reported_pairs"], 3)
            self.assertEqual(result["aggregate_delta_bp"], 3000)
            self.assertEqual(result["cohorts"][1], {"cohort": "small", "status": "suppressed_small_cell"})
            self.assertNotIn("single", str(result))
