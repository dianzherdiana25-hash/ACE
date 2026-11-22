from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .mastery_predictor import predict
from .test_learner_model import profile
from .test_topic_map import topics


class PredictionTests(unittest.TestCase):
    def test_half_life_and_missing_prerequisite_distinct_from_zero(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = {"schema": "ace.teaching.mastery-plan.v1", "profile": profile(root), "graph": topics(),
                    "forecast_on": "2025-04-20", "threshold_bp": 2800,
                    "policies": [{"topic": key, "half_life_days": 10, "baseline_bp": 2000,
                                  "source_ref": "fixture:assumption"} for key in ("base", "target")]}
            output = predict(plan, identity(plan), root)["topics"]
            self.assertEqual(output[0]["estimate_bp"], 2875)
            self.assertEqual(output[0]["status"], "likely_above_threshold")
            self.assertIsNone(output[2]["estimate_bp"])
