from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .kb_freshness import freshness
from .test_source_collector import source, source_plan


class FreshnessTests(unittest.TestCase):
    def test_age_bound_inclusive_and_stale_insufficient_groups(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = source_plan([source(root, "a", "g_a", created="2025-01-10"),
                                   source(root, "b", "g_b", created="2025-01-09")])
            plan = {"schema": "ace.institute.freshness-plan.v1", "register_plan": catalog,
                    "policies": [{"topic": "cahaya", "maximum_age_days": 10, "minimum_groups": 2}]}
            topic = freshness(plan, identity(plan), root)["topics"][0]
            self.assertEqual(topic["fresh_groups"], ["g_a"])
            self.assertEqual(topic["latest_fresh_age_days"], 10)
            self.assertEqual(topic["status"], "refresh_needed")
            self.assertEqual([row["status"] for row in topic["sources"]], ["fresh", "stale"])
