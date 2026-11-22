import unittest

from ._contracts import identity
from .reteach_engine import reteach
from .test_grader import grade


class ReteachingTests(unittest.TestCase):
    def test_alternative_method_and_separate_verification_without_answer(self):
        material = {"criterion": "volume", "narrative": "Lihat diagram kedua.",
                    "verification": "Uji hubungan dengan wadah baru.", "minutes": 5,
                    "source_ref": "fixture:lesson", "id": "diagram", "method": "diagram"}
        plan = {"schema": "ace.teaching.reteach-plan.v1", "assessment": grade(),
                "prior_methods": [{"criterion": "volume", "method": "text"}],
                "materials": [material, material | {"id": "repeat", "method": "text", "minutes": 1}],
                "minutes": 6, "reserved_answer": ["jawaban akhir"]}
        report = reteach(plan, identity(plan))
        self.assertEqual(report["prepared"][0]["material"]["id"], "diagram")
        self.assertEqual(report["prepared"][0]["previous_method"], "text")
        self.assertEqual(report["unresolved"][0]["reason"], "approach_before_unknown")
        self.assertEqual(report["minutes_left"], 1)
