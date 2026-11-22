from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .research_prioritizer import prioritize
from .test_research_intake import request_plan


class PrioritizerTests(unittest.TestCase):
    def test_rank_score_and_fit_are_separate_and_held_rows_unranked(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            queue = request_plan(root)
            queue["requests"].append(queue["requests"][0] | {"id": "expensive", "impact": 100, "effort_hours": 8})
            plan = {"schema": "ace.institute.priority-plan.v1", "intake": queue, "hours": 4,
                    "weights": {"impact": 50, "urgency": 30, "wait": 10, "evidence": 5, "effort_saving": 5}}
            result = prioritize(plan, identity(plan), root)
            self.assertEqual([row["id"] for row in result["ranked"]], ["expensive", "fast"])
            self.assertEqual(result["allocated"], ["fast"])
            self.assertEqual(result["hours_left"], 1)
            self.assertEqual(result["ranked"][1]["weighted_breakdown"]["urgency"], 2760)
            self.assertEqual([row["id"] for row in result["held"]], ["hold"])
