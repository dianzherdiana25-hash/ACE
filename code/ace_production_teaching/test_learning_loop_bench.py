import json
from pathlib import Path
import unittest

from ._contracts import ProductionError, decode, identity
from .grader import assess
from .learning_loop_bench import _rubric, bench

ROOT = Path(__file__).parent / "fixtures" / "learning_loop"


class LearningLoopTests(unittest.TestCase):
    def test_hint_policy_updates_only_after_two_verified_corrections(self):
        fixture = decode((ROOT / "plan.json").read_bytes())
        result = bench(fixture, identity(fixture), ROOT)
        self.assertEqual(result, json.loads((ROOT / "run.json").read_bytes()))
        self.assertEqual((result["without_hint"]["correct"], result["with_hint"]["correct"], result["tasks"]), (3, 9, 9))
        self.assertEqual(result["with_hint"]["known"], {"add": "sum", "multiply": "product", "subtract": "difference"})
        states = {row["id"]: row for row in result["with_hint"]["trace"]}
        self.assertIsNone(states["prod_one"]["learned"])
        self.assertEqual(states["prod_one"]["corrected_score_bp"], 10_000)
        self.assertEqual(states["prod_two"]["learned"], "product")

    def test_second_fixture_cannot_learn_if_answer_leaks_or_repeats(self):
        plan = decode((ROOT / "plan.json").read_bytes())
        plan["hints"]["multiply"][0]["prompt"] = "Jawab 12."
        report = bench(plan, identity(plan), ROOT)
        self.assertEqual(report["with_hint"]["known"], {"add": "sum", "subtract": "difference"})
        self.assertEqual(report["with_hint"]["correct"], 6)
        plan["practice"][1]["operands"] = [4, 7]
        with self.assertRaisesRegex(ProductionError, "Held-out"):
            bench(plan, identity(plan), ROOT)

    def test_signed_exact_integer_is_not_credited_for_opposite_sign(self):
        request = _rubric("fixture", 1, -1, "fixture:test")
        self.assertEqual(assess(request, identity(request))["score_bp"], 0)
