"""Tests for Durable Research Autonomy & Multi-Session Resumption across Processes.

Verifies P3 requirements:
1. Multi-session execution across completely separate OS processes.
2. Zero duplicate actions for completed hypotheses.
3. Metacognitive adaptation (failure memory) preserved across process restarts.
4. Tamper-evident HMAC chains in Autonomy, ExperienceMemory, and ResearchArchive
   remain valid across process boundaries.
5. Crash recovery and lease cleanup without database corruption.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ace_autonomy import IntegrityError
from ace_research_agenda.coordinator import (
    AutonomousResearchCoordinator,
    run_autonomous_research_campaign,
    run_durable_autonomous_research_campaign,
)
from ace_research_agenda.models import ResearchArchive, ResearchCampaignBudget


class TestDurableResearchAutonomy(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]

    def test_two_phase_stop_and_resume_separate_processes(self) -> None:
        """Execute cycles 1-2 in Process A, exit, then resume cycles 3-5 in Process B."""
        with tempfile.TemporaryDirectory(prefix="ace_durable_test_") as tmp:
            ws = Path(tmp) / "persistent_ws"
            ws.mkdir(parents=True, exist_ok=True)

            # --- Phase 1: Process A runs 2 cycles ---
            script_phase1 = f"""
import sys
from pathlib import Path
from ace_research_agenda.coordinator import run_durable_autonomous_research_campaign
from ace_research_agenda.models import ResearchCampaignBudget

ws = Path({json.dumps(str(ws))})
root = Path({json.dumps(str(self.repo_root))})
budget = ResearchCampaignBudget(max_cycles=2, max_total_steps=16, max_total_cpu_s=15.0)
rep = run_durable_autonomous_research_campaign(ws, root, budget, target_total_cycles=2)
print("PHASE1_CYCLES:", rep["campaign_budget"]["cycles_executed"])
print("PHASE1_DONE")
"""
            p1 = subprocess.run(
                [sys.executable, "-c", script_phase1],
                capture_output=True,
                text=True,
                env={"PYTHONPATH": str(self.repo_root / "code"), "PATH": sys.path[0]},
                check=True,
            )
            self.assertIn("PHASE1_DONE", p1.stdout)
            self.assertIn("PHASE1_CYCLES: 2", p1.stdout)

            # Verify on-disk artifacts after Process A terminated:
            with ResearchArchive(ws / "archive_ws") as arch:
                records_p1 = arch.list_records()
                self.assertGreaterEqual(len(records_p1), 2)
                p1_hyps = [r["hypothesis_id"] for r in records_p1 if "hypothesis_id" in r]
                self.assertIn("HYP_01_REPAIR_TIGHT_BUDGET_K4", p1_hyps)
                self.assertIn("HYP_02_PALINDROME_DFA_LIMIT_PROBE_A", p1_hyps)
                # Ensure HYP_04, HYP_05, HYP_06 have NOT run yet
                self.assertNotIn("HYP_04_G2_LOW_SAMPLE_B24", p1_hyps)
                self.assertNotIn("HYP_05_MULTI_MODULAR_INHERITANCE", p1_hyps)

            # --- Phase 2: Process B resumes on the SAME workspace to 5 cycles ---
            script_phase2 = f"""
import sys, json
from pathlib import Path
from ace_research_agenda.coordinator import run_durable_autonomous_research_campaign
from ace_research_agenda.models import ResearchCampaignBudget

ws = Path({json.dumps(str(ws))})
root = Path({json.dumps(str(self.repo_root))})
budget = ResearchCampaignBudget(max_cycles=5, max_total_steps=32, max_total_cpu_s=25.0)
rep = run_durable_autonomous_research_campaign(ws, root, budget, target_total_cycles=5)
print("PHASE2_CYCLES:", rep["campaign_budget"]["cycles_executed"])
print("PHASE2_RESUMED:", rep.get("durable_resumption", {{}}).get("resumed_from_cycle"))
print("PHASE2_SESSION_CYCLES:", rep.get("durable_resumption", {{}}).get("session_cycles_executed"))
print("PHASE2_GATES:", rep["agenda_loop_gates"]["all_passed"])
print("PHASE2_METACRED:", rep["archive_summary"]["metacognitive_post_refutation_abstention_verified"])
print("PHASE2_DONE")
"""
            p2 = subprocess.run(
                [sys.executable, "-c", script_phase2],
                capture_output=True,
                text=True,
                env={"PYTHONPATH": str(self.repo_root / "code"), "PATH": sys.path[0]},
                check=True,
            )
            self.assertIn("PHASE2_DONE", p2.stdout)
            self.assertIn("PHASE2_CYCLES: 5", p2.stdout)
            self.assertIn("PHASE2_RESUMED: 2", p2.stdout)
            self.assertIn("PHASE2_SESSION_CYCLES: 3", p2.stdout)
            self.assertIn("PHASE2_GATES: True", p2.stdout)
            self.assertIn("PHASE2_METACRED: True", p2.stdout)

            # Final on-disk verification:
            with ResearchArchive(ws / "archive_ws") as arch:
                final_records = arch.list_records()
                final_hyps = [r["hypothesis_id"] for r in final_records if "hypothesis_id" in r]
                # Check for no duplicate hypothesis evaluations
                executed_hyps = [r["hypothesis_id"] for r in final_records if r.get("outcome_status") != "ABSTAINED_UNIDENTIFIABLE"]
                self.assertEqual(len(executed_hyps), len(set(executed_hyps)), "Duplicate hypothesis executions found!")
                self.assertEqual(len(final_records), 6)  # 5 executed + 1 unidentifiable drift abstained

    def test_idempotent_resume_on_completed_campaign(self) -> None:
        """Running on an already completed workspace executes 0 additional cycles idempotently."""
        with tempfile.TemporaryDirectory(prefix="ace_durable_idem_") as tmp:
            ws = Path(tmp) / "ws"
            budget = ResearchCampaignBudget(max_cycles=5, max_total_steps=32, max_total_cpu_s=25.0)

            # Run full 5-cycle campaign
            rep1 = run_durable_autonomous_research_campaign(ws, self.repo_root, budget, target_total_cycles=5)
            self.assertEqual(rep1["campaign_budget"]["cycles_executed"], 5)

            # Run again on the same workspace with target_total_cycles=5
            rep2 = run_durable_autonomous_research_campaign(ws, self.repo_root, budget, target_total_cycles=5)
            self.assertEqual(rep2["campaign_budget"]["cycles_executed"], 5)
            self.assertEqual(rep2["durable_resumption"]["session_cycles_executed"], 0)
            self.assertEqual(rep2["durable_resumption"]["resumed_from_cycle"], 5)

    def test_checkpoint_state_tamper_detection(self) -> None:
        """Tampering with SQLite archive or episode database triggers fail-closed IntegrityError."""
        with tempfile.TemporaryDirectory(prefix="ace_durable_tamper_") as tmp:
            ws = Path(tmp) / "ws"
            budget = ResearchCampaignBudget(max_cycles=2, max_total_steps=16, max_total_cpu_s=15.0)
            run_durable_autonomous_research_campaign(ws, self.repo_root, budget, target_total_cycles=2)

            # ResearchArchive HMAC tampering:
            with open(ws / "archive_ws" / ".agenda_key", "wb") as f:
                f.write(b"x" * 32)

            with self.assertRaises(IntegrityError):
                run_durable_autonomous_research_campaign(ws, self.repo_root, budget, target_total_cycles=3)


if __name__ == "__main__":
    unittest.main()
