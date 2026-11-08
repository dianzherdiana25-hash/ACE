"""Autonomous Continuous Researcher Agent Pipeline.

Enables researcher agents to:
1. Formulate hypotheses and scout novel algorithmic capabilities.
2. Package findings into structured DiscoveryProposals.
3. Notify the coordinating agent (Antigravity) via messages/events.
4. Immediately resume searching for subsequent capabilities in an uninterrupted loop.
5. Track proposal lifecycle: PROPOSED -> IMPLEMENTED -> VERIFIED -> BENCHMARKED.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class DiscoveryProposal:
    proposal_id: str
    capability_name: str
    target_bottleneck: str
    mathematical_foundation: str
    suggested_implementation: str
    verification_criteria: str
    author_agent: str
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    status: str = "PROPOSED"  # PROPOSED, IMPLEMENTED, VERIFIED, BENCHMARKED
    implementation_commit: Optional[str] = None
    evaluation_receipt: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DiscoveryProposal:
        return cls(**data)


class ContinuousResearcherPipeline:
    """Manages the autonomous discovery agenda and two-way handoff loop."""

    # Default curricular research topics derived from computer science literature
    CURRICULUM_TOPICS = [
        {
            "capability_name": "Counterexample-Guided Inductive Synthesis (CEGIS)",
            "target_bottleneck": "Synthesis search space explosion when validating against large test sets",
            "mathematical_foundation": "Iterative verifier-synthesizer loop finding minimal distinguishing counterexample constraints",
            "suggested_implementation": "code/ace_synthesis/cegis.py",
            "verification_criteria": "Guaranteed convergence to correct candidate with minimal oracle calls"
        },
        {
            "capability_name": "Monte Carlo Tree Search (MCTS) Program Tree Exploration",
            "target_bottleneck": "Exponential branching factor in grammar-guided expression generation",
            "mathematical_foundation": "UCT (Upper Confidence bounds applied to Trees) balancing exploration and exploitation in AST construction",
            "suggested_implementation": "code/ace_mcts/program_mcts.py",
            "verification_criteria": "Finds target predicates 5x faster than blind exhaustive enumeration"
        },
        {
            "capability_name": "Abstract Interpretation Invariant Analyzer",
            "target_bottleneck": "Unobservable runtime semantic drift, out-of-bounds states, and unbounded loops in candidate execution",
            "mathematical_foundation": "Interval & polyhedral abstract domain fixed-point iteration for invariant synthesis and safety bounds",
            "suggested_implementation": "code/ace_abstract_interp/invariants.py",
            "verification_criteria": "Zero false negatives in detecting out-of-bound variables or non-terminating ASTs, with sound inductive invariant synthesis"
        },
        {
            "capability_name": "Relational Predicate Mining (Inductive Logic Programming)",
            "target_bottleneck": "Multi-entity graph relationship and topological structure discovery",
            "mathematical_foundation": "First-order horn clause induction over background relational facts",
            "suggested_implementation": "code/ace_ilp/relational_miner.py",
            "verification_criteria": "Induces connectivity, reachability, and transitivity rules automatically"
        },
        {
            "capability_name": "Active Epistemic Uncertainty Sampling (BALD)",
            "target_bottleneck": "High verification oracle query costs and sample-inefficient counterexamples",
            "mathematical_foundation": "Mutual information maximization over hypothesis posterior (Bayesian Active Learning by Disagreement)",
            "suggested_implementation": "code/ace_epistemic/active_sampler.py",
            "verification_criteria": "Achieves >= 60% sample efficiency gain over uniform random query generation"
        },
        {
            "capability_name": "Neural-Guided A* Heuristic Program Search",
            "target_bottleneck": "Exponential state space explosion in grammar-guided partial AST enumeration",
            "mathematical_foundation": "Statistical feature estimator P(rule | spec) and admissible A* cost-to-go bounds h(s)",
            "suggested_implementation": "code/ace_neurosymbolic/neural_guided_search.py",
            "verification_criteria": "Achieves 5-10x speedup over exhaustive search without compromising soundness on typed ASTs"
        },
        {
            "capability_name": "Causal Invariant Graph Mining (Structural Causal Models)",
            "target_bottleneck": "Spurious observational correlations and hidden confounders in candidate program execution",
            "mathematical_foundation": "Pearl's do-calculus interventional distributions P(Y | do(X)) and d-separation invariance",
            "suggested_implementation": "code/ace_causal/causal_miner.py",
            "verification_criteria": "Identifies true causal invariants with zero false discovery under non-interventional confounders"
        },
        {
            "capability_name": "Differentiable Neurosymbolic Program Sketching",
            "target_bottleneck": "Discrete combinatorial cliff in high-order multi-primitive AST synthesis",
            "mathematical_foundation": "Continuous relaxation over AST grammar productions with Gumbel-Softmax annealing",
            "suggested_implementation": "code/ace_neurosymbolic/sketch_synthesizer.py",
            "verification_criteria": "Converges to verified AST program sketches with 10x search space compression"
        },
        {
            "capability_name": "PAC-Bayesian Generalization Bound Estimator",
            "target_bottleneck": "Unbounded generalization error and catastrophic overfitting in synthesized program distributions",
            "mathematical_foundation": "McAllester and Seeger-Maurer PAC-Bayesian theorems inverting relative entropy kl(R_hat || R) <= (KL + ln(2*sqrt(m)/delta)) / m",
            "suggested_implementation": "code/ace_pac_bayes/pac_bounds.py",
            "verification_criteria": "Guarantees finite sample population risk bounds with confidence >= 1 - delta, strictly tighter than naive union bounds"
        },
        {
            "capability_name": "Conformal Risk Control & Distribution-Free Prediction Sets",
            "target_bottleneck": "Uncalibrated confidence intervals and lack of finite-sample coverage guarantees for program outputs",
            "mathematical_foundation": "Split conformal prediction and bounded loss exchangeability (Vovk et al., 2005; Bates et al., 2021)",
            "suggested_implementation": "code/ace_conformal/conformal_risk.py",
            "verification_criteria": "Guaranteed 1 - alpha marginal coverage on arbitrary non-parametric test distributions"
        },
        {
            "capability_name": "Bidirectional Program Inversion (Category-Theoretic Lenses)",
            "target_bottleneck": "One-way synthesis inability to derive invertible parsers, encoders/decoders, and bijective DSL transducers",
            "mathematical_foundation": "Asymmetric lens laws (Get-Put, Put-Get) and Galois connections over algebraic data types",
            "suggested_implementation": "code/ace_inversion/bidirectional_transducer.py",
            "verification_criteria": "Guaranteed round-trip bijectivity f^{-1}(f(x)) == x across non-trivial structured domains"
        }
    ]

    def __init__(self, workspace_path: Path):
        self.workspace = Path(workspace_path)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.workspace / "discovery_registry.json"
        self.proposals: Dict[str, DiscoveryProposal] = {}
        self.current_curriculum_index = 0
        self._load_registry()

    def _load_registry(self):
        if self.registry_file.exists():
            try:
                data = json.loads(self.registry_file.read_text(encoding="utf-8"))
                self.proposals = {
                    pid: DiscoveryProposal.from_dict(p)
                    for pid, p in data.get("proposals", {}).items()
                }
                self.current_curriculum_index = data.get("current_index", 0)
            except Exception:
                self.proposals = {}
                self.current_curriculum_index = 0

    def _save_registry(self):
        data = {
            "current_index": self.current_curriculum_index,
            "total_proposals": len(self.proposals),
            "proposals": {pid: p.to_dict() for pid, p in self.proposals.items()}
        }
        self.registry_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def scout_next_capability(self, agent_id: str = "scout_agent_01") -> DiscoveryProposal:
        """Agent scouts and proposes the next breakthrough capability, advancing research agenda."""
        topic = self.CURRICULUM_TOPICS[self.current_curriculum_index % len(self.CURRICULUM_TOPICS)]
        self.current_curriculum_index += 1

        proposal_raw = f"{topic['capability_name']}_{self.current_curriculum_index}_{datetime.datetime.now().timestamp()}"
        pid = f"disc_{hashlib.sha256(proposal_raw.encode()).hexdigest()[:10]}"

        proposal = DiscoveryProposal(
            proposal_id=pid,
            capability_name=topic["capability_name"],
            target_bottleneck=topic["target_bottleneck"],
            mathematical_foundation=topic["mathematical_foundation"],
            suggested_implementation=topic["suggested_implementation"],
            verification_criteria=topic["verification_criteria"],
            author_agent=agent_id,
            status="PROPOSED"
        )
        self.proposals[pid] = proposal
        self._save_registry()
        return proposal

    def mark_implemented(self, proposal_id: str, commit_sha: str) -> DiscoveryProposal:
        """Coordinating agent (Antigravity) records code implementation."""
        if proposal_id not in self.proposals:
            raise KeyError(f"Proposal {proposal_id} not found")
        p = self.proposals[proposal_id]
        p.status = "IMPLEMENTED"
        p.implementation_commit = commit_sha
        self._save_registry()
        return p

    def mark_verified(self, proposal_id: str, receipt: Dict[str, Any]) -> DiscoveryProposal:
        """Coordinating agent records test suite verification and holdout evaluation receipt."""
        if proposal_id not in self.proposals:
            raise KeyError(f"Proposal {proposal_id} not found")
        p = self.proposals[proposal_id]
        p.status = "VERIFIED"
        p.evaluation_receipt = receipt
        self._save_registry()
        return p

    def pending_implementations(self) -> List[DiscoveryProposal]:
        """Returns proposals waiting for implementation."""
        return [p for p in self.proposals.values() if p.status == "PROPOSED"]


def audit_and_enforce_agent_missions(
    active_agents: List[Dict[str, Any]],
    active_mission_agent_ids: Set[str],
) -> Dict[str, Any]:
    """Strict lifecycle governor enforcing:
    1. Zero idle agents: Any agent runtime without an active mission is flagged for immediate termination.
    2. Zero obsolete agents: Any agent that has completed its task or is not needed is shut down.
    """
    valid_active = []
    to_terminate = []

    for ag in active_agents:
        ag_id = ag.get("conversationId") or ag.get("id") or ag.get("agent_id")
        role = ag.get("role", "unknown")
        state = ag.get("state", "running")

        # Condition: An agent must not be idle, and must have an active assigned mission
        if state == "idle" or ag_id not in active_mission_agent_ids:
            to_terminate.append({
                "id": ag_id,
                "role": role,
                "reason": "IDLE_OR_UNASSIGNED_MISSION" if state == "idle" else "NO_ACTIVE_MISSION_ASSIGNED"
            })
        else:
            valid_active.append(ag)

    return {
        "total_audited": len(active_agents),
        "valid_active_count": len(valid_active),
        "termination_targets": to_terminate,
        "clean_state": len(to_terminate) == 0,
    }

