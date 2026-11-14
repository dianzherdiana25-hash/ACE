"""Regression tests for the CodeRabbit PR #105 finding
(input-validation weakness in the visual bridge).

Two defects, both reproduced on origin/main before the
fix:
  1. Anchor.approved_by_user arriving as the string
     "false" passes the adoption check in plan_edit
     (``not "false"`` is False) — an unadopted generated
     result can become the source anchor.
  2. Observation.drifted_axes arriving as a string is
     split into characters (the CLI's frozenset(string)
     conversion) — drift on a locked axis evades the
     ``drifted_axes & plan.locked_axes`` check and the
     candidate can reach USER_ACCEPTED.
"""
import unittest

from ace_visual_bridge.cli import process
from ace_visual_bridge.contract import (
    Anchor, Observation, plan_edit, review_batch,
)

SCORES = {"identity": 5, "wardrobe": 5, "pose": 5,
          "camera": 5, "anatomy": 5, "composition": 5}


def anchor(**overrides):
    data = {"asset_id": "x", "provenance": "USER_ORIGINAL",
            "approved_by_user": False, "real_or_possible_person": False}
    data.update(overrides)
    return Anchor(**data)


def observation(**overrides):
    data = {"slot": 0, "asset_id": "img1",
            "image_type": "SINGLE_PHOTO", "safety": "SAFE",
            "evidence": "OBSERVED_IMAGE", "identity": "MATCH",
            "drifted_axes": frozenset(),
            "scores": dict(SCORES),
            "independently_reviewed": True, "accepted_by_user": True}
    data.update(overrides)
    return Observation(**data)


class ApprovedByUserValidationTests(unittest.TestCase):
    def test_string_false_is_rejected(self):
        with self.assertRaises(ValueError):
            Anchor(asset_id="x", provenance="GENERATED_RESULT",
                   approved_by_user="false",
                   real_or_possible_person=False)

    def test_int_is_rejected(self):
        with self.assertRaises(ValueError):
            Anchor(asset_id="x", provenance="USER_ORIGINAL",
                   approved_by_user=1, real_or_possible_person=False)

    def test_real_person_string_is_rejected(self):
        with self.assertRaises(ValueError):
            Anchor(asset_id="x", provenance="USER_ORIGINAL",
                   approved_by_user=False,
                   real_or_possible_person="false")

    def test_real_bools_still_accepted(self):
        plan = plan_edit(anchor())
        self.assertEqual(plan.change_axis, "micro_detail")

    def test_unadopted_generated_still_refused(self):
        with self.assertRaises(ValueError):
            plan_edit(anchor(provenance="GENERATED_RESULT",
                             approved_by_user=False))


class DriftedAxesValidationTests(unittest.TestCase):
    def test_char_split_frozenset_is_rejected(self):
        with self.assertRaises(ValueError):
            observation(drifted_axes=frozenset("face_identity"))

    def test_unknown_axis_is_rejected(self):
        with self.assertRaises(ValueError):
            observation(drifted_axes=frozenset({"not_an_axis"}))

    def test_raw_string_is_rejected(self):
        with self.assertRaises(ValueError):
            observation(drifted_axes="face_identity")

    def test_list_is_rejected(self):
        with self.assertRaises(ValueError):
            observation(drifted_axes=["face_identity"])

    def test_locked_axis_drift_still_rejected(self):
        plan = plan_edit(anchor())
        review = review_batch(
            anchor(), plan,
            [observation(drifted_axes=frozenset({"face_identity"}))],
            expected=1)
        self.assertEqual(review.reviews[0].status, "REJECTED")
        self.assertEqual(review.reviews[0].reason,
                         "locked visual dimension drift")

    def test_clean_observation_still_qualified(self):
        plan = plan_edit(anchor())
        review = review_batch(anchor(), plan, [observation()], expected=1)
        self.assertEqual(review.reviews[0].status, "QUALIFIED")
        self.assertEqual(review.status, "USER_ACCEPTED")


class CliBoundaryTests(unittest.TestCase):
    def _request(self, **overrides):
        data = {"schema": "ace.ava.request.v1",
                "anchor": {"asset_id": "x",
                           "provenance": "USER_ORIGINAL",
                           "approved_by_user": False,
                           "real_or_possible_person": False},
                "axis": "micro_detail",
                "expected": 1,
                "observations": []}
        data.update(overrides)
        return data

    def test_cli_string_drifted_axes_is_invalid(self):
        request = self._request(observations=[
            {"slot": 0, "asset_id": "img1",
             "image_type": "SINGLE_PHOTO", "safety": "SAFE",
             "evidence": "OBSERVED_IMAGE", "identity": "MATCH",
             "drifted_axes": "face_identity", "scores": dict(SCORES),
             "independently_reviewed": True, "accepted_by_user": True}])
        with self.assertRaises(ValueError):
            process("review", request)

    def test_cli_string_false_approved_is_invalid(self):
        request = self._request()
        request["anchor"]["provenance"] = "GENERATED_RESULT"
        request["anchor"]["approved_by_user"] = "false"
        with self.assertRaises(ValueError):
            process("plan", request)

    def test_cli_valid_request_still_works(self):
        request = self._request(observations=[
            {"slot": 0, "asset_id": "img1",
             "image_type": "SINGLE_PHOTO", "safety": "SAFE",
             "evidence": "OBSERVED_IMAGE", "identity": "MATCH",
             "drifted_axes": [], "scores": dict(SCORES),
             "independently_reviewed": True, "accepted_by_user": True}])
        result = process("review", request)
        self.assertEqual(result["status"], "USER_ACCEPTED")


if __name__ == "__main__":
    unittest.main()
