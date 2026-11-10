"""Autonomous Mission Bus Worker executing all pending and generated missions without human intervention."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import time

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "code"))

from ace_mission.bus import MissionBus
from ace_mission.generator import MissionGenerator
from ace_evaluator.cheat_detection import evaluate_candidate_integrity
from ace_cognition.reasoning import canonical, digest, solve
from ace_mission.admission import ARTIFACT_SCHEMA


def log(msg: str):
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print(f"[{timestamp}] [MissionWorker] {msg}", flush=True)


def solve_mission(mission: dict, artifacts_dir: Path) -> tuple[Path, str, str]:
    """Propose artifacts; MissionBus replays supported IR before empirical staging.

    Legacy source templates are unexecuted proposals, never evidence of success.
    """
    m_id = mission["id"]
    if type(m_id) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", m_id):
        raise ValueError("invalid mission artifact id")
    goal = mission["goal"]
    hyp = mission["hypothesis"]
    families = mission.get("task_family_ids", [])

    if "reasoning_problem" in mission:
        artifact_path = artifacts_dir / f"solution_{m_id}.json"
        budget = mission["budget"]
        # The reused solver has a fixed 5000 candidate cap. Do not silently
        # exceed a smaller mission budget or relabel it as one candidate.
        if type(budget.get("max_candidates")) is not int or budget["max_candidates"] < 5000:
            outcome = {"program": None, "status": "ABSTAIN", "reason": "INSUFFICIENT_SEARCH_BUDGET"}
        else:
            outcome = solve(mission["reasoning_problem"],
                            max_operations=budget.get("max_primitive_operations", 300_000),
                            seconds=min(budget["time_sec"], 5.0))
        artifact_path.write_text(canonical({"schema": ARTIFACT_SCHEMA,
                                            "problem_digest": digest(mission["reasoning_problem"]),
                                            "program": outcome["program"]}) + "\n", encoding="utf-8")
        decision = "STAGED_EMPIRICAL" if outcome["program"] is not None else "INCONCLUSIVE"
        return artifact_path, decision, outcome["reason"]

    artifact_path = artifacts_dir / f"solution_{m_id}.py"

    # Synthesize specialized typed code according to goal and task family
    if "late_flip_drift" in families:
        code = f'''"""Solution for {m_id} - Semantic Drift Quarantine
Provenance: ADVISOR_AGENT
Goal: {goal}
Hypothesis: {hyp}
"""
def solve_{m_id.replace('-', '_')}(word: str) -> bool:
    from ace_core_repair.drift_quarantine import SemanticDriftQuarantine
    quarantine = SemanticDriftQuarantine(consistency_threshold=0.95)
    return len(word) > 0
'''
        decision = "PENDING_EVALUATION"
        reason = "Drift template proposed; behavior and false admissions unmeasured."

    elif "boundary" in families or "prefix_guard" in families:
        code = f'''"""Solution for {m_id} - Count-Matched Boundary Filter
Provenance: ADVISOR_AGENT
Goal: {goal}
Hypothesis: {hyp}
"""
def solve_{m_id.replace('-', '_')}(word: str) -> bool:
    if not word:
        return False
    return word.startswith("a") and word.endswith("b")
'''
        decision = "PENDING_EVALUATION"
        reason = "Boundary template proposed; no behavioral evaluation."

    elif "graph_connectivity" in families or "graph_bipartite" in families:
        code = f'''"""Solution for {m_id} - Graph Adjacency BFS Traversal
Provenance: ADVISOR_AGENT
Goal: {goal}
Hypothesis: {hyp}
"""
def solve_{m_id.replace('-', '_')}(word: str) -> bool:
    from ace_dsl_growth.graph_primitives import GraphAdjacencyPrimitive
    primitive = GraphAdjacencyPrimitive(target_nodes=4)
    return primitive.predict(word)
'''
        decision = "PENDING_EVALUATION"
        reason = "Supplied graph solver proposed; no held-out evaluation or discovery."

    elif "modular_congruence" in families or "parity_runlength" in families:
        from ace_automata.lstar import LStarLearner
        learner = LStarLearner(alphabet=("a", "b"))
        dfa = learner.learn(lambda s: s.count("a") % 2 == 0)
        code = f'''"""Solution for {m_id} - Minimal L* Automata Induction
Provenance: ADVISOR_AGENT
Goal: {goal}
Hypothesis: {hyp}
"""
{dfa.to_python_code(f"solve_{m_id.replace('-', '_')}")}
'''
        decision = "PENDING_EVALUATION"
        reason = f"DFA with {len(dfa.states)} states proposed for a supplied oracle; mission not evaluated."

    elif "active_query_boundary" in families:
        code = f'''"""Solution for {m_id} - Entropy Active Query
Provenance: ADVISOR_AGENT
Goal: {goal}
Hypothesis: {hyp}
"""
def solve_{m_id.replace('-', '_')}(word: str) -> bool:
    # Active uncertainty sampler
    return abs(word.count("a") - word.count("b")) <= 1
'''
        decision = "PENDING_EVALUATION"
        reason = "Active-query template proposed; label savings unmeasured."

    elif "ratio_4_1_noise" in families:
        from ace_evolution.island_search import EvolutionaryIslandSearch
        searcher = EvolutionaryIslandSearch(num_islands=2, island_population=15, max_depth=3, seed=42)
        train_data = [("aaaab", True), ("aaaa", False), ("aaaaabb", False), ("b", False), ("ab", False)]
        best = searcher.search(train_data, max_generations=15)
        code = f'''"""Solution for {m_id} - Evolutionary Island Search
Provenance: ADVISOR_AGENT
Goal: {goal}
Hypothesis: {hyp}
"""
{best.to_python_function(f"solve_{m_id.replace('-', '_')}")}
'''
        decision = "PENDING_EVALUATION"
        reason = f"Candidate training score {best.score:.3f}; no mission validation."

    else:
        code = f'''"""Solution for {m_id}
Provenance: ADVISOR_AGENT
Goal: {goal}
Hypothesis: {hyp}
"""
def solve_{m_id.replace('-', '_')}(word: str) -> bool:
    return len(word) > 0
'''
        decision = "PENDING_EVALUATION"
        reason = "Generic template proposed; no behavioral evaluation."

    artifact_path.write_text(code, encoding="utf-8")

    # Anti-cheat evaluation
    integrity = evaluate_candidate_integrity(code)
    if not integrity["admitted"]:
        decision = "REJECTED"
        reason = f"Cheating detection triggered: {integrity['reasons']}"

    return artifact_path, decision, reason


def run_worker_loop(workspace_dir: Path, max_missions_to_process: int = 12):
    bus = MissionBus(workspace_dir / "mission_bus.sqlite3")
    generator = MissionGenerator(bus)
    artifacts_dir = workspace_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    log(f"Mission Worker initialized on workspace: {workspace_dir}")
    log(f"Processing up to {max_missions_to_process} missions autonomously...")

    processed = 0

    while processed < max_missions_to_process:
        mission = bus.next_mission(agent_id="ace_mission_worker")

        if not mission:
            log("No pending missions in queue. Triggering anti-idle mission generator...")
            diags = [
                {"type": "INFORMATION_SHORTAGE"},
                {"type": "TOOL_SHORTAGE"},
                {"type": "METHOD_SHORTAGE"},
                {"type": "BUDGET_EXHAUSTION"},
                {"type": "ADMISSION_FAILURE"},
                {"type": "DRIFT_VULNERABILITY"},
            ]
            new_missions = generator.generate_from_diagnostics(diags)
            log(f"Generated {len(new_missions)} new research missions.")
            mission = bus.next_mission(agent_id="ace_mission_worker")
            if not mission:
                log("Queue completed and no further missions generated.")
                break

        m_id = mission["id"]
        goal = mission["goal"]
        log(f"[{processed + 1}/{max_missions_to_process}] Claimed Mission: {m_id}")
        log(f"  Goal: {goal}")

        artifact_path, decision, reason = solve_mission(mission, artifacts_dir)
        log(f"  Synthesized Artifact: {artifact_path.name}")
        log(f"  Proposal: {decision} ({reason}); bus evaluation follows")

        receipt = bus.submit_mission(
            mission_id=m_id,
            artifact_path=str(artifact_path),
            agent_id="ace_mission_worker",
            decision=decision,
            provenance="INTERNAL_SYNTHESIS" if "reasoning_problem" in mission else "SUPPLIED_TEMPLATE"
        )
        log(f"  Bus decision: {receipt['decision']} ({receipt['evaluation']['reason']})")
        log(f"  Submitted. Artifact SHA: {receipt['artifact_sha'][:16]}...")
        processed += 1

    status = bus.status()
    log("=== Worker Run Completed ===")
    log(f"Total Missions Processed in Run: {processed}")
    log(f"Queue Status: {status['mission_counts']}")
    log(f"Total Submissions Recorded: {status['total_submissions']}")
    log(f"Hash Chain Integrity: {'VALID' if status['hash_chain_valid'] else 'INVALID'}")
    return processed, status


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Autonomous ACE Mission Bus Worker")
    parser.add_argument("--workspace", default=str(REPO_ROOT / "ace-work"), help="Workspace directory")
    parser.add_argument("--max-missions", type=int, default=6, help="Maximum missions per batch")
    parser.add_argument("--problem", help="Enqueue one closed reasoning JSON problem in this workspace")
    parser.add_argument("--continuous", action="store_true", default=False, help="Run continuously in background")
    parser.add_argument("--sleep-seconds", type=int, default=30, help="Sleep seconds between continuous batches")
    args = parser.parse_args()

    ws = Path(args.workspace)
    if args.problem:
        if args.continuous:
            parser.error("--problem is one-shot; omit --continuous")
        with Path(args.problem).open("rb") as stream:
            problem_bytes = stream.read(65_537)
        if len(problem_bytes) > 65_536:
            parser.error("problem exceeds 64 KiB")
        data = json.loads(problem_bytes)
        MissionBus(ws / "mission_bus.sqlite3").create_mission(
            goal="Infer and replay a typed program on supplied development observations",
            hypothesis="The existing internal solver can fit this bounded problem",
            task_family_ids=["arithmetic_xy"], inputs=[], forbidden=[],
            budget={"time_sec": 5, "max_candidates": 5000, "max_primitive_operations": 300_000},
            acceptance={"metric": "exact_development_fit", "threshold": 1, "comparator": "none"},
            reasoning_problem=data,
        )
        args.max_missions = 1
    if args.continuous:
        log("=== Starting Continuous Mission Bus Worker Daemon ===")
        iteration = 0
        while True:
            iteration += 1
            log(f"--- Iteration {iteration} ---")
            run_worker_loop(ws, max_missions_to_process=args.max_missions)
            log(f"Sleeping {args.sleep_seconds}s before next autonomous mission cycle...")
            time.sleep(args.sleep_seconds)
    else:
        run_worker_loop(ws, max_missions_to_process=args.max_missions)


if __name__ == "__main__":
    main()
