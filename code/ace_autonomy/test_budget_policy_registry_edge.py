"""Edge-case unit tests for ace_autonomy budget.py, policy.py, and registry.py."""
from __future__ import annotations

import hashlib
import hmac
import math
import sqlite3
from unittest.mock import patch
import unittest

from ace_autonomy.budget import BudgetController, BudgetUsage
from ace_autonomy.errors import BudgetExhaustedError, IntegrityError, PolicyError
from ace_autonomy.policy import BudgetCeiling, canonical, digest
from ace_autonomy.registry import CapabilityRegistry


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE capability_registry (
            cap_id TEXT PRIMARY KEY,
            goal_id TEXT NOT NULL,
            step_index INTEGER NOT NULL,
            kind TEXT NOT NULL,
            artifact_digest TEXT NOT NULL,
            domain_scope TEXT NOT NULL,
            status TEXT NOT NULL,
            event_signature TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            signature TEXT NOT NULL
        )
        """
    )
    return conn


def _hmac_sign(payload: object) -> str:
    return hmac.new(b"test-secret", canonical(payload).encode("utf-8"), hashlib.sha256).hexdigest()


class TestAutonomyBudgetPolicyRegistryEdgeCases(unittest.TestCase):
    def test_01_budget_usage_roundtrip_defaults_and_from_none(self) -> None:
        empty = BudgetUsage.from_dict(None)
        self.assertEqual(empty.steps_used, 0)
        self.assertEqual(empty.retries_by_step, {})
        raw = {"steps_used": 2, "candidates_staged": 1, "wall_seconds_used": 1.25, "cpu_seconds_used": 0.5, "retries_by_step": {"0": 1}}
        rt = BudgetUsage.from_dict(raw).to_dict()
        self.assertEqual(rt["steps_used"], 2)
        self.assertEqual(rt["retries_by_step"], {"0": 1})

    def test_02_check_pre_step_raises_on_step_ceiling(self) -> None:
        ctrl = BudgetController(BudgetCeiling(max_steps=3), BudgetUsage(steps_used=3))
        with self.assertRaisesRegex(BudgetExhaustedError, "step budget exhausted"):
            ctrl.check_pre_step(3, {"tool": "inspect_file"})

    def test_03_check_pre_step_candidate_ceiling_only_blocks_stage_candidate(self) -> None:
        ctrl = BudgetController(BudgetCeiling(max_candidates=2), BudgetUsage(candidates_staged=2))
        ctrl.check_pre_step(0, {"tool": "inspect_file"})
        with self.assertRaisesRegex(BudgetExhaustedError, "candidate budget exhausted"):
            ctrl.check_pre_step(0, {"tool": "stage_candidate"})

    def test_04_check_pre_step_raises_on_wall_and_cpu_ceilings(self) -> None:
        ctrl_w = BudgetController(BudgetCeiling(wall_seconds=5.0), BudgetUsage(wall_seconds_used=5.0))
        with self.assertRaisesRegex(BudgetExhaustedError, "wall budget exhausted"):
            ctrl_w.check_pre_step(0, {})
        ctrl_c = BudgetController(BudgetCeiling(cpu_seconds=2.0), BudgetUsage(cpu_seconds_used=2.1))
        with self.assertRaisesRegex(BudgetExhaustedError, "cpu budget exhausted"):
            ctrl_c.check_pre_step(0, {})

    def test_05_remaining_wall_and_cpu_clamp_to_minimum_positive(self) -> None:
        ctrl = BudgetController(BudgetCeiling(wall_seconds=1.0, cpu_seconds=1.0), BudgetUsage(wall_seconds_used=5.0, cpu_seconds_used=3.0))
        self.assertEqual(ctrl.remaining_wall_seconds(), 0.001)
        self.assertEqual(ctrl.remaining_cpu_seconds(), 0.001)

    def test_06_retry_budget_blocks_external_and_enforces_local_ceiling(self) -> None:
        ctrl = BudgetController(BudgetCeiling(max_retries_per_step=1))
        self.assertFalse(ctrl.can_retry_local_step(0, is_external=True))
        self.assertTrue(ctrl.can_retry_local_step(0, is_external=False))
        ctrl.record_retry(0)
        self.assertFalse(ctrl.can_retry_local_step(0, is_external=False))
        self.assertTrue(ctrl.can_retry_local_step(1, is_external=False))

    def test_07_finish_measurement_clamps_negative_deltas_and_tracks_counts(self) -> None:
        ctrl = BudgetController(BudgetCeiling(wall_seconds=10.0, cpu_seconds=10.0))
        with patch("ace_autonomy.budget.time.monotonic", return_value=50.0), \
                patch("ace_autonomy.budget.total_process_cpu_seconds", return_value=5.0):
            ctrl.finish_measurement((100.0, 10.0), step_completed=True, staged_candidate=True)
        self.assertEqual(ctrl.usage.wall_seconds_used, 0.0)
        self.assertEqual(ctrl.usage.cpu_seconds_used, 0.0)
        self.assertEqual(ctrl.usage.steps_used, 1)
        self.assertEqual(ctrl.usage.candidates_staged, 1)

    def test_08_finish_measurement_raises_when_wall_or_cpu_exceeded(self) -> None:
        ctrl_w = BudgetController(BudgetCeiling(wall_seconds=1.0, cpu_seconds=10.0))
        with patch("ace_autonomy.budget.time.monotonic", return_value=12.0), \
                patch("ace_autonomy.budget.total_process_cpu_seconds", return_value=1.0):
            with self.assertRaisesRegex(BudgetExhaustedError, "wall budget exceeded"):
                ctrl_w.finish_measurement((10.0, 1.0), step_completed=True)

        ctrl_c = BudgetController(BudgetCeiling(wall_seconds=10.0, cpu_seconds=1.0))
        with patch("ace_autonomy.budget.time.monotonic", return_value=10.1), \
                patch("ace_autonomy.budget.total_process_cpu_seconds", return_value=3.0):
            with self.assertRaisesRegex(BudgetExhaustedError, "cpu budget exceeded"):
                ctrl_c.finish_measurement((10.0, 1.0), step_completed=False)

    def test_09_budget_ceiling_rejects_bool_coercion_as_int(self) -> None:
        for field in ("max_steps", "max_candidates", "max_retries_per_step"):
            with self.assertRaises(PolicyError):
                BudgetCeiling.from_dict({field: True})

    def test_10_budget_ceiling_rejects_out_of_bounds_steps_candidates_retries(self) -> None:
        with self.assertRaises(PolicyError):
            BudgetCeiling.from_dict({"max_steps": 0})
        with self.assertRaises(PolicyError):
            BudgetCeiling.from_dict({"max_steps": 9})
        with self.assertRaises(PolicyError):
            BudgetCeiling.from_dict({"max_candidates": -1})
        with self.assertRaises(PolicyError):
            BudgetCeiling.from_dict({"max_candidates": 5})
        with self.assertRaises(PolicyError):
            BudgetCeiling.from_dict({"max_retries_per_step": 3})

    def test_11_budget_ceiling_rejects_nan_inf_and_zero_wall_cpu(self) -> None:
        for bad in (math.nan, math.inf, -math.inf, 0.0, 0.0005, 180.1, True):
            with self.assertRaises(PolicyError):
                BudgetCeiling.from_dict({"wall_seconds": bad})
        for bad_cpu in (math.nan, 0.0, 60.1):
            with self.assertRaises(PolicyError):
                BudgetCeiling.from_dict({"cpu_seconds": bad_cpu})

    def test_12_budget_ceiling_rejects_non_dict_and_unknown_fields(self) -> None:
        with self.assertRaises(PolicyError):
            BudgetCeiling.from_dict(["bad"])  # type: ignore[arg-type]
        with self.assertRaises(PolicyError):
            BudgetCeiling.from_dict({"unknown_quota": 1})

    def test_13_canonical_rejects_nan_and_sorts_keys_deterministically(self) -> None:
        self.assertEqual(canonical({"b": 1, "a": 2}), '{"a":2,"b":1}')
        with self.assertRaises(ValueError):
            canonical({"x": float("nan")})

    def test_14_digest_identical_for_reordered_dict_keys(self) -> None:
        self.assertEqual(digest({"k1": 1, "k2": 2}), digest({"k2": 2, "k1": 1}))

    def test_15_registry_registers_lists_and_verifies_valid_capability(self) -> None:
        db = _make_db()
        reg = CapabilityRegistry(db, _hmac_sign)
        cap_id = reg.register_verified(
            goal_id="g1",
            step_index=0,
            kind="tool_script",
            artifact_digest="a" * 64,
            domain_scope="tools",
            status="VERIFIED_OPERATIONAL",
            event_signature="sig_ev_1",
            metadata={"score": 1},
        )
        items = reg.list_capabilities()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["cap_id"], cap_id)
        reg.verify_all({"sig_ev_1"})

    def test_16_registry_rejects_unsupported_status_on_register(self) -> None:
        reg = CapabilityRegistry(_make_db(), _hmac_sign)
        with self.assertRaisesRegex(IntegrityError, "unsupported capability status"):
            reg.register_verified(
                goal_id="g1",
                step_index=0,
                kind="k",
                artifact_digest="a" * 64,
                domain_scope="tools",
                status="UNVERIFIED",
                event_signature="sig_1",
                metadata={},
            )

    def test_17_registry_verify_all_rejects_unknown_event_signature(self) -> None:
        reg = CapabilityRegistry(_make_db(), _hmac_sign)
        reg.register_verified(
            goal_id="g1",
            step_index=0,
            kind="k",
            artifact_digest="a" * 64,
            domain_scope="tools",
            status="STAGED_CANDIDATE_UNEXECUTED",
            event_signature="sig_missing",
            metadata={},
        )
        with self.assertRaisesRegex(IntegrityError, "unknown or unverified event signature"):
            reg.verify_all({"sig_other"})

    def test_18_registry_verify_all_detects_tampered_row_signature(self) -> None:
        db = _make_db()
        reg = CapabilityRegistry(db, _hmac_sign)
        cap_id = reg.register_verified(
            goal_id="g1",
            step_index=0,
            kind="k",
            artifact_digest="a" * 64,
            domain_scope="tools",
            status="VERIFIED_OPERATIONAL",
            event_signature="sig_1",
            metadata={"x": 1},
        )
        db.execute("UPDATE capability_registry SET domain_scope = 'evil' WHERE cap_id = ?", (cap_id,))
        with self.assertRaisesRegex(IntegrityError, "signature tampered"):
            reg.verify_all({"sig_1"})

    def test_19_registry_verify_all_detects_tampered_db_status(self) -> None:
        db = _make_db()
        reg = CapabilityRegistry(db, _hmac_sign)
        cap_id = reg.register_verified(
            goal_id="g1",
            step_index=0,
            kind="k",
            artifact_digest="a" * 64,
            domain_scope="tools",
            status="VERIFIED_OPERATIONAL",
            event_signature="sig_1",
            metadata={},
        )
        db.execute("UPDATE capability_registry SET status = 'ADMIN_OVERRIDE' WHERE cap_id = ?", (cap_id,))
        with self.assertRaisesRegex(IntegrityError, "invalid capability_registry status"):
            reg.verify_all({"sig_1"})

    def test_20_registry_list_orders_by_step_index_then_cap_id(self) -> None:
        reg = CapabilityRegistry(_make_db(), _hmac_sign)
        reg.register_verified(
            goal_id="g1", step_index=2, kind="b", artifact_digest="2" * 64,
            domain_scope="tools", status="VERIFIED_OPERATIONAL", event_signature="s", metadata={},
        )
        reg.register_verified(
            goal_id="g1", step_index=1, kind="a", artifact_digest="1" * 64,
            domain_scope="tools", status="VERIFIED_OPERATIONAL", event_signature="s", metadata={},
        )
        listed = reg.list_capabilities()
        self.assertEqual([x["step_index"] for x in listed], [1, 2])

    def test_21_budget_ceiling_boundary_values_allowed(self) -> None:
        bc = BudgetCeiling.from_dict({"max_steps": 1, "max_candidates": 0, "max_retries_per_step": 0, "wall_seconds": 0.001, "cpu_seconds": 60.0})
        self.assertEqual(bc.max_steps, 1)
        self.assertEqual(bc.max_candidates, 0)
        self.assertEqual(bc.wall_seconds, 0.001)
        self.assertEqual(bc.cpu_seconds, 60.0)

    def test_22_budget_ceiling_to_dict_casts_floats_cleanly(self) -> None:
        d = BudgetCeiling(wall_seconds=10, cpu_seconds=5).to_dict()  # type: ignore[arg-type]
        self.assertIsInstance(d["wall_seconds"], float)
        self.assertIsInstance(d["cpu_seconds"], float)

    def test_23_budget_usage_to_dict_rounds_to_six_decimals(self) -> None:
        u = BudgetUsage(wall_seconds_used=1.123456789, cpu_seconds_used=0.987654321)
        d = u.to_dict()
        self.assertEqual(d["wall_seconds_used"], 1.123457)
        self.assertEqual(d["cpu_seconds_used"], 0.987654)

    def test_24_registry_re_register_same_identity_updates_idempotently(self) -> None:
        reg = CapabilityRegistry(_make_db(), _hmac_sign)
        id1 = reg.register_verified(
            goal_id="g1", step_index=0, kind="k", artifact_digest="a" * 64,
            domain_scope="tools", status="STAGED_CANDIDATE_UNEXECUTED", event_signature="s1", metadata={"v": 1},
        )
        id2 = reg.register_verified(
            goal_id="g1", step_index=0, kind="k", artifact_digest="a" * 64,
            domain_scope="tools", status="VERIFIED_OPERATIONAL", event_signature="s2", metadata={"v": 2},
        )
        self.assertEqual(id1, id2)
        items = reg.list_capabilities()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["metadata"], {"v": 2})


if __name__ == "__main__":
    unittest.main()
