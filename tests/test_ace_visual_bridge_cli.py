"""Offline JSON adapter tests for ACE-AVA."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from ace_visual_bridge.cli import process

ANCHOR = {
    "asset_id": "user-original", "provenance": "USER_ORIGINAL",
    "approved_by_user": True, "real_or_possible_person": True,
}
SCORES = {
    "identity": 5, "wardrobe": 4, "pose": 4,
    "camera": 4, "anatomy": 4, "composition": 4,
}


class JsonAdapterTests(unittest.TestCase):
    def test_plan_does_not_generate(self):
        result = process("plan", {"schema": "ace.ava.request.v1", "anchor": ANCHOR})
        self.assertEqual(result["change_axis"], "micro_detail")
        self.assertFalse(result["native_generator_called"])
        self.assertIn("wardrobe_coverage", result["locked_axes"])

    def test_one_observed_photo_cannot_pass_five_photo_gate(self):
        result = process("review", {
            "schema": "ace.ava.request.v1", "anchor": ANCHOR,
            "observations": [{
                "slot": 1, "asset_id": "photo-1", "image_type": "SINGLE_PHOTO",
                "safety": "SAFE", "evidence": "SOURCE_COMPARE", "identity": "MATCH",
                "drifted_axes": [], "scores": SCORES,
            }],
        })
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["observed_original_assets"], 1)
        self.assertFalse(result["native_quality_verified"])

    def test_refusal_blocks_selection(self):
        result = process("review", {
            "schema": "ace.ava.request.v1", "anchor": ANCHOR,
            "observations": [{
                "slot": 1, "asset_id": None, "image_type": "UNKNOWN",
                "safety": "BLOCKED", "evidence": "UNKNOWN", "identity": "UNKNOWN",
                "drifted_axes": [], "scores": None,
            }],
        })
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIsNone(result["selected_asset_id"])

    def test_schema_required(self):
        with self.assertRaises(ValueError):
            process("plan", {"schema": "wrong", "anchor": ANCHOR})

    def test_unapproved_generated_anchor_rejected(self):
        unapproved = {**ANCHOR, "provenance": "GENERATED_RESULT", "approved_by_user": False}
        with self.assertRaises(ValueError):
            process("plan", {"schema": "ace.ava.request.v1", "anchor": unapproved})


if __name__ == "__main__":
    unittest.main()
