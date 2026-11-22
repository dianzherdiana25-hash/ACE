import unittest

from ._contracts import identity
from .research_roadmap import roadmap


class RoadmapTests(unittest.TestCase):
    def test_partial_infeasible_work_does_not_consume_hours(self):
        def item(key, hours, earliest, deadline, required=()):
            return {"id": key, "question": "Bagaimana hasil?", "priority": 10, "hours": hours,
                    "earliest_month": earliest, "deadline_month": deadline, "requirements": list(required),
                    "evidence_ref": f"fixture:{key}"}
        plan = {"schema": "ace.institute.roadmap-plan.v1", "starting_on": "2025-12-01",
                "monthly_hours": [4] * 12, "projects": [
                    item("base", 6, 1, 2), item("replica", 3, 1, 4, ("base",)),
                    item("lose", 9, 1, 1), item("blocked", 1, 1, 10, ("lose",))]}
        result = roadmap(plan, identity(plan))
        self.assertEqual(result["allocated"][0]["work"], [{"month": "2025-12", "hours": 4}, {"month": "2026-01", "hours": 2}])
        self.assertEqual(result["allocated"][1]["work"], [{"month": "2026-02", "hours": 3}])
        self.assertEqual(result["remaining_hours"]["2026-01"], 2)
        self.assertEqual({row["id"]: row["reason"] for row in result["unplaced"]},
                         {"blocked": "unplaced_dependency", "lose": "insufficient_hours_before_deadline"})
