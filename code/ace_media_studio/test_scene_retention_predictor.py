from hashlib import sha256
import unittest

from ._contracts import identity
from .scene_retention_predictor import forecast


class RetentionProxyTests(unittest.TestCase):
    def test_feature_score_is_reproducible_and_names_lowest_scene(self):
        plan = {"schema": "ace.media.retention-plan.v1", "baseline_bp": 6400,
                "roles": {"action_terms": ["ukur"], "promise_terms": ["cahaya"]},
                "scenes": [{"id": "intro", "source_ref": "fixture:1", "narration": "Ukur cahaya?",
                            "duration_ms": 4000, "has_visual_action": True},
                           {"id": "slow", "source_ref": "fixture:2", "narration": "Layar diam.",
                            "duration_ms": 12000, "has_visual_action": False},
                           {"id": "return", "source_ref": "fixture:3", "narration": "Ukur cahaya lagi.",
                            "duration_ms": 5000, "has_visual_action": True}]}
        data = forecast(plan, identity(plan))
        self.assertEqual(data["kind"], "unvalidated_script_proxy")
        self.assertEqual([row["proxy_score_bp"] for row in data["scenes"]], [7000, 6200, 6550])
        self.assertEqual(data["lowest_proxy_scene"], "slow")
        self.assertEqual(data["scenes"][0]["narration_sha256"], sha256(b"Ukur cahaya?").hexdigest())
        self.assertEqual(data, forecast(plan, identity(plan)))
