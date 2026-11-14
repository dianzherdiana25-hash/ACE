"""Unified Zero-Theater Autonomous Evolver uniting formal synthesis, co-evolution,
causal localization, Godel meta-modification, Compositional OAIE, passive external-AI
work-order emission, and behavioral SubstrateSpore continuity verification.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ace_component_synthesis.component_synthesizer import TYPE_INT

from .causal_repo_evolution import run_causal_repo_evolution_cycle
from .coevolution_arena import run_coevolution_arena_cycle
from .compositional_oaie import CompositionalOAIERunner
from .evolution_mission_loop import PassiveEvolutionPlanner
from .local_repo_workflow import atomic_write_verified
from .neuro_formal_genesis import (
    FormalSkillSpec,
    SpecDrivenProgramSynthesizer,
    run_neuro_formal_genesis_cycle,
)
from .oaie_unlimited import AutopoieticSkillForge
from .ontological_godel_engine import run_ontological_godel_cycle
from .sovereign_runtime import SovereignRuntimeSupervisor, SubstrateSpore


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def generate_procedural_skill_spec(gen_idx: int) -> FormalSkillSpec:
    """Generate a novel behavioral FormalSkillSpec parameterized by generation index."""
    mode = gen_idx % 3
    if mode == 1:
        k_add = 2 + (gen_idx % 17)
        k_mul = 2 + (gen_idx % 5)
        fn = lambda x, y, _a=k_add, _m=k_mul: (x * _m) + _a
        shown = tuple((((x, y), fn(x, y)) for x, y in ((1, 0), (3, 2), (5, 4), (0, 7))))
        holdout = tuple((((x, y), fn(x, y)) for x, y in ((8, 1), (10, 5), (2, 9))))
        return FormalSkillSpec(
            skill_id=f"proc_pricing_curve_g{gen_idx}",
            title=f"Procedural Pricing Curve Gen-{gen_idx} (x*{k_mul}+{k_add})",
            domain="procedural_pricing",
            entrypoint=f"pricing_curve_g{gen_idx}",
            arg_names=("x", "y"),
            return_type=TYPE_INT,
            shown_io=shown,
            holdout_io=holdout,
            constants=((k_add, TYPE_INT), (k_mul, TYPE_INT)),
        )
    if mode == 2:
        limit = 50 + (gen_idx * 5)
        fn = lambda x, y, _lim=limit: (x - y) + _lim
        shown = tuple((((x, y), fn(x, y)) for x, y in ((10, 2), (25, 5), (0, 3), (7, 7))))
        holdout = tuple((((x, y), fn(x, y)) for x, y in ((30, 10), (15, 0), (40, 12))))
        return FormalSkillSpec(
            skill_id=f"proc_margin_delta_g{gen_idx}",
            title=f"Procedural Margin Delta Gen-{gen_idx} ((x-y)+{limit})",
            domain="procedural_guardrail",
            entrypoint=f"margin_delta_g{gen_idx}",
            arg_names=("x", "y"),
            return_type=TYPE_INT,
            shown_io=shown,
            holdout_io=holdout,
            constants=((limit, TYPE_INT),),
        )
    bonus = 3 + (gen_idx % 19)
    fn = lambda x, y, _b=bonus: (x * y) + _b
    shown = tuple((((x, y), fn(x, y)) for x, y in ((2, 3), (4, 5), (0, 6), (7, 1))))
    holdout = tuple((((x, y), fn(x, y)) for x, y in ((6, 6), (9, 2), (1, 0))))
    return FormalSkillSpec(
        skill_id=f"proc_load_score_g{gen_idx}",
        title=f"Procedural Load Score Gen-{gen_idx} (x*y+{bonus})",
        domain="procedural_telemetry",
        entrypoint=f"load_score_g{gen_idx}",
        arg_names=("x", "y"),
        return_type=TYPE_INT,
        shown_io=shown,
        holdout_io=holdout,
        constants=((bonus, TYPE_INT),),
    )


class AutonomousEvolver:
    """Runs the unified, zero-theater self-evolution loop with causal lineage and passive work orders."""

    def __init__(
        self,
        workspace: str | Path,
        *,
        repo_root: str | Path | None = None,
        scan_subpath: str = "code",
    ) -> None:
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.repo_root = Path(repo_root).resolve() if repo_root else _default_repo_root()
        self.scan_subpath = scan_subpath
        self.supervisor = SovereignRuntimeSupervisor(self.workspace / "runtime")
        self.planner = PassiveEvolutionPlanner(
            self.workspace / "passive_evolution",
            self.repo_root,
            scan_subpath=scan_subpath,
        )

    def _synthesize_verified_skill(self, gen_dir: Path, gen_idx: int) -> tuple[Any, dict[str, Any]]:
        proc_spec = generate_procedural_skill_spec(gen_idx)
        proc_forge = AutopoieticSkillForge()
        proc_skill, _ = SpecDrivenProgramSynthesizer().synthesize_from_spec(proc_spec, proc_forge)
        skills_dir = gen_dir / "synthesized_skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_verified(skills_dir / f"{proc_skill.skill_id}.py", proc_skill.source_code + "\n")

        cases = [[list(args), expected] for args, expected in proc_spec.holdout_io]
        skill_entry = {
            "skill_id": proc_skill.skill_id,
            "entrypoint": proc_spec.entrypoint,
            "birth_sha256": proc_skill.birth_certificate_sha256,
            "source_sha256": hashlib.sha256(proc_skill.source_code.encode("utf-8")).hexdigest(),
            "source_code": proc_skill.source_code,
            "verification_cases": cases,
            "generation_idx": gen_idx,
        }
        checked, failures = SubstrateSpore._verify_skill_behavior(skill_entry)
        if checked != len(cases) or failures > 0:
            raise RuntimeError(
                f"Synthesized procedural skill {proc_skill.skill_id} failed holdout check: {failures}/{checked}"
            )
        return proc_skill, skill_entry

    def _evaluate_and_commit_tick(
        self,
        *,
        generation_id: str,
        proc_skill: Any,
        epoch_a: dict[str, Any],
        epoch_b: dict[str, Any],
        epoch_c: dict[str, Any],
        epoch_d: dict[str, Any],
        comp_report: dict[str, Any] | None,
        passive_mission: dict[str, Any],
    ) -> tuple[str, tuple[str, ...], dict[str, Any]]:
        prev_proofs = self.supervisor.dag.nodes("proof_pheromone")
        parent_ids = (prev_proofs[-1].node_id,) if prev_proofs else ()

        epoch_a_ok = epoch_a["forgetting_count"] == 0 and epoch_a["skills_synthesized"] >= 4
        epoch_b_ok = (
            bool(epoch_b.get("waves"))
            and epoch_b.get("forgetting_count") == 0
            and int(epoch_b.get("cumulative_solved", 0)) == int(epoch_b.get("cumulative_total", -1))
        )
        epoch_c_ok = epoch_c["mutation_report"]["mutation_kill_rate"] >= 1.0
        epoch_d_ok = bool(epoch_d.get("active_strategy_id"))
        comp_ok = True if comp_report is None else (
            comp_report["overall_verdict"] == "COMPOSITIONAL_OAIE_VERIFIED"
            and comp_report["spore_continuity_exam"]["forgetting_count"] == 0
        )

        gen_digest = hashlib.sha256(
            json.dumps(
                {
                    "a": epoch_a["genesis_digest"],
                    "a_proc": proc_skill.birth_certificate_sha256,
                    "b": epoch_b["arena_digest"],
                    "c": epoch_c["epoch_c_digest"],
                    "d": epoch_d["godel_tcb_digest"],
                    "comp": comp_report["spore_sha256"] if comp_report else None,
                    "mission_sha": passive_mission.get("order_sha256"),
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()

        def _gate_evaluator(_: dict[str, Any]) -> dict[str, Any]:
            all_ok = epoch_a_ok and epoch_b_ok and epoch_c_ok and epoch_d_ok and comp_ok
            return {
                "verified": all_ok,
                "failure_reason": "" if all_ok else "subsystem_verification_failed",
                "generation_digest": gen_digest,
                "novel_skill_id": proc_skill.skill_id,
                "parent_ids": parent_ids,
                "passive_order_id": passive_mission.get("order_id"),
            }

        tick_res = self.supervisor.run_single_tick(
            {
                "task_id": f"autoevolve_{generation_id}",
                "expected_benefit": 2.0,
                "estimated_dt": 0.5,
                "remaining_budget_ratio": 1.0,
            },
            executor_fn=_gate_evaluator,
        )
        if tick_res["status"] != "tactical_verified":
            raise RuntimeError(f"Generation {generation_id} failed verification gate: {tick_res}")
        return gen_digest, parent_ids, tick_res

    def run_evolution_generation(
        self,
        generation_id: str = "gen-1",
        *,
        include_compositional_oaie: bool = True,
    ) -> dict[str, Any]:
        """Run one empirical evolution generation, fail-closed on any regression or gap."""
        gen_dir = self.workspace / generation_id
        gen_dir.mkdir(parents=True, exist_ok=True)
        digits = "".join(ch for ch in generation_id if ch.isdigit())
        gen_idx = int(digits) if digits else (self.supervisor.state["cycle_count"] + 1)

        epoch_c = run_causal_repo_evolution_cycle(gen_dir / "epoch_c")
        epoch_a = run_neuro_formal_genesis_cycle()
        proc_skill, skill_entry = self._synthesize_verified_skill(gen_dir, gen_idx)
        epoch_b = run_coevolution_arena_cycle()
        epoch_d = run_ontological_godel_cycle(gen_dir / "epoch_d")

        comp_report: dict[str, Any] | None = None
        comp_report_path: Path | None = None
        if include_compositional_oaie:
            comp_report = CompositionalOAIERunner(gen_dir / "compositional_oaie").run(include_falsification=True)
            comp_report_path = gen_dir / "compositional_oaie" / "compositional_oaie_report.json"

        passive_mission = self.planner.plan_next_evolution(compositional_report_path=comp_report_path)

        existing_ids = {s["skill_id"] for s in self.supervisor._state["certified_skills"]}
        if proc_skill.skill_id not in existing_ids:
            self.supervisor._state["certified_skills"].append({**skill_entry, "generation_id": generation_id})

        probe_res = self.supervisor.run_single_tick(
            {
                "task_id": f"probe_{generation_id}",
                "expected_benefit": 1.0,
                "estimated_dt": 0.3,
                "remaining_budget_ratio": 1.0,
                "payload_code": f"import os; os.system('probe_{generation_id}')",
            }
        )

        gen_digest, parent_ids, tick_res = self._evaluate_and_commit_tick(
            generation_id=generation_id,
            proc_skill=proc_skill,
            epoch_a=epoch_a,
            epoch_b=epoch_b,
            epoch_c=epoch_c,
            epoch_d=epoch_d,
            comp_report=comp_report,
            passive_mission=passive_mission,
        )

        spore_path = gen_dir / "generation_spore.json"
        spore = SubstrateSpore.export_spore(
            spore_path=spore_path,
            dag=self.supervisor.dag,
            certified_skills=self.supervisor.state["certified_skills"],
            checkpoint_state=self.supervisor.state,
        )
        exam = SubstrateSpore.import_and_verify_spore(
            spore_path=spore_path,
            target_workspace=gen_dir / "continuity_probe",
            expected_ancestor_skills=["core_stage2_guard", proc_skill.skill_id],
            antibody_probes=[],
        )
        if not exam["exam_passed"] or exam["forgetting_count"] != 0:
            raise RuntimeError(f"Generation {generation_id} spore continuity exam failed: {exam}")

        summary = {
            "schema": "ace.autonomous_evolver.generation.v2",
            "generation_id": generation_id,
            "generation_digest": gen_digest,
            "novel_skill_id": proc_skill.skill_id,
            "novel_skill_birth_sha256": proc_skill.birth_certificate_sha256,
            "novel_skill_source": proc_skill.source_code,
            "epoch_a_skills_synthesized": epoch_a["skills_synthesized"] + 1,
            "epoch_a_forgetting": epoch_a["forgetting_count"],
            "epoch_b_waves_solved": len(epoch_b["waves"]),
            "epoch_c_mutation_kill_rate": epoch_c["mutation_report"]["mutation_kill_rate"],
            "epoch_d_active_strategy": epoch_d["active_strategy_id"],
            "compositional_oaie_verdict": comp_report["overall_verdict"] if comp_report else "SKIPPED",
            "passive_mission_status": passive_mission["status"],
            "passive_order_id": passive_mission.get("order_id"),
            "passive_work_order_md": passive_mission.get("work_order_md_path"),
            "epoch_e_tick_status": tick_res["status"],
            "probe_antibody_status": probe_res["status"],
            "parent_ids": list(parent_ids),
            "causal_lineage_edges": sum(len(n.parent_ids) for n in self.supervisor.dag.nodes()),
            "total_certified_skills": len(self.supervisor.state["certified_skills"]),
            "total_antibodies": self.supervisor.state["antibodies_compiled"],
            "spore_sha256": spore["spore_sha256"],
            "spore_behavioral_checks_passed": exam["behavioral_checks_passed"],
            "forgetting_count": exam["forgetting_count"],
            "dag_chain_valid": self.supervisor.dag.verify_chain(),
        }
        atomic_write_verified(gen_dir / "evolution_summary.json", json.dumps(summary, indent=2, sort_keys=True))
        return summary

    def run_multi_generation_loop(
        self,
        *,
        generations: int = 2,
        include_compositional_oaie: bool = True,
    ) -> dict[str, Any]:
        """Evolve across N generations, verifying SubstrateSpore continuity after each generation."""
        if generations < 1:
            raise ValueError("generations must be >= 1")
        gen_summaries: list[dict[str, Any]] = []
        continuity_exams: list[dict[str, Any]] = []
        for idx in range(1, generations + 1):
            gid = f"gen-{idx}"
            run_comp = include_compositional_oaie and idx == 1
            summary = self.run_evolution_generation(gid, include_compositional_oaie=run_comp)
            gen_summaries.append(summary)
            exam = SubstrateSpore.import_and_verify_spore(
                spore_path=self.workspace / gid / "generation_spore.json",
                target_workspace=self.workspace / gid / "multi_continuity_probe",
                expected_ancestor_skills=["core_stage2_guard", summary["novel_skill_id"]],
                antibody_probes=[],
            )
            continuity_exams.append(exam)
        return {
            "schema": "ace.autonomous_evolver.multi_gen.v2",
            "generations_completed": len(gen_summaries),
            "all_continuity_exams_passed": all(e["exam_passed"] for e in continuity_exams),
            "total_forgetting_count": sum(e["forgetting_count"] for e in continuity_exams),
            "latest_spore_sha256": gen_summaries[-1]["spore_sha256"],
            "generations": gen_summaries,
        }
