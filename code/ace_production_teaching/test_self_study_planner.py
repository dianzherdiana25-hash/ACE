import unittest

from ._contracts import identity
from .self_study_planner import plan_study
from .test_topic_map import topics


class SelfStudyTests(unittest.TestCase):
    def test_thirty_days_respect_quota_and_future_verification_dependencies(self):
        plan = {"schema": "ace.teaching.self-study-plan.v1", "start": "2025-01-28",
                "start_material": topics(), "targets": ["target"], "daily_minutes": 10, "off_days": [2], "review_gap": 2}
        result = plan_study(plan, identity(plan))
        self.assertEqual(len(result["calendar"]), 30)
        self.assertEqual(result["calendar"][1]["actions"], [])
        self.assertTrue(any(action["topic"] == "target" and action["conditional_on_verified"] == ["base", "other"]
                            for row in result["calendar"] for action in row["actions"]))
        self.assertTrue(all(sum(item["minutes"] for item in row["actions"]) <= 10 for row in result["calendar"]))
        self.assertEqual(result["status"], "plan_only")
