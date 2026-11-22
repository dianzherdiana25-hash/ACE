import unittest

from ._contracts import identity
from .bridge_lesson import bridge
from .test_topic_map import topics


class BridgeTests(unittest.TestCase):
    def test_bridge_waits_on_shared_prerequisite_and_applies_both_goals(self):
        plan = {"schema": "ace.teaching.bridge-lesson-plan.v1", "graph": topics(),
                "pair": ["other", "target"], "completed": [], "minutes": 30,
                "activities": [{"id": key, "goal": "Bandingkan contoh", "topics": names, "kind": mode,
                                "minutes": 5, "material_ref": "fixture:prompt"} for key, names, mode in (
                    ("seen", ["other"], "review"), ("added", ["target"], "compare"), ("mix", ["target", "other"], "apply"))]}
        result = bridge(plan, identity(plan))
        self.assertEqual(result["shared_prerequisites"], ["base"])
        self.assertEqual(result["missing_proof"], ["base"])
        self.assertEqual(result["activities"], [])
        plan["completed"] = [{"topic": "base", "ref": "fixture:graded"}]
        self.assertEqual(bridge(plan, identity(plan))["activities"][-1]["id"], "mix")
