"""Edge-case unit tests for ace_visual_bridge (contract.py and cli.py)."""
from __future__ import annotations

import io
import json
import math
from unittest.mock import patch
import unittest

from ace_visual_bridge import cli, contract


def _valid_scores(val: float = 4.0) -> dict[str, float]:
    return {k: val for k in contract.WEIGHTS}


def _obs(
    slot: int = 1,
    asset_id: str | None = "asset_1",
    image_type: str = "SINGLE_PHOTO",
    safety: str = "SAFE",
    evidence: str = "SOURCE_COMPARE",
    identity: str = "MATCH",
    drifted_axes: frozenset[str] = frozenset(),
    scores: dict[str, float] | None = None,
    independently_reviewed: bool = False,
    accepted_by_user: bool = False,
) -> contract.Observation:
    return contract.Observation(
        slot=slot,
        asset_id=asset_id,
        image_type=image_type,
        safety=safety,
        evidence=evidence,
        identity=identity,
        drifted_axes=drifted_axes,
        scores=_valid_scores() if scores is None else scores,
        independently_reviewed=independently_reviewed,
        accepted_by_user=accepted_by_user,
    )


class TestVisualBridgeEdgeCases(unittest.TestCase):
    def test_01_anchor_blank_asset_id_rejected(self) -> None:
        with self.assertRaises(ValueError):
            contract.Anchor("   ", "USER_ORIGINAL", True, True)

    def test_02_anchor_unknown_provenance_rejected(self) -> None:
        with self.assertRaises(ValueError):
            contract.Anchor("a1", "SCRAPED_WEB", True, False)

    def test_03_anchor_non_bool_flags_rejected(self) -> None:
        with self.assertRaises(ValueError):
            contract.Anchor("a1", "USER_ORIGINAL", "false", True)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            contract.Anchor("a1", "USER_ORIGINAL", True, 1)  # type: ignore[arg-type]

    def test_04_plan_edit_disallowed_axis_rejected(self) -> None:
        anchor = contract.Anchor("a1", "USER_ORIGINAL", True, True)
        with self.assertRaises(ValueError):
            contract.plan_edit(anchor, "face_identity")

    def test_05_plan_edit_unadopted_generated_result_rejected(self) -> None:
        anchor = contract.Anchor("g1", "GENERATED_RESULT", False, False)
        with self.assertRaises(ValueError):
            contract.plan_edit(anchor, "lighting")

    def test_06_plan_edit_adopted_generated_result_locks_other_axes(self) -> None:
        anchor = contract.Anchor("g1", "GENERATED_RESULT", True, False)
        plan = contract.plan_edit(anchor, "lighting")
        self.assertEqual(plan.change_axis, "lighting")
        self.assertNotIn("lighting", plan.locked_axes)
        self.assertIn("face_identity", plan.locked_axes)

    def test_07_observation_drifted_axes_string_or_unknown_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _obs(drifted_axes="lighting")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            _obs(drifted_axes=frozenset({"nonexistent_axis"}))

    def test_08_assess_safety_blocked_takes_precedence(self) -> None:
        anchor = contract.Anchor("a1", "USER_ORIGINAL", True, True)
        plan = contract.plan_edit(anchor, "lighting")
        res = contract.assess(anchor, plan, _obs(asset_id=None, image_type="UNKNOWN", safety="BLOCKED"))
        self.assertEqual(res.status, "BLOCKED")
        self.assertIsNone(res.score)

    def test_09_assess_missing_asset_or_unknown_image_type_not_assessed(self) -> None:
        anchor = contract.Anchor("a1", "USER_ORIGINAL", True, True)
        plan = contract.plan_edit(anchor, "lighting")
        self.assertEqual(contract.assess(anchor, plan, _obs(asset_id=None)).status, "NOT_ASSESSED")
        self.assertEqual(contract.assess(anchor, plan, _obs(image_type="UNKNOWN")).status, "NOT_ASSESSED")

    def test_10_assess_composite_or_document_rejected(self) -> None:
        anchor = contract.Anchor("a1", "USER_ORIGINAL", True, True)
        plan = contract.plan_edit(anchor, "lighting")
        res = contract.assess(anchor, plan, _obs(image_type="COMPOSITE"))
        self.assertEqual(res.status, "REJECTED")
        self.assertEqual(res.reason, "OUTPUT_TYPE_MISMATCH")

    def test_11_assess_unknown_safety_not_assessed(self) -> None:
        anchor = contract.Anchor("a1", "USER_ORIGINAL", True, True)
        plan = contract.plan_edit(anchor, "lighting")
        res = contract.assess(anchor, plan, _obs(safety="UNKNOWN"))
        self.assertEqual(res.status, "NOT_ASSESSED")

    def test_12_assess_locked_axis_drift_rejected_while_allowed_axis_passes(self) -> None:
        anchor = contract.Anchor("a1", "USER_ORIGINAL", True, True)
        plan = contract.plan_edit(anchor, "lighting")
        rej = contract.assess(anchor, plan, _obs(drifted_axes=frozenset({"pose"})))
        self.assertEqual(rej.status, "REJECTED")
        ok = contract.assess(anchor, plan, _obs(drifted_axes=frozenset({"lighting"})))
        self.assertEqual(ok.status, "QUALIFIED")

    def test_13_assess_real_person_evidence_and_identity_gates(self) -> None:
        anchor = contract.Anchor("a1", "USER_ORIGINAL", True, True)
        plan = contract.plan_edit(anchor, "lighting")
        self.assertEqual(contract.assess(anchor, plan, _obs(evidence="OBSERVED_IMAGE")).status, "NOT_ASSESSED")
        self.assertEqual(contract.assess(anchor, plan, _obs(identity="MISMATCH")).status, "REJECTED")
        self.assertEqual(contract.assess(anchor, plan, _obs(identity="UNKNOWN")).status, "NOT_ASSESSED")

    def test_14_assess_non_person_allows_observed_image_without_identity_match(self) -> None:
        anchor = contract.Anchor("a1", "USER_ORIGINAL", True, False)
        plan = contract.plan_edit(anchor, "lighting")
        res = contract.assess(anchor, plan, _obs(evidence="OBSERVED_IMAGE", identity="UNKNOWN"))
        self.assertEqual(res.status, "QUALIFIED")
        self.assertEqual(res.score, 4.0)

    def test_15_assess_non_person_unknown_evidence_not_assessed(self) -> None:
        anchor = contract.Anchor("a1", "USER_ORIGINAL", True, False)
        plan = contract.plan_edit(anchor, "lighting")
        res = contract.assess(anchor, plan, _obs(evidence="UNKNOWN"))
        self.assertEqual(res.status, "NOT_ASSESSED")

    def test_16_assess_rubric_missing_bool_nan_or_out_of_range(self) -> None:
        anchor = contract.Anchor("a1", "USER_ORIGINAL", True, False)
        plan = contract.plan_edit(anchor, "lighting")
        for bad_scores in (
            {"identity": 4.0},
            {**_valid_scores(), "extra": 1.0},
            {**_valid_scores(), "identity": True},
            {**_valid_scores(), "identity": math.nan},
            {**_valid_scores(), "identity": math.inf},
            {**_valid_scores(), "identity": -0.1},
            {**_valid_scores(), "identity": 5.1},
        ):
            obs = contract.Observation(1, "a", "SINGLE_PHOTO", "SAFE", "OBSERVED_IMAGE", "UNKNOWN", frozenset(), bad_scores)
            self.assertEqual(contract.assess(anchor, plan, obs).status, "NOT_ASSESSED")

    def test_17_review_batch_validation_errors(self) -> None:
        anchor = contract.Anchor("a1", "USER_ORIGINAL", True, False)
        plan = contract.plan_edit(anchor, "lighting")
        other_plan = contract.plan_edit(contract.Anchor("other", "USER_ORIGINAL", True, False), "lighting")
        with self.assertRaises(ValueError):
            contract.review_batch(anchor, plan, [], expected=0)
        with self.assertRaises(ValueError):
            contract.review_batch(anchor, other_plan, [])
        with self.assertRaises(ValueError):
            contract.review_batch(anchor, plan, [_obs(slot=1, asset_id="x1"), _obs(slot=1, asset_id="x2")], expected=2)
        with self.assertRaises(ValueError):
            contract.review_batch(anchor, plan, [_obs(slot=1, asset_id="dup"), _obs(slot=2, asset_id="dup")], expected=2)

    def test_18_review_batch_tie_review_required_within_margin(self) -> None:
        anchor = contract.Anchor("a1", "USER_ORIGINAL", True, False)
        plan = contract.plan_edit(anchor, "lighting")
        obs1 = _obs(slot=1, asset_id="c1", evidence="OBSERVED_IMAGE", scores=_valid_scores(4.05))
        obs2 = _obs(slot=2, asset_id="c2", evidence="OBSERVED_IMAGE", scores=_valid_scores(4.0))
        batch = contract.review_batch(anchor, plan, [obs1, obs2], expected=2)
        self.assertEqual(batch.status, "TIE_REVIEW_REQUIRED")
        self.assertIsNone(batch.selected_asset_id)

    def test_19_review_batch_user_accepted_vs_provisional_and_partial(self) -> None:
        anchor = contract.Anchor("a1", "USER_ORIGINAL", True, False)
        plan = contract.plan_edit(anchor, "lighting")
        top = _obs(
            slot=1, asset_id="c1", evidence="OBSERVED_IMAGE", scores=_valid_scores(5.0),
            independently_reviewed=True, accepted_by_user=True,
        )
        runner = _obs(slot=2, asset_id="c2", evidence="OBSERVED_IMAGE", scores=_valid_scores(3.0))
        accepted = contract.review_batch(anchor, plan, [top, runner], expected=2)
        self.assertEqual(accepted.status, "USER_ACCEPTED")
        self.assertEqual(accepted.selected_asset_id, "c1")

        partial = contract.review_batch(anchor, plan, [top, runner], expected=3)
        self.assertEqual(partial.status, "PARTIAL")

    def test_20_cli_process_plan_and_review_success(self) -> None:
        req = {
            "schema": "ace.ava.request.v1",
            "anchor": {
                "asset_id": "src_1",
                "provenance": "USER_ORIGINAL",
                "approved_by_user": True,
                "real_or_possible_person": False,
            },
            "axis": "camera",
            "expected": 1,
            "observations": [
                {
                    "slot": 1,
                    "asset_id": "out_1",
                    "image_type": "SINGLE_PHOTO",
                    "safety": "SAFE",
                    "evidence": "OBSERVED_IMAGE",
                    "identity": "UNKNOWN",
                    "drifted_axes": ["camera"],
                    "scores": _valid_scores(4.5),
                }
            ],
        }
        plan_out = cli.process("plan", req)
        self.assertEqual(plan_out["status"], "PLAN_ONLY")
        self.assertFalse(plan_out["native_generator_called"])
        rev_out = cli.process("review", req)
        self.assertEqual(rev_out["status"], "PROVISIONAL_SELECTION")
        self.assertEqual(rev_out["selected_asset_id"], "out_1")

    def test_21_cli_process_rejects_bad_schema_non_dict_and_string_drifted_axes(self) -> None:
        with self.assertRaises(ValueError):
            cli.process("plan", ["not_dict"])  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            cli.process("plan", {"schema": "wrong.v1"})
        req = {
            "schema": "ace.ava.request.v1",
            "anchor": {
                "asset_id": "src_1",
                "provenance": "USER_ORIGINAL",
                "approved_by_user": True,
                "real_or_possible_person": False,
            },
            "observations": [{"slot": 1, "drifted_axes": "camera"}],
        }
        with self.assertRaises(ValueError):
            cli.process("review", req)

    def test_22_cli_main_malformed_json_returns_exit_2_invalid_request(self) -> None:
        stdout = io.StringIO()
        with patch("sys.stdin", io.StringIO("{not valid json")), patch("sys.stdout", stdout):
            rc = cli.main(["plan"])
        self.assertEqual(rc, 2)
        parsed = json.loads(stdout.getvalue())
        self.assertEqual(parsed["status"], "INVALID_REQUEST")

    def test_23_cli_main_valid_json_returns_exit_0(self) -> None:
        payload = json.dumps(
            {
                "schema": "ace.ava.request.v1",
                "anchor": {
                    "asset_id": "src_1",
                    "provenance": "USER_ORIGINAL",
                    "approved_by_user": True,
                    "real_or_possible_person": False,
                },
            }
        )
        stdout = io.StringIO()
        with patch("sys.stdin", io.StringIO(payload)), patch("sys.stdout", stdout):
            rc = cli.main(["plan"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "PLAN_ONLY")

    def test_24_review_batch_blocked_overrides_qualified(self) -> None:
        anchor = contract.Anchor("a1", "USER_ORIGINAL", True, False)
        plan = contract.plan_edit(anchor, "lighting")
        q = _obs(slot=1, asset_id="c1", evidence="OBSERVED_IMAGE", scores=_valid_scores(5.0))
        b = _obs(slot=2, asset_id="c2", safety="BLOCKED")
        res = contract.review_batch(anchor, plan, [q, b], expected=2)
        self.assertEqual(res.status, "BLOCKED")
        self.assertIsNone(res.selected_asset_id)


if __name__ == "__main__":
    unittest.main()
