import unittest

from ._contracts import ProductionError, identity
from .topic_map import graph


def topics():
    return {"schema": "ace.teaching.topic-graph-plan.v1", "topics": [
        {"id": "target", "title": "Target", "requires": ["base", "other"], "minutes": 11, "source_ref": "fixture:target"},
        {"id": "base", "title": "Dasar", "requires": [], "minutes": 5, "source_ref": "fixture:base"},
        {"id": "other", "title": "Pendamping", "requires": ["base"], "minutes": 7, "source_ref": "fixture:other"}]}


class TopicGraphTests(unittest.TestCase):
    def test_layered_order_and_critical_path_or_cycle(self):
        plan = topics()
        result = graph(plan, identity(plan))
        self.assertEqual(result["order"], ["base", "other", "target"])
        self.assertEqual(result["topics"]["target"]["critical_minutes"], 23)
        self.assertEqual(result["topics"]["target"]["transitive_requires"], ["base", "other"])
        self.assertEqual(result["topics"]["base"]["unlocks"], ["other", "target"])
        plan["topics"][1]["requires"] = ["target"]
        with self.assertRaisesRegex(ProductionError, "siklus"):
            graph(plan, identity(plan))
