from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .evidence_grader import grade
from .test_literature_reviewer import DIMS, hypotheses


class GradeTests(unittest.TestCase):
    def test_intergroup_disagreement_precedes_declarative_design_score(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            risks = {"attrition": "low", "selection": "low", "measurement": "low"}
            plan = {"schema": "ace.institute.grade-plan.v1", "sources": hypotheses(root),
                    "target": {"dimensions": DIMS, "unit": "pct"}, "minimum_groups": 2, "conflict_width": "5",
                    "assessments": [{"source_id": item, "design": "randomized", "citation": f"fixture:{item}",
                                     "risk": dict(risks)} for item in ("left", "right")]}
            result = grade(plan, identity(plan), root)
            self.assertEqual(result["status"], "conflicting_graded_estimates")
            self.assertEqual(result["between_group_spread"], "0.15")
            plan["assessments"][1]["risk"]["selection"] = "high"
            plan["assessments"][1]["risk"]["attrition"] = "high"
            result = grade(plan, identity(plan), root)
            self.assertEqual(result["status"], "insufficient_graded_independent_groups")
