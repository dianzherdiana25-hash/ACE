from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .literature_reviewer import review
from .test_source_collector import source, source_plan


DIMS = {"population": "group", "outcome": "cahaya", "context": "lab"}


def hypotheses(root):
    return source_plan([source(root, "left", "cohort_a", "| left | group | cahaya | lab | 31 | pct | 20 | - | - |"),
                        source(root, "right", "cohort_b", "| right | group | cahaya | lab | 0.46 | ratio | 40 | - | - |"),
                        source(root, "wrong", "cohort_c", "| wrong | group | cahaya | field | 31 | pct | 40 | - | - |")])


class LiteratureTests(unittest.TestCase):
    def test_literature_preserves_group_disagreement_and_absence(self):
        with TemporaryDirectory() as temporary:
            table = hypotheses(Path(temporary))
            row = {"id": "test", "question": "Apakah cahayanya konsisten?", "dimensions": DIMS,
                   "unit": "pct", "agreement_width": "4", "minimum_groups": 2, "minimum_sample": 10}
            plan = {"schema": "ace.institute.literature-plan.v1", "sources": table,
                    "questions": [row, row | {"id": "missing", "dimensions": DIMS | {"population": "other"}}]}
            output = review(plan, identity(plan), Path(temporary))
            found, missing = output["results"]
            self.assertEqual(found["status"], "group_disagreement")
            self.assertEqual(found["group_medians"], {"cohort_a": "0.31", "cohort_b": "0.46"})
            self.assertIn("left.md:6", output["markdown"])
            self.assertEqual(missing["group_range"], None)
            self.assertEqual(missing["status"], "insufficient_independent_groups")
