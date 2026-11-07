"""ACE Autonomous Self-Development Coordinator V0.2.

Coordinates the 8-stage autonomous research lifecycle:
1. Observe (StateManager: loads persistent state, active lineage, past failures, acquires concurrency lock)
2. Diagnose (DiagnosticEngine: analyzes current active head across confirmation tasks)
3. Hypothesize (AgendaEngine & StrategyRepairEngine: selects target task, seed, and repaired representation family)
4. Generate (SourceGenerator: synthesizes typed AST candidate with cryptographic provenance proof)
4.5. Stagnation Guard (StagnationDetector: early detection of duplicate SHAs, semantic equivalence, patience exhaustion)
5. Evaluate (IsolatedEvaluator: sealed confirmation holdout evaluation, negative control; skipped if stagnated)
6. Decide (LineageGovernor: fail-closed gating; preserves baseline on rejection/stagnation)
7. Preserve (CheckpointManager & StateManager: durable checkpoint, compressed evidence, recovery backup)
8. Select Next Goal (AgendaEngine & StrategyRepairEngine: formulates next research agenda, rolls state digest, releases lock)
"""
from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from ace_host_controller import (
    ExecutionBudget,
    HostController,
    HostSandboxGate,
    SealedHoldoutEvaluator,
)
from .agenda_engine import AgendaEngine
from .checkpoint_manager import CheckpointManager
from .confirmation_suite import ConfirmationTask, create_confirmation_suite
from .diagnostic_engine import DiagnosticEngine
from .hypothesis_selector import HypothesisSelector
from .isolated_evaluator import IsolatedEvaluator
from .lineage_governor import LineageGovernor
from .models import (
    AuthorType,
    CandidateDecision,
    CodeCandidate,
    CycleCheckpoint,
    EvaluationReceipt,
    PersistentResearchState,
    ResearchHypothesis,
    SystemDiagnosis,
)
from .proposal_engine import ProposalEngine
from .provenance_engine import ProvenanceEngine
from .source_generator import SourceGenerator
from .stagnation_detector import (
    BitvectorRegistry,
    StagnationCheckResult,
    StagnationDetector,
    StagnationType,
)
from .state_manager import StateManager
from .strategy_repair import (
    RepresentationFamily,
    StrategyRepairDecision,
    StrategyRepairEngine,
)


class SelfDevelopmentCoordinator:
    """Orchestrates autonomous research continuity and multi-cycle execution."""

    def __init__(
        self,
        checkpoint_dir: str = "checkpoints/self_dev",
        evidence_dir: str = "evidence/self_dev",
        signing_key: Optional[str] = None,
    ):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.evidence_dir = Path(evidence_dir)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

        self.state_manager = StateManager(state_dir=checkpoint_dir)
        self.checkpointer = CheckpointManager(checkpoint_dir=checkpoint_dir)
        self.provenance_engine = ProvenanceEngine(signing_key=signing_key)
        self.diagnoser = DiagnosticEngine()
        self.hypothesizer = HypothesisSelector()
        self.agenda_engine = AgendaEngine()
        self.generator = SourceGenerator(provenance_engine=self.provenance_engine)
        self.evaluator = IsolatedEvaluator(provenance_engine=self.provenance_engine)
        self.governor = LineageGovernor()
        self.proposer = ProposalEngine()
        self.stagnation_detector = StagnationDetector(
            registry_path=str(self.checkpoint_dir / "bitvector_registry.json")
        )
        self.strategy_repair = StrategyRepairEngine()

    def search_and_select_candidate(
        self,
        hypothesis: ResearchHypothesis,
        parent_candidate: Optional[CodeCandidate],
        active_head_id: str,
        author_type: AuthorType,
        target_task: ConfirmationTask,
        search_budget: int = 1,
    ) -> CodeCandidate:
        """Search candidate hypotheses relying strictly on train and validation metrics.

        The sealed confirmation holdout is strictly gated and NEVER queried during this search.
        """
        base_ordinal = getattr(hypothesis, "mutation_ordinal", 1)
        if search_budget <= 1:
            return self.generator.generate_candidate(
                hypothesis=hypothesis,
                parent_candidate=parent_candidate,
                parent_id=active_head_id,
                ordinal=base_ordinal,
                author_type=author_type,
            )

        best_cand: Optional[CodeCandidate] = None
        best_val_score = -1.0

        for offset in range(search_budget):
            cand = self.generator.generate_candidate(
                hypothesis=hypothesis,
                parent_candidate=parent_candidate,
                parent_id=active_head_id,
                ordinal=base_ordinal + offset,
                author_type=author_type,
            )
            # Evaluate strictly on train and validation pools without holdout access
            train_acc, val_acc, _ = self.evaluator.score_train_and_validation(cand, target_task)
            if val_acc > best_val_score:
                best_val_score = val_acc
                best_cand = cand

        return best_cand or self.generator.generate_candidate(
            hypothesis=hypothesis,
            parent_candidate=parent_candidate,
            parent_id=active_head_id,
            ordinal=base_ordinal,
            author_type=author_type,
        )

    def run_autonomous_cycle(
        self,
        host_controller: Optional[HostController] = None,
        author_type: AuthorType = AuthorType.ACE_AUTONOMOUS_V02,
        candidate_search_budget: int = 1,
    ) -> Dict[str, Any]:
        """Execute one complete autonomous cycle driven entirely by persistent research state."""
        worker_id = f"worker_{os.getpid()}_{int(time.time())}"
        lock_token = self.state_manager.acquire_lock(worker_id)

        try:
            # 1. OBSERVE
            state = self.state_manager.load_state()
            cycle_id = state.cycle_count + 1
            prior_cycle_id = state.cycle_count if state.cycle_count > 0 else None
            state_digest_before = state.state_digest or "GENESIS"
            active_head_id = state.active_generation_id

            # Check existing checkpoint if restarting an interrupted cycle
            ckpt = self.checkpointer.load_checkpoint(cycle_id)
            if ckpt is None:
                ckpt = CycleCheckpoint(
                    cycle_id=cycle_id,
                    phase="OBSERVED",
                    active_head_id=active_head_id,
                    prior_cycle_id=prior_cycle_id,
                    state_digest_before=state_digest_before,
                )
                self.checkpointer.save_checkpoint(ckpt)

            # 2. DIAGNOSE
            # Derive tasks dynamically using seed from state entropy
            provisional_seed = self.agenda_engine.derive_task_seed(cycle_id, state_digest_before)
            provisional_tasks = create_confirmation_suite(task_seed=provisional_seed)

            # Default root classification: len(w) % 3 == 0
            default_root_fn = lambda w: (len(w) % 3 == 0)
            diagnosis = self.diagnoser.diagnose_weakness(
                baseline_fn=default_root_fn,
                baseline_head_id=active_head_id,
                tasks=provisional_tasks,
            )
            ckpt.phase = "DIAGNOSED"
            ckpt.diagnosis = {
                "timestamp": diagnosis.timestamp,
                "baseline_head_id": diagnosis.baseline_head_id,
                "baseline_score": diagnosis.baseline_score,
                "diagnosed_weakness_task": diagnosis.diagnosed_weakness_task,
                "diagnosed_weakness_family": diagnosis.diagnosed_weakness_family,
                "observed_failure_rate": diagnosis.observed_failure_rate,
                "error_cue": diagnosis.error_cue,
                "details": diagnosis.diagnostic_details,
            }
            self.checkpointer.save_checkpoint(ckpt)

            # 3. HYPOTHESIZE
            target_task_id, task_seed, mutation_ordinal = self.agenda_engine.select_cycle_strategy(
                state=state,
                diagnosis=diagnosis,
                tasks=provisional_tasks,
            )

            # Check for exhaustive search space closure
            if target_task_id == "SEARCH_SPACE_EXHAUSTED":
                return {
                    "cycle_id": cycle_id,
                    "status": "STAGNATED",
                    "phase": "TERMINAL_STAGNATION",
                    "active_head_id": active_head_id,
                    "is_promoted": False,
                    "decision": "STAGNATED",
                    "candidate_id": "NONE",
                    "author_type": author_type.value,
                    "target_task_id": "NONE",
                    "holdout_score": diagnosis.baseline_score,
                    "gain_over_parent": 0.0,
                    "evidence_path": "",
                    "prior_cycle_id": prior_cycle_id,
                    "state_digest_before": state_digest_before,
                    "state_digest_after": state_digest_before,
                    "should_commit": False,
                    "reason": "SEARCH_SPACE_EXHAUSTED: All representation families exhausted across confirmation tasks.",
                    "governance": {
                        "release_gate": "BLOCK_RELEASE",
                        "scientific_status": "NOT_ASSESSED",
                        "oaie_established": False,
                    },
                }

            tasks = create_confirmation_suite(task_seed=task_seed)
            target_task = tasks[target_task_id]

            hypothesis = self.agenda_engine.formulate_hypothesis(
                cycle_id=cycle_id,
                target_task_id=target_task_id,
                target_task=target_task,
                ordinal=mutation_ordinal,
                state=state,
            )
            ckpt.phase = "HYPOTHESIS_SELECTED"
            ckpt.hypothesis = {
                "hypothesis_id": hypothesis.hypothesis_id,
                "statement": hypothesis.statement,
                "target_task_id": hypothesis.target_task_id,
                "min_required_gain": hypothesis.min_required_gain,
                "max_regression_tolerance": hypothesis.max_regression_tolerance,
                "preregistration_hash": hypothesis.preregistration_hash,
                "task_seed": task_seed,
                "mutation_ordinal": mutation_ordinal,
                "strategy": hypothesis.strategy,
            }
            self.checkpointer.save_checkpoint(ckpt)

            # 4. GENERATE
            candidate = self.generator.generate_candidate(
                hypothesis=hypothesis,
                parent_candidate=None,
                parent_id=active_head_id,
                ordinal=mutation_ordinal,
                author_type=author_type,
            )
            ckpt.phase = "CANDIDATE_GENERATED"
            ckpt.candidate = {
                "candidate_id": candidate.candidate_id,
                "parent_id": candidate.parent_id,
                "author_type": candidate.author_type.value,
                "source_code": candidate.source_code,
                "source_sha": candidate.source_sha,
                "gene_dict": candidate.gene_dict,
                "diff_patch": candidate.diff_patch,
                "creation_timestamp": candidate.creation_timestamp,
                "provenance_proof": candidate.provenance_proof.to_dict() if candidate.provenance_proof else None,
            }
            self.checkpointer.save_checkpoint(ckpt)

            # 4.5. STAGNATION GUARD (Pre-Evaluation Gating)
            stagnation_check = self.stagnation_detector.inspect_pre_evaluation(
                candidate=candidate,
                hypothesis=hypothesis,
                state=state,
                task=target_task,
            )

            # 5. EVALUATE
            if stagnation_check.is_stagnated or not stagnation_check.should_evaluate:
                # Halt redundant evaluation! Zero queries to sealed holdout!
                receipt = EvaluationReceipt(
                    receipt_id=f"receipt_stag_{candidate.candidate_id}_c{cycle_id}",
                    evaluator_manifest_digest="SKIPPED_DUE_TO_STAGNATION",
                    candidate_id=candidate.candidate_id,
                    parent_id=active_head_id,
                    train_score=diagnosis.baseline_score,
                    validation_score=diagnosis.baseline_score,
                    holdout_score=diagnosis.baseline_score,
                    gain_over_parent=0.0,
                    prior_regression=0.0,
                    decision=CandidateDecision.STAGNATED,
                    decision_reason=f"STAGNATION_DETECTED: {stagnation_check.reason}",
                    evaluator_calls=0,
                    cpu_seconds=0.0,
                    memory_mb=0.0,
                    cost_usd=0.0,
                    receipt_signature=f"STAG_{stagnation_check.stagnation_type.value}",
                    key_fingerprint="NONE",
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    prior_cycle_id=prior_cycle_id,
                    state_digest_before=state_digest_before,
                    provenance_proof=candidate.provenance_proof.to_dict() if candidate.provenance_proof else {},
                )
            else:
                if host_controller is None:
                    holdout_banks = {tid: list(t.sealed_confirmation_holdout) for tid, t in tasks.items()}
                    sealed_eval = SealedHoldoutEvaluator(
                        manifest_id=f"manifest_self_dev_c{cycle_id}_ts{task_seed}",
                        holdout_banks=holdout_banks,
                    )
                    host_controller = HostController(
                        evaluator=sealed_eval,
                        budget=ExecutionBudget(max_execution_seconds=120.0, max_queries=500, max_candidates=20),
                        sandbox_gate=HostSandboxGate(enforce_os_containment=False),
                        root_candidate_id=active_head_id,
                        root_source_sha=f"root_sha_c{cycle_id}",
                        min_gain=0.1500,
                        max_regression=0.0200,
                    )
                    host_controller.initialize_root_score(default_root_fn)

                receipt = self.evaluator.evaluate_candidate(
                    candidate=candidate,
                    hypothesis=hypothesis,
                    tasks=tasks,
                    host_controller=host_controller,
                    prior_cycle_id=prior_cycle_id,
                    state_digest_before=state_digest_before,
                )

                # Register novel evaluated candidate in bitvector catalog
                self.stagnation_detector.register_evaluated_candidate(
                    task_id=target_task_id,
                    candidate_id=candidate.candidate_id,
                    source_sha=candidate.source_sha,
                    score=receipt.holdout_score,
                    bitvector_hash=stagnation_check.bitvector_hash or "",
                    cycle_id=cycle_id,
                    bitvector=stagnation_check.bitvector,
                )

            ckpt.phase = "EVALUATED"
            ckpt.evaluation = {
                "receipt_id": receipt.receipt_id,
                "evaluator_manifest_digest": receipt.evaluator_manifest_digest,
                "candidate_id": receipt.candidate_id,
                "parent_id": receipt.parent_id,
                "train_score": receipt.train_score,
                "validation_score": receipt.validation_score,
                "holdout_score": receipt.holdout_score,
                "gain_over_parent": receipt.gain_over_parent,
                "prior_regression": receipt.prior_regression,
                "decision": receipt.decision.value,
                "decision_reason": receipt.decision_reason,
                "evaluator_calls": receipt.evaluator_calls,
                "cpu_seconds": receipt.cpu_seconds,
                "memory_mb": receipt.memory_mb,
                "cost_usd": receipt.cost_usd,
                "receipt_signature": receipt.receipt_signature,
                "key_fingerprint": receipt.key_fingerprint,
                "timestamp": receipt.timestamp,
                "prior_cycle_id": receipt.prior_cycle_id,
                "state_digest_before": receipt.state_digest_before,
                "provenance_proof": receipt.provenance_proof,
                "stagnation_check": stagnation_check.to_dict(),
            }
            self.checkpointer.save_checkpoint(ckpt)

            # 6. DECIDE
            active_head, is_promoted = self.governor.apply_decision(
                receipt=receipt,
                host_controller=host_controller,
                fallback_head_id=active_head_id,
            )
            ckpt.phase = "DECIDED"
            ckpt.active_head_id = active_head
            ckpt.decision = receipt.decision.value
            self.checkpointer.save_checkpoint(ckpt)

            # 7. PRESERVE & SELECT NEXT GOAL
            proposal = self.proposer.build_proposal_payload(
                cycle_id=cycle_id,
                diagnosis=diagnosis,
                hypothesis=hypothesis,
                candidate=candidate,
                receipt=receipt,
                is_promoted=is_promoted,
            )

            # Autonomous formulation of next goal via StrategyRepairEngine
            next_goal = self.agenda_engine.formulate_next_goal(
                current_cycle_id=cycle_id,
                current_task_id=target_task_id,
                current_ordinal=mutation_ordinal,
                decision=receipt.decision.value,
                gain=receipt.gain_over_parent,
                tasks=tasks,
                state=state,
                current_strategy=hypothesis.strategy,
            )
            ckpt.next_goal = next_goal.to_dict()

            evidence_path = self.evidence_dir / f"ace_self_dev_v02_cycle_{cycle_id:04d}.json.gz"
            evidence_payload = {
                "benchmark_id": "ACE_AUTONOMOUS_CONTINUITY_V02",
                "cycle_id": cycle_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "prior_cycle_id": prior_cycle_id,
                "state_digest_before": state_digest_before,
                "diagnosis": ckpt.diagnosis,
                "hypothesis": ckpt.hypothesis,
                "candidate": ckpt.candidate,
                "evaluation_receipt": ckpt.evaluation,
                "stagnation_analysis": stagnation_check.to_dict(),
                "governance_result": {
                    "active_head_id": active_head,
                    "is_promoted": is_promoted,
                    "decision": receipt.decision.value,
                    "release_gate": "BLOCK_RELEASE",
                    "scientific_status": "NOT_ASSESSED",
                    "oaie_established": False,
                },
                "next_agenda_priority": next_goal.to_dict(),
                "proposal": proposal,
            }

            with gzip.open(evidence_path, "wb") as f:
                f.write(json.dumps(evidence_payload, indent=2).encode("utf-8"))

            # Update persistent research state and roll state digest
            updated_state = self.state_manager.record_completed_cycle(
                cycle_id=cycle_id,
                hypothesis_id=hypothesis.hypothesis_id,
                target_task_id=target_task_id,
                candidate_id=candidate.candidate_id,
                source_sha=candidate.source_sha,
                decision=receipt.decision.value,
                holdout_score=receipt.holdout_score,
                gain_over_parent=receipt.gain_over_parent,
                rejection_reason=receipt.decision_reason,
                evidence_path=str(evidence_path),
                receipt_signature=receipt.receipt_signature,
                gene_dict=candidate.gene_dict,
                mutation_ordinal=mutation_ordinal,
                active_head_id=active_head,
                next_agenda=next_goal.to_dict(),
            )

            ckpt.state_digest_after = updated_state.state_digest
            ckpt.phase = "REPORTED"
            self.checkpointer.save_checkpoint(ckpt)

            return {
                "cycle_id": cycle_id,
                "status": "COMPLETED",
                "phase": "REPORTED",
                "active_head_id": active_head,
                "is_promoted": is_promoted,
                "decision": receipt.decision.value,
                "candidate_id": candidate.candidate_id,
                "author_type": candidate.author_type.value,
                "target_task_id": target_task_id,
                "holdout_score": receipt.holdout_score,
                "gain_over_parent": receipt.gain_over_parent,
                "evidence_path": str(evidence_path),
                "prior_cycle_id": prior_cycle_id,
                "state_digest_before": state_digest_before,
                "state_digest_after": updated_state.state_digest,
                "is_stagnated": stagnation_check.is_stagnated,
                "stagnation_type": stagnation_check.stagnation_type.value,
                "should_commit": stagnation_check.should_commit,
                "next_agenda_priority": next_goal.to_dict(),
                "governance": {
                    "release_gate": "BLOCK_RELEASE",
                    "scientific_status": "NOT_ASSESSED",
                    "oaie_established": False,
                },
            }

        finally:
            self.state_manager.release_lock(lock_token)

    def run_continuous_cycles(
        self,
        max_cycles: int = 3,
        author_type: AuthorType = AuthorType.ACE_AUTONOMOUS_V02,
    ) -> List[Dict[str, Any]]:
        """Run up to max_cycles autonomously in succession, advancing state at each cycle."""
        results = []
        for step in range(max_cycles):
            print(f"\n[Coordinator] Executing Autonomous Continuity Cycle Step {step + 1}/{max_cycles}...")
            res = self.run_autonomous_cycle(author_type=author_type)
            results.append(res)
            print(f"  Completed Cycle {res['cycle_id']}: Decision={res['decision']}, Task={res['target_task_id']}")
            if res.get("status") == "STAGNATED":
                print(f"  [Coordinator] Halting continuous execution: {res.get('reason')}")
                break
            if res.get("next_agenda_priority"):
                print(f"  Next Agenda: {res['next_agenda_priority']['strategy']} on {res['next_agenda_priority']['priority_task_id']}")
        return results

    def run_cycle(
        self,
        cycle_id: int,
        task_seed: int = 42,
        mutation_ordinal: int = 1,
        author_type: AuthorType = AuthorType.ACE_AUTONOMOUS_V02,
        host_controller: Optional[HostController] = None,
        tasks: Optional[Dict[str, ConfirmationTask]] = None,
    ) -> Dict[str, Any]:
        """Backward-compatible manual cycle invocation."""
        return self.run_autonomous_cycle(
            host_controller=host_controller,
            author_type=author_type,
        )
