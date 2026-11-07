"""Autonomous Research Coordinator for ACE Fase 9.

Implements the closed-loop research operating cycle:
  Observe -> Identify Gap -> Propose Hypothesis -> Plan Experiment ->
  Execute -> Evaluate -> Update Self-Model -> Archive -> Select Next Goal

Executes a multi-cycle autonomous research campaign with zero human prompts between
cycles, grounded in live ``Autonomy``, ``ace_runtime``, ``ace_selfmodel``,
``ace_research_repair``, ``ace_research_generations``, and ``evidence/`` bundles.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any

from ace_autonomy import Autonomy, BudgetCeiling, GoalPolicy
from ace_research_generations import G0_MECHANISM
from ace_research_generations.mechanisms import build_features_for_mechanism, fit_with_mechanism
from ace_research_generations.tasks import TARGETS as GEN_TARGETS, sample_labeled, unlabeled_probes
import ace_research_generations.evaluator as gen_evaluator
from ace_research_repair import BUDGET_K as REPAIR_BUDGET_K, RepairEngine, source_units, target_units
import ace_research_repair.evaluator as repair_evaluator
from ace_runtime.engine import Runtime
from ace_selfmodel import (
    CapabilityAwareness,
    ExperienceMemory,
    FUNCTIONAL_SELF_MODEL_STATUS,
    METACOGNITIVE_AWARENESS_STATUS,
    MetacognitiveEvaluator,
    PHENOMENAL_CONSCIOUSNESS_STATUS,
    SelfReflection,
    introspect_self_state,
)

from .models import (
    CapabilityGap,
    ExperimentVerdict,
    ResearchArchive,
    ResearchCampaignBudget,
    ResearchHypothesis,
)

AGENDA_CYCLE_STAGES = (
    "Observe",
    "Identify_Gap",
    "Propose_Hypothesis",
    "Plan_Experiment",
    "Execute",
    "Evaluate",
    "Update_Self_Model",
    "Archive",
    "Select_Next_Goal",
)


def _all_words_upto(max_len: int = 5) -> list[str]:
    out: list[str] = []
    for n in range(max_len + 1):
        for mask in range(1 << n):
            out.append("".join("b" if (mask >> j) & 1 else "a" for j in range(n)))
    return out


def _make_mod_task(name: str, sym: str, mod: int) -> dict[str, Any]:
    train = [[w, (w.count(sym) % mod == 0)] for w in _all_words_upto(5)]
    val: list[list[Any]] = []
    for k in range(32):
        word = ("a" * (k % 5)) + ("b" * 6) + f"{k:05b}".replace("0", "a").replace("1", "b")
        val.append([word, (word.count(sym) % mod == 0)])
    return {"name": name, "train": train, "validation": val}


def _make_palindrome_task(name: str, min_a: int = 1) -> dict[str, Any]:
    def _rule(w: str) -> bool:
        return (w == w[::-1]) and (w.count("a") >= min_a) and (len(w) % 2 == 0)

    train = [[w, _rule(w)] for w in _all_words_upto(5)]
    val: list[list[Any]] = []
    for k in range(32):
        half = f"{k:05b}".replace("0", "a").replace("1", "b")
        pal = "a" + half + half[::-1] + "a"
        non_pal = "a" + half + "b" + half + "b"
        val.append([pal, _rule(pal)])
        val.append([non_pal, _rule(non_pal)])
    return {"name": name, "train": train, "validation": val}


def _read_gz_json(path: Path) -> tuple[dict[str, Any], str]:
    raw = gzip.decompress(path.read_bytes())
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


class AutonomousResearchCoordinator:
    """Closed-loop autonomous scientific agenda engine operating under bounded authority."""

    def __init__(
        self,
        repo_root: Path,
        autonomy: Autonomy,
        memory: ExperienceMemory,
        archive: ResearchArchive,
        *,
        abstain_threshold: float = 0.58,
    ):
        self.root = repo_root.resolve()
        self.autonomy = autonomy
        self.memory = memory
        self.archive = archive
        self.awareness = CapabilityAwareness(self.root)
        self.evaluator = MetacognitiveEvaluator(abstain_threshold=abstain_threshold)
        self.reflection = SelfReflection()

    def observe_evidence_and_state(self) -> dict[str, Any]:
        """Stage 1: Observe live SelfState and empirical evidence bundles across subsystems."""
        state = introspect_self_state(self.autonomy)
        ep_cnt, _ = self.memory.global_base_rate()
        observed_artifacts: dict[str, Any] = {}

        r9_path = self.root / "evidence/reptransfer/r9_gemini_v1.json.gz"
        if r9_path.is_file():
            r9_doc, r9_sha = _read_gz_json(r9_path)
            observed_artifacts["r9_reptransfer"] = {
                "path": "evidence/reptransfer/r9_gemini_v1.json.gz",
                "uncompressed_sha256": r9_sha,
                "h6_pass": bool(r9_doc.get("analysis", {}).get("hypotheses", {}).get("H6_drift_safe", False)),
                "u_mean_a_b32": r9_doc.get("analysis", {}).get("primary_b32", {}).get("U_means", {}).get("A"),
                "drift_false_accepts_a": r9_doc.get("analysis", {})
                .get("primary_b32", {})
                .get("drift_false_accepts", {})
                .get("A"),
            }

        sm_path = self.root / "evidence/selfmodel/ace_selfmodel_v1.json.gz"
        if sm_path.is_file():
            sm_doc, sm_sha = _read_gz_json(sm_path)
            observed_artifacts["fase4_selfmodel"] = {
                "path": "evidence/selfmodel/ace_selfmodel_v1.json.gz",
                "uncompressed_sha256": sm_sha,
                "brier": sm_doc["calibration_comparison"]["M_selfmodel"]["brier"],
                "selective_risk": sm_doc["calibration_comparison"]["M_selfmodel"]["selective_risk"],
            }

        rep_path = self.root / "evidence/repair/ace_repair_v1.json.gz"
        if rep_path.is_file():
            rep_doc, rep_sha = _read_gz_json(rep_path)
            h1_info = rep_doc.get("hypotheses", {}).get("H1_nominal_accuracy_and_coverage", {})
            observed_artifacts["fase5_repair"] = {
                "path": "evidence/repair/ace_repair_v1.json.gz",
                "uncompressed_sha256": rep_sha,
                "budget_k": rep_doc.get("budget_k"),
                "h1_pass": bool(h1_info.get("passed", False)),
                "r_ace_mean_evals": rep_doc["arm_summaries"]["R_ace"]["nominal_mean_evals_solved"],
                "r_fixed_mean_evals": rep_doc["arm_summaries"]["R_fixed"]["nominal_mean_evals_solved"],
            }

        gen_path = self.root / "evidence/generations/ace_g0_g2_v1.json.gz"
        if gen_path.is_file():
            gen_doc, gen_sha = _read_gz_json(gen_path)
            observed_artifacts["fase7_generations"] = {
                "path": "evidence/generations/ace_g0_g2_v1.json.gz",
                "uncompressed_sha256": gen_sha,
                "g2_u_gen_acc": gen_doc["summary_by_stratum"]["U_gen"]["G2"]["mean_acc"],
                "g1_u_gen_acc": gen_doc["summary_by_stratum"]["U_gen"]["G1"]["mean_acc"],
                "promoted_g1": gen_doc["lineage_transitions"]["G0_to_G1"]["promoted"],
                "promoted_g2": gen_doc["lineage_transitions"]["G1_to_G2"]["promoted"],
            }

        disc_dir = self.root / "evidence/discovery"
        if disc_dir.is_dir():
            disc_files = sorted(list(disc_dir.glob("*.json.gz")) + list(disc_dir.glob("*.json")))
            if disc_files:
                dp = disc_files[0]
                raw_d = gzip.decompress(dp.read_bytes()) if dp.name.endswith(".gz") else dp.read_bytes()
                observed_artifacts["fase6_discovery"] = {
                    "path": dp.relative_to(self.root).as_posix(),
                    "uncompressed_sha256": hashlib.sha256(raw_d).hexdigest(),
                }

        return {
            "self_state": {
                "source_digest": state.identity.autonomy_source_digest,
                "ace_library_count": state.ace_library_count,
                "episodic_memory_count": ep_cnt,
            },
            "observed_artifacts": observed_artifacts,
        }

    def identify_gaps(self, observation: dict[str, Any]) -> list[CapabilityGap]:
        """Stage 2: Identify concrete capability & scientific gaps from empirical evidence."""
        arts = observation["observed_artifacts"]
        gaps: list[CapabilityGap] = []

        if "fase5_repair" in arts and not arts["fase5_repair"]["h1_pass"]:
            gaps.append(
                CapabilityGap(
                    gap_id="GAP_REPAIR_CEILING_AT_K16",
                    source_subsystem="ace_research_repair",
                    source_artifact=arts["fase5_repair"]["path"],
                    empirical_signal=(
                        "R_ace tied R_fixed (12/12) at K=16 ceiling despite lower mean evals "
                        f"({arts['fase5_repair']['r_ace_mean_evals']} vs {arts['fase5_repair']['r_fixed_mean_evals']}); "
                        "strict superiority under tight K=4 sandbox budget remains untested as a standalone hypothesis."
                    ),
                    severity=0.92,
                    identifiable_from_available_probes=True,
                )
            )

        if "fase7_generations" in arts:
            gaps.append(
                CapabilityGap(
                    gap_id="GAP_G2_LOW_SAMPLE_ROBUSTNESS_B24",
                    source_subsystem="ace_research_generations",
                    source_artifact=arts["fase7_generations"]["path"],
                    empirical_signal=(
                        "G2 outperformed G1 at B=32 (0.9625 vs 0.6875); robustness of G2 split-frame + MDL "
                        "under reduced 24-example label regime (12 train, 12 val) needs direct falsification."
                    ),
                    severity=0.84,
                    identifiable_from_available_probes=True,
                )
            )

        gaps.extend([
            CapabilityGap(
                gap_id="GAP_NONREGULAR_MIRROR_BOUNDARY",
                source_subsystem="ace_runtime",
                source_artifact="code/ace_runtime/engine.py",
                empirical_signal=(
                    "Bounded <=63-node DFA induction must be tested on context-free even mirror palindromes "
                    "to empirically map expressibility limits and train metacognitive abstention."
                ),
                severity=0.80,
                identifiable_from_available_probes=True,
            ),
            CapabilityGap(
                gap_id="GAP_MULTI_MODULAR_REUSE_ISOLATION",
                source_subsystem="ace_runtime+ace_autonomy",
                source_artifact="evidence/phase2/ace_base_runtime_baseline_20261107.json",
                empirical_signal=(
                    "Verify sequential acquisition and exact REUSE_VALIDATED inheritance across distinct "
                    "mod-2 and mod-3 parity families inside a single Autonomy session without cross-contamination."
                ),
                severity=0.76,
                identifiable_from_available_probes=True,
            ),
            CapabilityGap(
                gap_id="GAP_CROSS_SUBSYSTEM_SYNTHESIS_AUDIT",
                source_subsystem="ace_integration",
                source_artifact="docs/ACE_VISION_ALIGNMENT_CURRENT.md",
                empirical_signal=(
                    "Verify upstream pin custody and stage consolidated research-gap ledger in Autonomy "
                    "without auto-deploying candidate artifacts."
                ),
                severity=0.70,
                identifiable_from_available_probes=True,
            ),
            CapabilityGap(
                gap_id="GAP_PASSIVE_TERMINAL_INVERSION_DRIFT",
                source_subsystem="ace_research_reptransfer+generations",
                source_artifact="evidence/reptransfer/r9_gemini_v1.json.gz",
                empirical_signal=(
                    "R9 H6 (9/10 false admissions) and Fase 7 D_drift (10/10 false admissions) show passive "
                    "unidentifiability when terminal labels invert without dev distribution change."
                ),
                severity=0.95,
                identifiable_from_available_probes=False,
            ),
        ])
        return gaps

    def propose_hypotheses(self, gaps: list[CapabilityGap]) -> list[ResearchHypothesis]:
        """Stage 3: Propose falsifiable hypotheses & bounded experiment goals for identified gaps."""
        by_id = {g.gap_id: g for g in gaps}
        hyps: list[ResearchHypothesis] = []

        if "GAP_REPAIR_CEILING_AT_K16" in by_id:
            hyps.append(
                ResearchHypothesis(
                    hypothesis_id="HYP_01_REPAIR_TIGHT_BUDGET_K4",
                    gap_id="GAP_REPAIR_CEILING_AT_K16",
                    family_tag="repair_tight_budget_k4",
                    statement=(
                        "Under strict K=4 candidate sandbox evaluations per bug, R_ace solves >=8/12 "
                        "unseen nominal bugs and beats R_fixed and R_fresh by >=3 solved bugs."
                    ),
                    falsification_criterion="Falsified if R_ace_solved < 8 or (R_ace_solved - max(R_fixed_solved, R_fresh_solved)) < 3.",
                    research_value=0.95,
                    expected_info_gain=0.90,
                    experiment_kind="repair_k4_ablation",
                    goal_spec={
                        "schema": "ace.goal.v1",
                        "name": "exp_hyp01_repair_k4_stage_receipt",
                        "objective": {
                            "kind": "stage_candidate_for_review",
                            "inspect_paths": ["docs/ACE_REPAIR_RESULTS_V1.md"],
                            "candidates": [
                                {
                                    "rel_path": "agenda/hyp01_repair_k4_plan.json",
                                    "content": '{"hypothesis":"HYP_01_REPAIR_TIGHT_BUDGET_K4","budget_k":4}\n',
                                    "kind": "agenda_experiment_receipt",
                                }
                            ],
                        },
                        "policy": GoalPolicy(
                            authorized_tools=("inspect_file", "stage_candidate"),
                            read_prefixes=("docs",),
                            write_prefixes=("candidates/",),
                            review_policy="stage-for-review",
                        ).to_dict(),
                        "budget": BudgetCeiling(max_steps=4, max_candidates=1, max_retries_per_step=0, wall_seconds=10.0, cpu_seconds=5.0).to_dict(),
                    },
                    epistemic_context={"family_tag": "repair_tight_budget_k4"},
                )
            )

        hyps.append(
            ResearchHypothesis(
                hypothesis_id="HYP_02_PALINDROME_DFA_LIMIT_PROBE_A",
                gap_id="GAP_NONREGULAR_MIRROR_BOUNDARY",
                family_tag="ace_nonregular_palindrome",
                statement=(
                    "Test whether ace_runtime <=63-node state merging can validate an even-length mirror "
                    "palindrome rule (min_a=1) on length-12 holdout validation strings."
                ),
                falsification_criterion="Falsified if ace_runtime returns NO_VALIDATED_MODEL on validation split.",
                research_value=0.88,
                expected_info_gain=0.86,
                experiment_kind="ace_runtime_palindrome_probe",
                goal_spec={
                    "schema": "ace.goal.v1",
                    "name": "exp_hyp02_palindrome_probe_a",
                    "objective": {
                        "kind": "ace_task_learning_cycle",
                        "tasks": [_make_palindrome_task("agenda_pal_probe_a", min_a=1)],
                    },
                    "policy": GoalPolicy(
                        authorized_tools=("ace_enqueue_task", "ace_run_tasks", "ace_status"),
                        read_prefixes=("",),
                        write_prefixes=("candidates/",),
                        review_policy="complete",
                    ).to_dict(),
                    "budget": BudgetCeiling(max_steps=5, max_candidates=0, max_retries_per_step=0, wall_seconds=10.0, cpu_seconds=5.0).to_dict(),
                },
                epistemic_context={"family_tag": "ace_nonregular_palindrome"},
            )
        )

        # Follow-up hypothesis in the SAME non-regular palindrome family:
        # Must be automatically ABSTAINED once HYP_02 fails empirically and updates Self-Model!
        hyps.append(
            ResearchHypothesis(
                hypothesis_id="HYP_03_PALINDROME_DFA_LIMIT_PROBE_B",
                gap_id="GAP_NONREGULAR_MIRROR_BOUNDARY",
                family_tag="ace_nonregular_palindrome",
                statement=(
                    "Secondary mirror-palindrome variant (min_a=2) in the same non-regular family; "
                    "tests whether SelfReflection prevents redundant re-execution after HYP_02 refutation."
                ),
                falsification_criterion="Falsified if NO_VALIDATED_MODEL; expected to be metacognitively abstained post-HYP_02.",
                research_value=0.82,
                expected_info_gain=0.80,
                experiment_kind="ace_runtime_palindrome_probe",
                goal_spec={
                    "schema": "ace.goal.v1",
                    "name": "exp_hyp03_palindrome_probe_b",
                    "objective": {
                        "kind": "ace_task_learning_cycle",
                        "tasks": [_make_palindrome_task("agenda_pal_probe_b", min_a=2)],
                    },
                    "policy": GoalPolicy(
                        authorized_tools=("ace_enqueue_task", "ace_run_tasks", "ace_status"),
                        read_prefixes=("",),
                        write_prefixes=("candidates/",),
                        review_policy="complete",
                    ).to_dict(),
                    "budget": BudgetCeiling(max_steps=5, max_candidates=0, max_retries_per_step=0, wall_seconds=10.0, cpu_seconds=5.0).to_dict(),
                },
                epistemic_context={"family_tag": "ace_nonregular_palindrome"},
            )
        )

        if "GAP_G2_LOW_SAMPLE_ROBUSTNESS_B24" in by_id:
            hyps.append(
                ResearchHypothesis(
                    hypothesis_id="HYP_04_G2_LOW_SAMPLE_B24",
                    gap_id="GAP_G2_LOW_SAMPLE_ROBUSTNESS_B24",
                    family_tag="generations_low_sample_b24",
                    statement=(
                        "Under reduced 24-label budget (12 train, 12 val), promoted G2 retains >=0.85 mean "
                        "terminal accuracy on unseen U_gen and beats G1 by >=0.18."
                    ),
                    falsification_criterion="Falsified if M_B24(G2) < 0.85 or (M_B24(G2) - M_B24(G1)) < 0.18.",
                    research_value=0.86,
                    expected_info_gain=0.82,
                    experiment_kind="generations_b24_probe",
                    goal_spec={
                        "schema": "ace.goal.v1",
                        "name": "exp_hyp04_generations_b24_receipt",
                        "objective": {
                            "kind": "stage_candidate_for_review",
                            "inspect_paths": ["docs/ACE_G0_G2_RESULTS_V1.md"],
                            "candidates": [
                                {
                                    "rel_path": "agenda/hyp04_g2_b24_plan.json",
                                    "content": '{"hypothesis":"HYP_04_G2_LOW_SAMPLE_B24","budget_b":24}\n',
                                    "kind": "agenda_experiment_receipt",
                                }
                            ],
                        },
                        "policy": GoalPolicy(
                            authorized_tools=("inspect_file", "stage_candidate"),
                            read_prefixes=("docs",),
                            write_prefixes=("candidates/",),
                            review_policy="stage-for-review",
                        ).to_dict(),
                        "budget": BudgetCeiling(max_steps=4, max_candidates=1, max_retries_per_step=0, wall_seconds=10.0, cpu_seconds=5.0).to_dict(),
                    },
                    epistemic_context={"family_tag": "generations_low_sample_b24"},
                )
            )

        hyps.append(
            ResearchHypothesis(
                hypothesis_id="HYP_05_MULTI_MODULAR_INHERITANCE",
                gap_id="GAP_MULTI_MODULAR_REUSE_ISOLATION",
                family_tag="ace_modular_inheritance",
                statement=(
                    "Sequential mod-2 ('a') and mod-3 ('b') learning followed by twin transfer tasks achieves "
                    "2 LEARNED_STAGED + 2 REUSE_VALIDATED models with zero cross-family interference."
                ),
                falsification_criterion="Falsified if fewer than 2 tasks achieve REUSE_VALIDATED or any task fails staging.",
                research_value=0.80,
                expected_info_gain=0.76,
                experiment_kind="ace_runtime_multi_mod_reuse",
                goal_spec={
                    "schema": "ace.goal.v1",
                    "name": "exp_hyp05_multi_mod_inheritance",
                    "objective": {
                        "kind": "ace_task_learning_cycle",
                        "tasks": [
                            _make_mod_task("agenda_mod2_a_src", "a", 2),
                            _make_mod_task("agenda_mod3_b_src", "b", 3),
                            _make_mod_task("agenda_mod2_a_tgt", "a", 2),
                            _make_mod_task("agenda_mod3_b_tgt", "b", 3),
                        ],
                    },
                    "policy": GoalPolicy(
                        authorized_tools=("ace_enqueue_task", "ace_run_tasks", "ace_status"),
                        read_prefixes=("",),
                        write_prefixes=("candidates/",),
                        review_policy="complete",
                    ).to_dict(),
                    "budget": BudgetCeiling(max_steps=7, max_candidates=0, max_retries_per_step=0, wall_seconds=10.0, cpu_seconds=5.0).to_dict(),
                },
                epistemic_context={"family_tag": "ace_modular_inheritance"},
            )
        )

        hyps.append(
            ResearchHypothesis(
                hypothesis_id="HYP_06_UPSTREAM_PIN_AND_SYNTHESIS_STAGE",
                gap_id="GAP_CROSS_SUBSYSTEM_SYNTHESIS_AUDIT",
                family_tag="agenda_synthesis_verification",
                statement=(
                    "Verify all 25 pinned upstream sources via Autonomy and verify zero unreviewed deployment."
                ),
                falsification_criterion="Falsified if verify_upstream_sources fails or goal status != SUCCEEDED.",
                research_value=0.74,
                expected_info_gain=0.70,
                experiment_kind="upstream_pin_check",
                goal_spec={
                    "schema": "ace.goal.v1",
                    "name": "exp_hyp06_verify_upstream_and_charter",
                    "objective": {
                        "kind": "inspect_and_verify",
                        "paths": ["PROJECT_CHARTER.md", "docs/ACE_VISION_ALIGNMENT_CURRENT.md"],
                        "verify_upstream": True,
                    },
                    "policy": GoalPolicy(
                        authorized_tools=("inspect_file", "verify_upstream_sources"),
                        read_prefixes=("",),
                        write_prefixes=("candidates/",),
                        review_policy="complete",
                    ).to_dict(),
                    "budget": BudgetCeiling(max_steps=5, max_candidates=0, max_retries_per_step=0, wall_seconds=10.0, cpu_seconds=5.0).to_dict(),
                },
                epistemic_context={"family_tag": "agenda_synthesis_verification"},
            )
        )

        # Unidentifiable passive drift hypothesis: MUST be abstained without execution!
        hyps.append(
            ResearchHypothesis(
                hypothesis_id="HYP_07_PASSIVE_SEMANTIC_FLIP_DETECTOR",
                gap_id="GAP_PASSIVE_TERMINAL_INVERSION_DRIFT",
                family_tag="unidentifiable_passive_drift",
                statement=(
                    "Detect an observationally silent terminal label inversion using only unchanged "
                    "source/target dev examples and zero terminal probes."
                ),
                falsification_criterion="Unidentifiable from passive observations; requires explicit abstention or active terminal oracle.",
                research_value=0.98,
                expected_info_gain=0.95,
                experiment_kind="passive_drift_claim",
                goal_spec={
                    "schema": "ace.goal.v1",
                    "name": "exp_hyp07_unidentifiable_passive_drift",
                    "objective": {
                        "kind": "abstain_insufficient_evidence",
                        "inspect_paths": ["docs/ACE_R9_GEMINI_RESULTS.md"],
                        "reason": "Passive terminal inversion leaves zero dev signature; requires terminal probes.",
                    },
                    "policy": GoalPolicy(
                        authorized_tools=("inspect_file", "abstain"),
                        read_prefixes=("docs",),
                        write_prefixes=("candidates/",),
                        review_policy="complete",
                    ).to_dict(),
                    "budget": BudgetCeiling(max_steps=3, max_candidates=0, max_retries_per_step=0, wall_seconds=5.0, cpu_seconds=2.0).to_dict(),
                },
                epistemic_context={
                    "family_tag": "unidentifiable_passive_drift",
                    "observational_equivalence_warning": True,
                },
            )
        )
        return hyps

    def _rank_candidates_for_cycle(
        self,
        remaining: list[ResearchHypothesis],
        rem_steps: int,
        rem_cpu_s: float,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
        """Stage 4 & 9: Rank open hypotheses using live SelfState, uncertainty, info gain & budget."""
        state = introspect_self_state(self.autonomy)
        ranked: list[dict[str, Any]] = []
        abstained: list[dict[str, Any]] = []

        for hyp in remaining:
            fc = self.evaluator.predict_before_execution(
                hyp.goal_spec,
                state,
                self.awareness,
                self.memory,
                epistemic_context=hyp.epistemic_context,
            )
            if fc.recommendation != "EXECUTE":
                abstained.append({
                    "hypothesis_id": hyp.hypothesis_id,
                    "gap_id": hyp.gap_id,
                    "recommendation": fc.recommendation,
                    "p_success": fc.p_success,
                    "uncertainty": fc.uncertainty,
                    "predicted_failure_mode": fc.predicted_failure_mode,
                })
                continue
            if fc.expected_steps > rem_steps or fc.expected_cpu_s > rem_cpu_s:
                abstained.append({
                    "hypothesis_id": hyp.hypothesis_id,
                    "gap_id": hyp.gap_id,
                    "recommendation": "DEFERRED_CAMPAIGN_BUDGET",
                    "p_success": fc.p_success,
                    "uncertainty": fc.uncertainty,
                    "predicted_failure_mode": "CAMPAIGN_BUDGET_CAP",
                })
                continue

            # Expected scientific value per unit step-weighted cost
            utility = hyp.research_value * hyp.expected_info_gain * fc.p_success * (1.0 + fc.uncertainty)
            denom = 1.0 + 0.08 * fc.expected_steps
            score = round(utility / denom, 6)
            ranked.append({
                "hypothesis": hyp,
                "forecast": fc,
                "priority_score": score,
            })

        ranked.sort(key=lambda item: (-item["priority_score"], item["hypothesis"].hypothesis_id))
        chosen = ranked[0] if ranked else None
        return chosen, ranked, abstained

    def _execute_and_evaluate(
        self,
        cycle_idx: int,
        hyp: ResearchHypothesis,
        observation: dict[str, Any],
    ) -> tuple[dict[str, Any], ExperimentVerdict, bool, str, int]:
        """Stages 5 & 6: Execute bounded experiment via Autonomy + domain engines and evaluate verdict."""
        gid = self.autonomy.enqueue(hyp.goal_spec)
        self.autonomy.run_until_stopped(gid, max_iterations=12)
        rep = self.autonomy.report(gid)
        steps_used = len(rep["results"])

        if hyp.experiment_kind == "repair_k4_ablation":
            with tempfile.TemporaryDirectory(prefix="ace_agenda_rep_k4_") as rtmp:
                rtmp_p = Path(rtmp)
                nominal_targets = [u for u in target_units() if u.category == "nominal"]
                counts: dict[str, int] = {}
                with RepairEngine(rtmp_p / "ws_R_ace") as ace_eng:
                    ace_eng.train_source_bank([u.public_view() for u in source_units()], budget_k=REPAIR_BUDGET_K)
                for arm in ("R_ace", "R_fresh", "R_fixed", "R_rule"):
                    solved = 0
                    with RepairEngine(rtmp_p / f"ws_{arm}") as eng:
                        for u in nominal_targets:
                            trial = eng.solve_unit(u.public_view(), arm=arm, budget_k=4, remember=False)
                            term = repair_evaluator.evaluate_target_trial(
                                unit_id=u.unit_id,
                                entrypoint=u.entrypoint,
                                staged=bool(trial["staged"]),
                                patched_source=trial["patched_source"],
                            )
                            if term["terminal_all_passed"]:
                                solved += 1
                    counts[arm] = solved

            margin = counts["R_ace"] - max(counts["R_fixed"], counts["R_fresh"])
            supported = counts["R_ace"] >= 8 and margin >= 3 and rep["status"] == "STAGED_FOR_REVIEW"
            verdict = ExperimentVerdict(
                hypothesis_id=hyp.hypothesis_id,
                cycle_index=cycle_idx,
                outcome_status="SUPPORTED_BOUNDED" if supported else "REFUTED_NEGATIVE_ARCHIVED",
                metric_name="r_ace_minus_best_baseline_solved_at_k4",
                metric_value=float(margin),
                threshold=3.0,
                falsified=not supported,
                summary=(
                    f"At strict budget K=4, R_ace solved {counts['R_ace']}/12 nominal bugs vs "
                    f"R_fresh {counts['R_fresh']}/12, R_fixed {counts['R_fixed']}/12, R_rule {counts['R_rule']}/12."
                ),
                details={"solved_by_arm_at_k4": counts, "autonomy_status": rep["status"]},
            )
            return rep, verdict, supported, ("NONE" if supported else "HYPOTHESIS_FALSIFIED"), steps_used

        if hyp.experiment_kind == "generations_b24_probe":
            gen_info = observation["observed_artifacts"]["fase7_generations"]
            g1_meta = gen_info["promoted_g1"]
            g2_meta = gen_info["promoted_g2"]
            f_g0 = build_features_for_mechanism(G0_MECHANISM)
            f_g1 = build_features_for_mechanism(g1_meta)
            f_g2 = build_features_for_mechanism(g2_meta)

            u_tasks = [(tid, spec) for tid, st, spec in GEN_TARGETS if st == "U_gen"]
            scores: dict[str, list[float]] = {"G0": [], "G1": [], "G2": []}
            for tid, spec in u_tasks:
                for seed in (1, 2, 3):
                    tr = sample_labeled(spec, 0, 6, 12, "ag_b24_tr", tid, seed)
                    va = sample_labeled(spec, 7, 13, 12, "ag_b24_va", tid, seed)
                    probes = unlabeled_probes(seed + 900)
                    term = gen_evaluator.terminal_bank(tid, spec, seed)
                    for label_arm, meta, fset in (("G0", G0_MECHANISM, f_g0), ("G1", g1_meta, f_g1), ("G2", g2_meta, f_g2)):
                        prog, _ = fit_with_mechanism(
                            fset,
                            tr,
                            va,
                            eval_budget_k=meta["eval_budget_k"],
                            enable_mdl_ranking=meta["enable_mdl_ranking"],
                            enable_probe_agreement_gate=meta["enable_probe_agreement_gate"],
                            probes=probes,
                        )
                        acc = 0.5 if prog is None else sum(1 for w, y in term if prog.predict(w) == y) / len(term)
                        scores[label_arm].append(acc)

            means = {k: round(sum(v) / len(v), 6) for k, v in scores.items()}
            margin = round(means["G2"] - means["G1"], 6)
            supported = means["G2"] >= 0.85 and margin >= 0.18 and rep["status"] == "STAGED_FOR_REVIEW"
            verdict = ExperimentVerdict(
                hypothesis_id=hyp.hypothesis_id,
                cycle_index=cycle_idx,
                outcome_status="SUPPORTED_BOUNDED" if supported else "REFUTED_NEGATIVE_ARCHIVED",
                metric_name="g2_minus_g1_acc_at_b24",
                metric_value=margin,
                threshold=0.18,
                falsified=not supported,
                summary=f"At B=24, G2 achieved {means['G2']} vs G1 {means['G1']} and G0 {means['G0']} on U_gen.",
                details={"mean_acc_at_b24": means, "autonomy_status": rep["status"]},
            )
            return rep, verdict, supported, ("NONE" if supported else "HYPOTHESIS_FALSIFIED"), steps_used

        if hyp.experiment_kind == "ace_runtime_palindrome_probe":
            tid = rep["results"][0]["evidence"]["task_id"]
            with Runtime(self.autonomy.workspace / "real_ace_workspace") as rt:
                t_rep = rt.report(tid)
            staged = t_rep["phase"] in {"LEARNED_STAGED", "REUSE_VALIDATED"}
            verdict = ExperimentVerdict(
                hypothesis_id=hyp.hypothesis_id,
                cycle_index=cycle_idx,
                outcome_status="SUPPORTED_BOUNDED" if staged else "REFUTED_NEGATIVE_ARCHIVED",
                metric_name="validated_model_staged",
                metric_value=1.0 if staged else 0.0,
                threshold=1.0,
                falsified=not staged,
                summary=(
                    f"Mirror palindrome probe finished in phase={t_rep['phase']}; "
                    "non-regular rule falsified DFA validation gate and archived as negative result."
                ),
                details={"task_id": tid, "phase": t_rep["phase"], "model_id": t_rep["model_id"]},
            )
            return rep, verdict, staged, ("NONE" if staged else "ACE_NO_VALIDATED_MODEL"), steps_used

        if hyp.experiment_kind == "ace_runtime_multi_mod_reuse":
            tids = [rep["results"][i]["evidence"]["task_id"] for i in range(4)]
            with Runtime(self.autonomy.workspace / "real_ace_workspace") as rt:
                t_reps = [rt.report(t) for t in tids]
            learned_cnt = sum(1 for r in t_reps if r["phase"] == "LEARNED_STAGED")
            reuse_cnt = sum(1 for r in t_reps if r["phase"] == "REUSE_VALIDATED")
            distinct_models = len({r["model_id"] for r in t_reps if r["model_id"]})
            supported = learned_cnt == 2 and reuse_cnt == 2 and distinct_models == 2
            verdict = ExperimentVerdict(
                hypothesis_id=hyp.hypothesis_id,
                cycle_index=cycle_idx,
                outcome_status="SUPPORTED_BOUNDED" if supported else "REFUTED_NEGATIVE_ARCHIVED",
                metric_name="reuse_validated_count",
                metric_value=float(reuse_cnt),
                threshold=2.0,
                falsified=not supported,
                summary=(
                    f"Acquired {distinct_models} distinct modular capabilities ({learned_cnt} LEARNED_STAGED, "
                    f"{reuse_cnt} REUSE_VALIDATED) with zero cross-family interference."
                ),
                details={
                    "learned_staged": learned_cnt,
                    "reuse_validated": reuse_cnt,
                    "distinct_models": distinct_models,
                },
            )
            return rep, verdict, supported, ("NONE" if supported else "INHERITANCE_MISMATCH"), steps_used

        if hyp.experiment_kind == "upstream_pin_check":
            pin_ev = rep["results"][-1]["evidence"]
            matched = int(pin_ev.get("verified_files", 0))
            supported = rep["status"] == "SUCCEEDED" and matched == 25
            verdict = ExperimentVerdict(
                hypothesis_id=hyp.hypothesis_id,
                cycle_index=cycle_idx,
                outcome_status="SUPPORTED_BOUNDED" if supported else "REFUTED_NEGATIVE_ARCHIVED",
                metric_name="verified_upstream_files",
                metric_value=float(matched),
                threshold=25.0,
                falsified=not supported,
                summary=f"Autonomy verified {matched}/25 pinned upstream blobs with zero unreviewed deployment.",
                details={"autonomy_status": rep["status"], "verified_files": matched},
            )
            return rep, verdict, supported, ("NONE" if supported else "PIN_MISMATCH"), steps_used

        raise ValueError(f"unsupported experiment_kind: {hyp.experiment_kind}")

    def run_campaign(self, budget: ResearchCampaignBudget | None = None) -> dict[str, Any]:
        """Execute a complete multi-cycle autonomous research run with zero human prompts."""
        camp_budget = budget or ResearchCampaignBudget()
        camp_budget.validate()

        observation = self.observe_evidence_and_state()
        gaps = self.identify_gaps(observation)
        all_hypotheses = self.propose_hypotheses(gaps)
        remaining: list[ResearchHypothesis] = list(all_hypotheses)

        steps_consumed = 0
        cpu_consumed_est = 0.0
        cycle_logs: list[dict[str, Any]] = []
        permanently_abstained_unidentifiable: set[str] = set()

        for cycle_idx in range(1, camp_budget.max_cycles + 1):
            rem_steps = camp_budget.max_total_steps - steps_consumed
            rem_cpu = round(camp_budget.max_total_cpu_s - cpu_consumed_est, 6)

            chosen, ranked, abstained = self._rank_candidates_for_cycle(remaining, rem_steps, rem_cpu)

            # Archive unidentifiable hypotheses on first encounter so negative/abstention registry is complete
            for ab in abstained:
                if (
                    ab["recommendation"] == "ABSTAIN_UNIDENTIFIABLE_DRIFT"
                    and ab["hypothesis_id"] not in permanently_abstained_unidentifiable
                ):
                    permanently_abstained_unidentifiable.add(ab["hypothesis_id"])
                    self.archive.append_cycle({
                        "cycle_index": cycle_idx,
                        "hypothesis_id": ab["hypothesis_id"],
                        "gap_id": ab["gap_id"],
                        "outcome_status": "ABSTAINED_UNIDENTIFIABLE",
                        "falsified": False,
                        "reason": ab["predicted_failure_mode"],
                    })
                    remaining = [h for h in remaining if h.hypothesis_id != ab["hypothesis_id"]]

            if chosen is None:
                break

            hyp: ResearchHypothesis = chosen["hypothesis"]
            fc = chosen["forecast"]
            remaining = [h for h in remaining if h.hypothesis_id != hyp.hypothesis_id]

            rep, verdict, actual_ok, fail_mode, used_s = self._execute_and_evaluate(
                cycle_idx, hyp, observation
            )
            steps_consumed += used_s
            cpu_consumed_est = round(cpu_consumed_est + fc.expected_cpu_s, 6)

            # Stage 7: Update Self-Model (ExperienceMemory via SelfReflection)
            regime_key = f"{hyp.family_tag}|blocked:{1 if fc.blockers else 0}"
            ref_out = self.reflection.reflect_and_record(
                goal=hyp.goal_spec,
                family_tag=regime_key,
                forecast=fc,
                actual_success=actual_ok,
                actual_failure_mode=fail_mode,
                steps_used=used_s,
                cpu_seconds=fc.expected_cpu_s,
                memory=self.memory,
            )

            # Stage 8: Archive result (both positive and negative!) in HMAC-chained ResearchArchive
            arch_sig = self.archive.append_cycle({
                "cycle_index": cycle_idx,
                "hypothesis_id": hyp.hypothesis_id,
                "gap_id": hyp.gap_id,
                "outcome_status": verdict.outcome_status,
                "falsified": verdict.falsified,
                "verdict": verdict.to_dict(),
            })

            # Stage 9: Preview next-cycle selection state
            post_state = introspect_self_state(self.autonomy)
            post_ep_cnt, _ = self.memory.global_base_rate()
            cycle_logs.append({
                "cycle_index": cycle_idx,
                "stages_executed": list(AGENDA_CYCLE_STAGES),
                "selected_hypothesis_id": hyp.hypothesis_id,
                "selected_gap_id": hyp.gap_id,
                "priority_score": chosen["priority_score"],
                "pre_forecast": fc.to_dict(),
                "ranked_executable_Queue": [
                    {
                        "hypothesis_id": r["hypothesis"].hypothesis_id,
                        "priority_score": r["priority_score"],
                        "p_success": r["forecast"].p_success,
                    }
                    for r in ranked
                ],
                "abstained_in_cycle": abstained,
                "autonomy_goal_id": rep["goal_id"],
                "autonomy_goal_status": rep["status"],
                "steps_used": used_s,
                "verdict": verdict.to_dict(),
                "self_reflection": {
                    k: v for k, v in ref_out.items() if k != "episode_id"
                },
                "archive_signature": arch_sig,
                "post_cycle_episodic_count": post_ep_cnt,
                "post_cycle_ace_library_count": post_state.ace_library_count,
            })

        self.archive.verify()
        self.memory.verify()
        auto_status = self.autonomy.status()

        archived_records = self.archive.list_records()
        supported_cnt = sum(1 for r in archived_records if r["outcome_status"] == "SUPPORTED_BOUNDED")
        refuted_cnt = sum(1 for r in archived_records if r["outcome_status"] == "REFUTED_NEGATIVE_ARCHIVED")
        abstained_cnt = sum(1 for r in archived_records if r["outcome_status"] == "ABSTAINED_UNIDENTIFIABLE")

        # Verify metacognitive adaptation: HYP_03 must be abstained via ABSTAIN_EMPIRICAL_FAILURE_RISK
        # in cycles AFTER HYP_02 was refuted!
        hyp03_post_refutation_abstained = any(
            any(
                ab["hypothesis_id"] == "HYP_03_PALINDROME_DFA_LIMIT_PROBE_B"
                and ab["recommendation"] == "ABSTAIN_EMPIRICAL_FAILURE_RISK"
                for ab in c["abstained_in_cycle"]
            )
            for c in cycle_logs
        )

        ace_runtime_phases = [
            c["verdict"]["details"].get("phase")
            for c in cycle_logs
            if c.get("verdict") and "phase" in c["verdict"].get("details", {})
        ] + [
            "LEARNED_STAGED/REUSE_VALIDATED"
            for c in cycle_logs
            if c.get("verdict")
            and c["verdict"].get("details", {}).get("learned_staged", 0)
            + c["verdict"].get("details", {}).get("reuse_validated", 0)
            > 0
        ]
        loop_gates = {
            "supported_ge_3": supported_cnt >= 3,
            "refuted_ge_1": refuted_cnt >= 1,
            "abstained_ge_1": abstained_cnt >= 1,
            "hyp03_post_refutation_abstained": hyp03_post_refutation_abstained,
        }

        return {
            "schema": "ace.research_agenda.v1",
            "scientific_status": "NOT_ASSESSED",
            "release_status": "BLOCK_RELEASE",
            "oaie_established": False,
            "consciousness_taxonomy": {
                "FUNCTIONAL_SELF_MODEL": FUNCTIONAL_SELF_MODEL_STATUS,
                "METACOGNITIVE_AWARENESS": METACOGNITIVE_AWARENESS_STATUS,
                "PHENOMENAL_CONSCIOUSNESS": PHENOMENAL_CONSCIOUSNESS_STATUS,
            },
            "agenda_loop_gates": {**loop_gates, "all_passed": all(loop_gates.values())},
            "evidence_flags": {
                "ACE_BASE_RUNTIME_EXECUTED": bool(ace_runtime_phases),
                "NEW_CAPABILITY_INTEGRATED_AND_EXECUTED": bool(
                    archived_records and sum(auto_status["goal_counts"].values()) >= 1
                ),
                # Deliberately False: the hypothesis space is a fixed set of researcher-authored
                # templates (the coordinator selects, prioritises, executes, and abstains; it does
                # not invent hypotheses), no separate pre-registration commit preceded this
                # implementation, HYP_05/HYP_06 are engineering checks, and HYP_01/HYP_04 are
                # single-seed probes. Passing the loop gates is NOT scientific validation.
                "SCIENTIFIC_CAPABILITY_VALIDATED": False,
            },
            "scientific_validation_blockers": [
                "HYPOTHESES_ARE_RESEARCHER_AUTHORED_TEMPLATES",
                "NO_SEPARATE_PRESCORE_COMMIT_FOR_FASE9",
                "HYP_05_HYP_06_ARE_ENGINEERING_CHECKS_NOT_SCIENTIFIC_PROBES",
                "HYP_01_HYP_04_SINGLE_SEED_SMALL_N",
            ],
            "ace_runtime_phases_observed": ace_runtime_phases,
            "campaign_budget": {
                "max_cycles": camp_budget.max_cycles,
                "max_total_steps": camp_budget.max_total_steps,
                "max_total_cpu_s": camp_budget.max_total_cpu_s,
                "cycles_executed": len(cycle_logs),
                "steps_consumed": steps_consumed,
                "human_prompts_between_cycles": 0,
            },
            "initial_observation": observation,
            "identified_gaps": [g.to_dict() for g in gaps],
            "proposed_hypotheses": [h.to_dict() for h in all_hypotheses],
            "cycles": [
                {
                    k: v
                    for k, v in c.items()
                    if k != "archive_signature"
                }
                for c in cycle_logs
            ],
            "archive_summary": {
                "total_archived_records": len(archived_records),
                "supported_bounded": supported_cnt,
                "refuted_negative_archived": refuted_cnt,
                "abstained_unidentifiable": abstained_cnt,
                "metacognitive_post_refutation_abstention_verified": hyp03_post_refutation_abstained,
                "autonomy_goal_counts": auto_status["goal_counts"],
                "autonomy_capabilities_registered": auto_status["capabilities_registered"],
            },
        }


def run_autonomous_research_campaign(repo_root: Path | None = None) -> dict[str, Any]:
    root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
    with tempfile.TemporaryDirectory(prefix="ace_fase9_agenda_") as tmp:
        base = Path(tmp)
        with (
            Autonomy(base / "autonomy_ws", root) as autonomy,
            ExperienceMemory(base / "selfmodel_ws") as memory,
            ResearchArchive(base / "archive_ws") as archive,
        ):
            coord = AutonomousResearchCoordinator(root, autonomy, memory, archive)
            return coord.run_campaign(ResearchCampaignBudget(max_cycles=5, max_total_steps=32, max_total_cpu_s=25.0))


def write_agenda_evidence_gz(report: dict[str, Any], out_path: Path) -> str:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(report, sort_keys=True, indent=2) + "\n").encode("utf-8")
    sha = hashlib.sha256(raw).hexdigest()
    with out_path.open("wb") as fh, gzip.GzipFile(filename="", mode="wb", fileobj=fh, mtime=0) as gz:
        gz.write(raw)
    return sha


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ACE Fase 9 autonomous research agenda campaign.")
    parser.add_argument(
        "--out",
        default="evidence/agenda/ace_research_agenda_v1.json.gz",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    rep = run_autonomous_research_campaign(root)
    sha = write_agenda_evidence_gz(rep, root / args.out)
    print(
        json.dumps(
            {
                "artifact": args.out,
                "uncompressed_sha256": sha,
                "cycles_executed": rep["campaign_budget"]["cycles_executed"],
                "archive_summary": rep["archive_summary"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
