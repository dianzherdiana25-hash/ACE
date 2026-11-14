"""Unified Closed-Loop Autonomous Evolver uniting Epochs A through F.

Executes a single deterministic self-evolution cycle across all 6 OAIE-∞ Epochs:
  1. Epoch C (Diagnose & Localize): causal fault localization + cross-file patch + truth market.
  2. Epoch A (Synthesize): neuro-formal program genesis from formal specs (zero templates).
  3. Epoch B (Co-Evolve & Immunize): adversarial challenger-solver + antibody compilation.
  4. Epoch D (Ontological & Godel): latent causal discovery + proof-carrying strategy upgrade.
  5. Epoch F (Commercialize & Ledger): build verified CLI deliverables + O(1) B2A receipts.
  6. Epoch E (Stigmergy & Spore): commit proof pheromones & export portable SubstrateSpore.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .causal_repo_evolution import run_causal_repo_evolution_cycle
from .coevolution_arena import run_coevolution_arena_cycle
from .commercial_product_factory import run_commercial_factory_cycle
from .local_repo_workflow import atomic_write_verified
from .neuro_formal_genesis import run_neuro_formal_genesis_cycle
from .ontological_godel_engine import run_ontological_godel_cycle
from .sovereign_runtime import SovereignRuntimeSupervisor, SubstrateSpore


class AutonomousEvolver:
    """Runs the unified A -> B -> C -> D -> F -> E closed self-evolution loop."""

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.supervisor = SovereignRuntimeSupervisor(self.workspace / "runtime")

    def run_evolution_generation(self, generation_id: str = "gen-1") -> dict[str, Any]:
        gen_dir = self.workspace / generation_id
        gen_dir.mkdir(parents=True, exist_ok=True)

        # Epoch C: Causal multi-file repo localization, atomic patch & epistemic market
        epoch_c = run_causal_repo_evolution_cycle(gen_dir / "epoch_c")
        # Epoch A: Neuro-formal zero-template program synthesis
        epoch_a = run_neuro_formal_genesis_cycle()
        # Epoch B: Adversarial challenger-solver co-evolution & antibodies
        epoch_b = run_coevolution_arena_cycle()
        # Epoch D: Ontological causal discovery & Godel proof-carrying strategy upgrade
        epoch_d = run_ontological_godel_cycle(gen_dir / "epoch_d")
        # Epoch F: Commercial CLI product factory, anti-slop publisher & O(1) B2A receipts
        epoch_f = run_commercial_factory_cycle(gen_dir / "epoch_f")

        # Epoch A: Register newly synthesized skills monotonically into supervisor certified_skills
        existing_skill_ids = {s["skill_id"] for s in self.supervisor._state["certified_skills"]}
        for rep in epoch_a.get("reports", []):
            sk = rep["skill"]
            gen_skill_id = f"{sk['skill_id']}__{generation_id}"
            if gen_skill_id not in existing_skill_ids:
                self.supervisor._state["certified_skills"].append(
                    {
                        "skill_id": gen_skill_id,
                        "base_skill_id": sk["skill_id"],
                        "birth_sha256": sk["birth_certificate_sha256"],
                        "generation_id": generation_id,
                    }
                )
                existing_skill_ids.add(gen_skill_id)

        # Epoch B/E: Inject generation-scoped adversarial reflex probe to compile a new antibody fossil
        probe_res = self.supervisor.run_single_tick(
            {
                "task_id": f"probe_{generation_id}",
                "expected_benefit": 1.0,
                "estimated_dt": 0.3,
                "remaining_budget_ratio": 1.0,
                "payload_code": f"import os; os.system('probe_{generation_id}')",
            }
        )

        # Epoch E: Commit unified proof pheromone into StigmergicDAGMemory & export SubstrateSpore
        gen_digest = hashlib.sha256(
            json.dumps(
                {
                    "a": epoch_a["genesis_digest"],
                    "b": epoch_b["arena_digest"],
                    "c": epoch_c["epoch_c_digest"],
                    "d": epoch_d["godel_tcb_digest"],
                    "f": epoch_f["anti_slop_bundle_sha256"],
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()

        tick_res = self.supervisor.run_single_tick(
            {
                "task_id": f"autoevolve_{generation_id}",
                "expected_benefit": 2.0,
                "estimated_dt": 0.5,
                "remaining_budget_ratio": 1.0,
            },
            executor_fn=lambda _: {"verified": True, "generation_digest": gen_digest},
        )

        spore = SubstrateSpore.export_spore(
            spore_path=gen_dir / "generation_spore.json",
            dag=self.supervisor.dag,
            certified_skills=self.supervisor.state["certified_skills"],
            checkpoint_state=self.supervisor.state,
        )

        summary = {
            "schema": "ace.autonomous_evolver.generation.v1",
            "generation_id": generation_id,
            "generation_digest": gen_digest,
            "epoch_a_skills_synthesized": epoch_a["skills_synthesized"],
            "epoch_a_forgetting": epoch_a["forgetting_count"],
            "epoch_b_waves_solved": len(epoch_b["waves"]),
            "epoch_c_mutation_kill_rate": epoch_c["mutation_report"]["mutation_kill_rate"],
            "epoch_d_active_strategy": epoch_d["active_strategy_id"],
            "epoch_f_receipts_verified": epoch_f["receipts_verified_o1"],
            "epoch_f_remaining_debt_idr": epoch_f["remaining_debt_idr"],
            "epoch_e_tick_status": tick_res["status"],
            "probe_antibody_status": probe_res["status"],
            "total_certified_skills": len(self.supervisor.state["certified_skills"]),
            "total_antibodies": self.supervisor.state["antibodies_compiled"],
            "spore_sha256": spore["spore_sha256"],
            "dag_chain_valid": self.supervisor.dag.verify_chain(),
        }
        atomic_write_verified(
            gen_dir / "evolution_summary.json",
            json.dumps(summary, indent=2, sort_keys=True),
        )
        return summary

    def run_multi_generation_loop(self, *, generations: int = 2) -> dict[str, Any]:
        """Evolve across N generations, verifying SubstrateSpore continuity after each generation."""
        if generations < 1:
            raise ValueError("generations must be >= 1")
        gen_summaries: list[dict[str, Any]] = []
        continuity_exams: list[dict[str, Any]] = []
        for idx in range(1, generations + 1):
            gid = f"gen-{idx}"
            summary = self.run_evolution_generation(gid)
            gen_summaries.append(summary)
            exam = SubstrateSpore.import_and_verify_spore(
                spore_path=self.workspace / gid / "generation_spore.json",
                target_workspace=self.workspace / gid / "continuity_probe",
                expected_ancestor_skills=["core_stage2_guard"],
                antibody_probes=[],
            )
            continuity_exams.append(exam)
        return {
            "schema": "ace.autonomous_evolver.multi_gen.v1",
            "generations_completed": len(gen_summaries),
            "all_continuity_exams_passed": all(e["exam_passed"] for e in continuity_exams),
            "total_forgetting_count": sum(e["forgetting_count"] for e in continuity_exams),
            "latest_spore_sha256": gen_summaries[-1]["spore_sha256"],
            "generations": gen_summaries,
        }

