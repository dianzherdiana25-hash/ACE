"""Unit tests for DreamCoder Wake-Sleep Library Abstraction."""
from __future__ import annotations

import unittest
from ace_abstraction.wake_sleep import WakeSleepAbstractionEngine, DiscoveredPrimitive
from ace_evolution.island_search import TypedASTNode


class TestWakeSleep(unittest.TestCase):
    def setUp(self):
        self.engine = WakeSleepAbstractionEngine()

    def test_wake_and_sleep_abstraction_compression(self):
        # Task 1: (word.count("a") * 2)
        ca = TypedASTNode("count_a", "INT")
        two = TypedASTNode("int_const", "INT", val=2)
        node1 = TypedASTNode("mul", "INT", children=[ca, two])

        # Task 2: (word.count("a") * 4)
        four = TypedASTNode("int_const", "INT", val=4)
        node2 = TypedASTNode("mul", "INT", children=[ca, four])

        # Task 3: (word.count("a") * 3)
        three = TypedASTNode("int_const", "INT", val=3)
        node3 = TypedASTNode("mul", "INT", children=[ca, three])

        # Wake phase
        self.engine.record_solution("task_ratio2", node1)
        self.engine.record_solution("task_ratio4", node2)
        self.engine.record_solution("task_ratio3", node3)

        # Sleep phase
        result = self.engine.sleep_abstract_library(min_support=2)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["solutions_processed"], 3)
        self.assertTrue(len(result["new_primitives_promoted"]) > 0)
        self.assertTrue(result["transfer_ready"])

        # Test evaluating newly abstracted primitive
        prim_id = result["new_primitives_promoted"][0]
        prim = self.engine.discovered_primitives[prim_id]
        val = prim.evaluate("aab", 2)
        self.assertEqual(val, 4)  # 2 'a's * 2 = 4


if __name__ == "__main__":
    unittest.main()
