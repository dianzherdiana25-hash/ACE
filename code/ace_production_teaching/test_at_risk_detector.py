from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .at_risk_detector import flag
from .test_learner_model import profile


class SupportTests(unittest.TestCase):
    def test_low_score_at_exact_floor_and_absent_evidence_are_distinct(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = {"schema": "ace.teaching.support-signal-plan.v1", "profile": profile(root),
                    "thresholds": {"minimum_recent": 2, "low_average_bp": 2500, "inactivity_days": 8, "downshift_bp": 2000}}
            base, target = flag(plan, identity(plan), root)["topics"]
            self.assertEqual(base["signals"], ["recent_scores_below_floor"])
            self.assertEqual(base["source_lines"], [1, 2])
            self.assertEqual(target["status"], "insufficient_recent_evidence")
            self.assertIsNone(target["recent_average_bp"])
