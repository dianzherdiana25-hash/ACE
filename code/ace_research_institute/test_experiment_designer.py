from collections import Counter
from copy import deepcopy
import unittest

from ._contracts import ResearchError, identity
from .experiment_designer import design_experiment


class ExperimentTests(unittest.TestCase):
    def test_balanced_treatment_allocation_and_insufficient_block(self):
        plan = {"schema": "ace.institute.experiment-plan.v1", "question": "Apakah cahaya berubah?", "seed": 73,
                "arms": [{"id": "base", "procedure_ref": "fixture:baseline", "is_control": True},
                         {"id": "test", "procedure_ref": "fixture:other", "is_control": False}],
                "units": [{"id": f"x_{n}", "block": "room_a" if n < 5 else "room_b",
                           "source_ref": f"fixture:{n}"} for n in range(7)],
                "min_per_arm_by_block": 2, "measurement": {"outcome": "lux", "effect_direction": "higher",
                    "minimum_effect": "1", "stop_rule": "Pemeriksaan kalibrasi gagal.",
                    "evaluator_ref": "fixture:metric"}}
        baseline = design_experiment(plan, identity(plan))
        counts = Counter(item["arm"] for item in baseline["assignments"])
        self.assertEqual(sorted(counts.values()), [2, 3])
        self.assertEqual(baseline["deferred_blocks"][0]["available"], 2)
        reordered = deepcopy(plan)
        reordered["units"].reverse()
        self.assertEqual(design_experiment(reordered, identity(reordered))["assignment_sha256"], baseline["assignment_sha256"])
        plan["arms"][1]["is_control"] = True
        with self.assertRaisesRegex(ResearchError, "satu lengan"):
            design_experiment(plan, identity(plan))
