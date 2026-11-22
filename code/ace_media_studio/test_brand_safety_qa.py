import unittest

from ._contracts import identity
from .brand_safety_qa import audit


class BrandTests(unittest.TestCase):
    def test_policy_categories_phrase_boundaries_and_annotation_holes(self):
        policy = {"schema": "ace.media.brand-policy.v1", "required_channels": ["audio", "visual"],
                  "blocked_categories": ["misleading"], "phrase_rules": [
                      {"id": "claim", "phrase": "jamin pasti", "category": "misleading"}]}
        annotation = {"schema": "ace.media.brand-annotations.v1", "asset_sha256": "a" * 64, "duration_ms": 600,
                      "items": [{"id": "talk", "channel": "audio", "start_ms": 0, "end_ms": 550,
                                 "text": "JAMIN PASTI", "categories": [], "source_ref": "fixture:transcript"},
                                {"id": "scene", "channel": "visual", "start_ms": 0, "end_ms": 600,
                                 "text": "Menjamin pastinya", "categories": ["misleading"], "source_ref": "fixture:frame"}]}
        findings = audit(policy, identity(policy), annotation, identity(annotation))
        self.assertEqual([r["rule"] for r in findings["findings"]], ["claim", "category"])
        self.assertEqual(findings["coverage_gaps"], [{"channel": "audio", "range_ms": [550, 600]}])
        annotation["items"][0].update(end_ms=600, text="Tidak ada klaim")
        annotation["items"][1]["categories"].clear()
        clean = audit(policy, identity(policy), annotation, identity(annotation))
        self.assertEqual(clean["status"], "eligible_on_annotated_tracks")
