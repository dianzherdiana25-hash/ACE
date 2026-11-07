"""ACE Autonomous Self-Development Coordinator V0.1.

Coordinates the end-to-end self-development loop:
1. Examines system capabilities & structural weaknesses (DiagnosticEngine)
2. Selects a falsifiable research hypothesis (HypothesisSelector)
3. Generates typed, AST-validated code modifications (SourceGenerator)
4. Executes isolated independent evaluation on sealed confirmation suite (IsolatedEvaluator)
5. Enforces fail-closed lineage governance: rejects failing candidates, retains baseline (LineageGovernor)
6. Persists durable checkpoints and evidence artifacts (CheckpointManager)
7. Generates change proposals and draft PR payload (ProposalEngine)
8. Seeds next research cycle based on empirical outcomes.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from ace_host_controller import (
    ExecutionBudget,
    HostController,
    HostSandboxGate,
    SealedHoldoutEvaluator,
)
from .checkpoint_manager import CheckpointManager
from .confirmation_suite import ConfirmationTask, create_confirmation_suite
from .diagnostic_engine import DiagnosticEngine
from .hypothesis_selector import HypothesisSelector
from .source_generator import SourceGenerator
from .isolated_evaluator import IsolatedEvaluator
from .lineage_governor import LineageGovernor
from .models import (
    AuthorType,
    CandidateDecision,
    CodeCandidate,
    CycleCheckpoint,
    EvaluationReceipt,
    ResearchHypothesis,
    SystemDiagnosis,
)
from .proposal_engine import ProposalEngine


class SelfDevelopmentCoordinator:
    """Orchestrates the 8-step autonomous self-development lifecycle."""

    def __init__(
        self,
        checkpoint_dir: str = "checkpoints/self_dev",
        evidence_dir: str = "evidence/self_dev",
        signing_key: str = "ace_self_dev_v01_secret",
    ):
        self.checkpointer = CheckpointManager(checkpoint_dir=checkpoint_dir)
        self.evidence_dir = Path(evidence_dir)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.diagnoser = DiagnosticEngine()
        self.hypothesizer = HypothesisSelector()
        self.generator = SourceGenerator()
        self.evaluator = IsolatedEvaluator(signing_key=signing_key)
        self.governor = LineageGovernor()
        self.proposer = ProposalEngine()

    def run_cycle(
        self,
        cycle_id: int,
        task_seed: int = 42,
        mutation_ordinal: int = 1,
        author_type: AuthorType = AuthorType.ACE_AUTONOMOUS_V01,
        host_controller: Optional[HostController] = None,
        tasks: Optional[Dict[str, ConfirmationTask]] = None,
    ) -> Dict[str, Any]:
        """Execute a full autonomous cycle with state persistence and fail-closed gating."""
        tasks = tasks or create_confirmation_suite(task_seed=task_seed)

        # 1. Initialize Host Controller if not supplied
        if host_controller is None:
            holdout_banks = {tid: list(t.sealed_confirmation_holdout) for tid, t in tasks.items()}
            sealed_eval = SealedHoldoutEvaluator(
                manifest_id=f"manifest_self_dev_c{cycle_id}_ts{task_seed}",
                holdout_banks=holdout_banks,
            )
            root_id = f"G0_self_dev_root_c{cycle_id}"
            host_controller = HostController(
                evaluator=sealed_eval,
                budget=ExecutionBudget(max_execution_seconds=120.0, max_queries=500, max_candidates=20),
                sandbox_gate=HostSandboxGate(enforce_os_containment=False),
                root_candidate_id=root_id,
                root_source_sha=f"root_sha_c{cycle_id}",
                min_gain=0.1500,
                max_regression=0.0200,
            )
            # Default root classification: len(w) % 3 == 0
            default_root_fn = lambda w: (len(w) % 3 == 0)
            host_controller.initialize_root_score(default_root_fn)

        # Check for existing checkpoint to support resumption
        ckpt = self.checkpointer.load_checkpoint(cycle_id)
        if ckpt is None:
            ckpt = CycleCheckpoint(
                cycle_id=cycle_id,
                phase="INITIALIZED",
                active_head_id=host_controller.lineage.active_head_id,
            )
            self.checkpointer.save_checkpoint(ckpt)

        # Step 1: Diagnose system weaknesses
        baseline_fn = getattr(host_controller, "root_candidate_fn", lambda w: (len(w) % 3 == 0))
        diagnosis = self.diagnoser.diagnose_weakness(
            baseline_fn=baseline_fn,
            baseline_head_id=host_controller.lineage.active_head_id,
            tasks=tasks,
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

        # Step 2: Select falsifiable hypothesis
        hypothesis = self.hypothesizer.select_hypothesis(
            diagnosis=diagnosis,
            cycle_id=cycle_id,
        )
        ckpt.phase = "HYPOTHESIS_SELECTED"
        ckpt.hypothesis = {
            "hypothesis_id": hypothesis.hypothesis_id,
            "statement": hypothesis.statement,
            "target_task_id": hypothesis.target_task_id,
            "min_required_gain": hypothesis.min_required_gain,
            "max_regression_tolerance": hypothesis.max_regression_tolerance,
            "preregistration_hash": hypothesis.preregistration_hash,
        }
        self.checkpointer.save_checkpoint(ckpt)

        # Step 3: Generate typed, validated candidate code
        candidate = self.generator.generate_candidate(
            hypothesis=hypothesis,
            parent_candidate=None,
            parent_id=host_controller.lineage.active_head_id,
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
        }
        self.checkpointer.save_checkpoint(ckpt)

        # Step 4: Execute isolated evaluation against sealed holdouts
        receipt = self.evaluator.evaluate_candidate(
            candidate=candidate,
            hypothesis=hypothesis,
            tasks=tasks,
            host_controller=host_controller,
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
            "timestamp": receipt.timestamp,
        }
        self.checkpointer.save_checkpoint(ckpt)

        # Step 5: Enforce lineage governance
        active_head, is_promoted = self.governor.apply_decision(
            receipt=receipt,
            host_controller=host_controller,
        )
        ckpt.phase = "DECIDED"
        ckpt.active_head_id = active_head
        ckpt.decision = receipt.decision.value
        self.checkpointer.save_checkpoint(ckpt)

        # Step 6: Build proposal and archive evidence
        proposal = self.proposer.build_proposal_payload(
            cycle_id=cycle_id,
            diagnosis=diagnosis,
            hypothesis=hypothesis,
            candidate=candidate,
            receipt=receipt,
            is_promoted=is_promoted,
        )

        evidence_payload = {
            "benchmark_id": "ACE_AUTONOMOUS_SELF_DEV_LOOP_V01",
            "cycle_id": cycle_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "diagnosis": ckpt.diagnosis,
            "hypothesis": ckpt.hypothesis,
            "candidate": ckpt.candidate,
            "evaluation_receipt": ckpt.evaluation,
            "governance_result": {
                "active_head_id": active_head,
                "is_promoted": is_promoted,
                "decision": receipt.decision.value,
                "release_gate": "BLOCK_RELEASE",
                "scientific_status": "NOT_ASSESSED",
                "oaie_established": False,
            },
            "proposal": proposal,
        }

        # Step 7: Persist compressed evidence artifact
        evidence_path = self.evidence_dir / f"ace_self_dev_v01_cycle_{cycle_id:04d}.json.gz"
        with gzip.open(evidence_path, "wb") as f:
            f.write(json.dumps(evidence_payload, indent=2).encode("utf-8"))

        ckpt.phase = "REPORTED"
        self.checkpointer.save_checkpoint(ckpt)

        # Step 8: Return comprehensive cycle result
        return {
            "cycle_id": cycle_id,
            "status": "COMPLETED",
            "phase": "REPORTED",
            "active_head_id": active_head,
            "is_promoted": is_promoted,
            "decision": receipt.decision.value,
            "candidate_id": candidate.candidate_id,
            "author_type": candidate.author_type.value,
            "target_task_id": hypothesis.target_task_id,
            "holdout_score": receipt.holdout_score,
            "gain_over_parent": receipt.gain_over_parent,
            "evidence_path": str(evidence_path),
            "proposal": proposal,
            "governance": {
                "release_gate": "BLOCK_RELEASE",
                "scientific_status": "NOT_ASSESSED",
                "oaie_established": False,
            },
        }
