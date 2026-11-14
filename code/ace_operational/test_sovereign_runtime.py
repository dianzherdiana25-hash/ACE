"""Tests for EPOCH E — Mycelial Stigmergy, SubstrateSpore & Non-Stop Sovereign Runtime."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from ace_operational.sovereign_runtime import (
    SovereignRuntimeSupervisor,
    SporeContinuityError,
    SubstrateSpore,
)


class SovereignRuntimeTests(unittest.TestCase):
    def test_non_stop_fault_isolation_voi_austerity_and_idempotent_restart(self) -> None:
        with tempfile.TemporaryDirectory() as d1:
            ws = Path(d1)
            sup = SovereignRuntimeSupervisor(ws)

            def flaky_executor(task: dict) -> dict:
                if task.get("inject_crash"):
                    raise RuntimeError("Simulated sub-brain crash!")
                return {"verified": True}

            tasks = [
                {"task_id": "t1_ok", "expected_benefit": 1.0, "estimated_dt": 0.5, "remaining_budget_ratio": 1.0},
                {"task_id": "t2_crash", "expected_benefit": 1.0, "estimated_dt": 0.5, "remaining_budget_ratio": 1.0, "inject_crash": True},
                {"task_id": "t3_reflex", "expected_benefit": 1.0, "estimated_dt": 0.5, "remaining_budget_ratio": 1.0, "payload_code": "import os; os.system('id')"},
                {"task_id": "t4_low_budget", "expected_benefit": 1.0, "estimated_dt": 0.5, "remaining_budget_ratio": 0.15},
                {"task_id": "t5_ok_after_faults", "expected_benefit": 1.0, "estimated_dt": 0.5, "remaining_budget_ratio": 1.0},
            ]
            results = sup.run_cycles(tasks, executor_fn=flaky_executor)

            self.assertEqual([r["status"] for r in results], [
                "tactical_verified",
                "quarantined_into_antibody",
                "quarantined_into_antibody",
                "metabolic_austerity_consolidation",
                "tactical_verified",
            ])
            self.assertEqual(sup.state["unhandled_crashes"], 0)
            self.assertEqual(sup.state["antibodies_compiled"], 2)
            self.assertEqual(sup.state["austerity_ticks"], 1)
            self.assertTrue(sup.dag.verify_chain())

            # Restart recovery & idempotency: replaying t1_ok must skip without duplicating side effects
            sup_restarted = SovereignRuntimeSupervisor(ws)
            replay = sup_restarted.run_single_tick(tasks[0], executor_fn=flaky_executor)
            self.assertEqual(replay["status"], "idempotent_skip")
            self.assertEqual(sup_restarted.state["cycle_count"], 5)

            # WorkOrderBridge zero-API export & fail-closed verification
            order = sup_restarted.work_bridge.export_work_order(
                order_id="wo-epoch-f",
                goal="Build commercial factory",
                target_files=["code/ace_operational/commercial_product_factory.py"],
                acceptance_checks=["unittest"],
                forbidden_paths=["code/ace_runtime/"],
            )
            self.assertTrue((ws / "ACE_WORK_ORDER.json").exists())
            self.assertEqual(len(order["order_sha256"]), 64)
            bad_sub = sup_restarted.work_bridge.verify_work_order_submission(
                order_id="wo-epoch-f",
                changed_files=["code/ace_runtime/forbidden.py"],
                forbidden_paths=["code/ace_runtime/"],
                checks_passed=True,
            )
            self.assertFalse(bad_sub["accepted"])

    def test_substrate_spore_migration_and_tamper_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
            sup = SovereignRuntimeSupervisor(src_dir)
            sup.run_cycles([
                {"task_id": "s1", "expected_benefit": 1.0, "estimated_dt": 0.4, "remaining_budget_ratio": 1.0},
                {"task_id": "s2_fault", "expected_benefit": 1.0, "estimated_dt": 0.4, "remaining_budget_ratio": 1.0, "payload_code": "subprocess.Popen('sh')"},
                {"task_id": "s3", "expected_benefit": 1.0, "estimated_dt": 0.4, "remaining_budget_ratio": 1.0},
            ])
            self.assertTrue(sup.spore_path.exists())

            exam = SubstrateSpore.import_and_verify_spore(
                spore_path=sup.spore_path,
                target_workspace=dst_dir,
                expected_ancestor_skills=["core_stage2_guard"],
                antibody_probes=["fault::PermissionError::s2_fault"],
            )
            self.assertTrue(exam["exam_passed"])
            self.assertEqual(exam["forgetting_count"], 0)

            # Tamper spore SHA-256 and ensure Succession Continuity Exam fails closed
            tampered = sup.spore_path.read_text(encoding="utf-8").replace(exam["spore_sha256"], "f" * 64)
            sup.spore_path.write_text(tampered, encoding="utf-8")
            with self.assertRaises(SporeContinuityError):
                SubstrateSpore.import_and_verify_spore(
                    spore_path=sup.spore_path,
                    target_workspace=dst_dir,
                    expected_ancestor_skills=["core_stage2_guard"],
                    antibody_probes=["fault::PermissionError::s2_fault"],
                )


if __name__ == "__main__":
    unittest.main()
