from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .expert_source_panel import form_panel
from .test_comparison_analyst import save


class ExpertTests(unittest.TestCase):
    def test_panel_is_independent_with_explicit_uncovered_goal_and_conflict(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry = {"schema": "ace.institute.expert-registry.v1", "entries": [
                {"id": key, "group": lab, "topics": topics, "credibility": 85, "credential_ref": f"fixture:{key}",
                 "disclosure": disclosure} for key, lab, topics, disclosure in (
                    ("a", "left", ["method", "data"], "none_declared"),
                    ("b", "left", ["data"], "none_declared"),
                    ("c", "right", ["method"], "none_declared"),
                    ("d", "other", ["data"], "conflict_declared"))]}
            plan = {"schema": "ace.institute.expert-panel-plan.v1", "registry": save(root, "experts.json", canonical(registry)),
                    "topics": [{"id": topic, "weight": 30, "minimum_members": 2} for topic in ("method", "data")],
                    "capacity": 3, "minimum_credibility": 75}
            result = form_panel(plan, identity(plan), root)
            self.assertEqual([person["id"] for person in result["selected"]], ["a", "c"])
            self.assertEqual(result["unmet_topics"], [{"topic": "data", "required": 2, "selected_members": 1}])
            self.assertEqual(result["hold"][0]["reasons"], ["conflict_or_unknown"])
