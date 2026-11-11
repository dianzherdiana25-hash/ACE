"""Offline contract tests; not evidence of native image generation."""
from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from ace_visual_bridge.contract import (
    Anchor, Observation, assess, plan_edit, review_batch,
)

SCORES = {
    "identity": 5.0, "wardrobe": 4.0, "pose": 4.0,
    "camera": 4.0, "anatomy": 4.0, "composition": 4.0,
}


def original(real=True):
    return Anchor("source-1", "USER_ORIGINAL", True, real)


def observation(slot=1, **changes):
    base = Observation(
        slot, f"asset-{slot}", "SINGLE_PHOTO", "SAFE",
        "SOURCE_COMPARE", "MATCH", frozenset(), SCORES,
    )
    return replace(base, **changes)


class VisualBridgeContractTests(unittest.TestCase):
    def setUp(self):
        self.anchor = original()
        self.plan = plan_edit(self.anchor)

    def test_next_only_micro_detail(self):
        self.assertEqual(self.plan.change_axis, "micro_detail")
        self.assertIn("wardrobe_coverage", self.plan.locked_axes)
        self.assertIn("face_identity", self.plan.locked_axes)

    def test_camera_only_keeps_pose_and_wardrobe_locked(self):
        plan = plan_edit(self.anchor, "camera")
        self.assertNotIn("camera", plan.locked_axes)
        self.assertIn("pose", plan.locked_axes)
        self.assertIn("wardrobe_coverage", plan.locked_axes)

    def test_unapproved_generated_asset_cannot_be_anchor(self):
        anchor = Anchor("generated-1", "GENERATED_RESULT", False, True)
        with self.assertRaises(ValueError):
            plan_edit(anchor)

    def test_approved_generated_asset_may_be_anchor(self):
        anchor = Anchor("generated-1", "GENERATED_RESULT", True, True)
        self.assertEqual(plan_edit(anchor, "pose").source_asset_id, "generated-1")

    def test_reject_unknown_axis(self):
        with self.assertRaises(ValueError):
            plan_edit(self.anchor, "exposure_escalation")

    def test_real_photo_requires_source_compare(self):
        o = observation(evidence="OBSERVED_IMAGE")
        self.assertEqual(assess(self.anchor, self.plan, o).status, "NOT_ASSESSED")

    def test_real_photo_unknown_identity_not_winner(self):
        o = observation(identity="UNKNOWN")
        self.assertEqual(assess(self.anchor, self.plan, o).status, "NOT_ASSESSED")

    def test_visible_identity_mismatch_rejected(self):
        o = observation(identity="MISMATCH")
        self.assertEqual(assess(self.anchor, self.plan, o).status, "REJECTED")

    def test_composite_not_an_independent_photo(self):
        o = observation(image_type="COMPOSITE")
        self.assertEqual(assess(self.anchor, self.plan, o).reason, "OUTPUT_TYPE_MISMATCH")

    def test_safety_refusal_terminates_batch(self):
        blocked = observation(safety="BLOCKED")
        result = review_batch(self.anchor, self.plan, [blocked, observation(slot=2)], expected=2)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIsNone(result.selected_asset_id)

    def test_unknown_safety_never_qualifies(self):
        o = observation(safety="UNKNOWN")
        self.assertEqual(assess(self.anchor, self.plan, o).status, "NOT_ASSESSED")

    def test_locked_dimension_drift_rejected(self):
        o = observation(drifted_axes=frozenset({"pose"}))
        self.assertEqual(assess(self.anchor, self.plan, o).status, "REJECTED")

    def test_requested_dimension_change_is_not_drift(self):
        plan = plan_edit(self.anchor, "pose")
        o = observation(drifted_axes=frozenset({"pose"}))
        self.assertEqual(assess(self.anchor, plan, o).status, "QUALIFIED")

    def test_weighted_score_has_observable_fields(self):
        result = assess(self.anchor, self.plan, observation())
        self.assertEqual(result.status, "QUALIFIED")
        self.assertAlmostEqual(result.score, 4.35)

    def test_missing_score_is_unknown(self):
        o = observation(scores={"identity": 5.0})
        self.assertEqual(assess(self.anchor, self.plan, o).status, "NOT_ASSESSED")

    def test_nan_score_is_unknown(self):
        o = observation(scores={**SCORES, "pose": float("nan")})
        self.assertEqual(assess(self.anchor, self.plan, o).status, "NOT_ASSESSED")

    def test_single_return_not_misreported_as_five(self):
        result = review_batch(self.anchor, self.plan, [observation()], expected=5)
        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(result.observed_original_assets, 1)

    def test_five_distinct_assets_without_independent_review_provisional(self):
        result = review_batch(self.anchor, self.plan, [observation(slot=i) for i in range(1, 6)], expected=5)
        self.assertEqual(result.status, "TIE_REVIEW_REQUIRED")

    def test_select_without_user_acceptance_is_provisional(self):
        high = observation(slot=1)
        low = observation(slot=2, scores={**SCORES, "identity": 3.0})
        result = review_batch(self.anchor, self.plan, [high, low], expected=2)
        self.assertEqual(result.status, "PROVISIONAL_SELECTION")
        self.assertEqual(result.selected_asset_id, "asset-1")

    def test_acceptance_requires_real_confirmation(self):
        high = observation(slot=1, independently_reviewed=True, accepted_by_user=True)
        low = observation(slot=2, scores={**SCORES, "identity": 3.0})
        result = review_batch(self.anchor, self.plan, [high, low], expected=2)
        self.assertEqual(result.status, "USER_ACCEPTED")

    def test_same_asset_two_slots_is_rejected(self):
        with self.assertRaises(ValueError):
            review_batch(self.anchor, self.plan, [
                observation(slot=1),
                observation(slot=2, asset_id="asset-1"),
            ])

    def test_anchor_swap_is_rejected(self):
        with self.assertRaises(ValueError):
            review_batch(Anchor("another", "USER_ORIGINAL", True, True), self.plan, [observation()])


if __name__ == "__main__":
    unittest.main()
