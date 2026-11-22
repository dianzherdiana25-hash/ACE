from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .lesson_planner import plan_lessons
from .test_learner_model import profile
from .test_topic_map import topics


class LessonPlanTests(unittest.TestCase):
    def test_observed_gap_remediated_dependents_wait_for_proof(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = {"schema": "ace.teaching.lesson-plan.v1", "topic_graph": topics(), "learner_model": profile(root),
                    "materials": [{"id": "review", "topic": "base", "kind": "remedial", "minutes": 5,
                                    "source_ref": "fixture:remedy", "goal": "Pahami konsep dasar"},
                                  {"id": "next", "topic": "target", "kind": "diagnostic", "minutes": 4,
                                    "source_ref": "fixture:target", "goal": "Uji konsep baru"}],
                    "mastery_floor_bp": 8000, "minutes": 10, "targets": ["target"]}
            report = plan_lessons(plan, identity(plan), root)
            self.assertEqual([row["topic"] for row in report["placed"]], ["base"])
            self.assertEqual(report["placed"][0]["kind"], "remedial")
            self.assertEqual(report["placed"][0]["evidence"]["estimate_bp"], 3750)
            self.assertEqual(report["held"][1]["dependencies"], ["base", "other"])
            self.assertEqual(report["minutes_unused"], 5)
