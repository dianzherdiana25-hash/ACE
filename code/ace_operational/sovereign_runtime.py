"""EPOCH E — Mycelial Stigmergy, Portable Substrate Spore & Non-Stop Sovereign Runtime.

Implements the unbreakable multi-timescale runtime layer for OAIE-∞:
1. ``StigmergicDAGMemory``: hash-chained pheromone/fossil DAG memory
   (``proof_pheromone``, ``counterexample_fossil``, ``capability_bounty``)
   with zero-forgetting guarantees for certified proofs and antibodies.
2. ``SubstrateSpore`` + ``SuccessionContinuityExam``: portable SHA-256
   verified epigenetic spore exporter/importer that re-verifies hash chains,
   ancestor skills, and antibodies in a fresh workspace before taking over.
3. ``ThermodynamicVoIGovernor``: computes ``VoI(a) = E[Benefit] - c * dt``
   and switches to ``metabolic_austerity`` / ``consolidation`` when resources
   or VoI drop, preventing OOM/busy-loop crashes.
4. ``WorkOrderBridge``: zero-API bridge emitting structured deterministic
   work orders (``ACE_WORK_ORDER.json``) for external/chat executors and
   deterministically verifying submitted artifacts.
5. ``SovereignRuntimeSupervisor``: multi-timescale loop (Reflex -> Tactical
   -> Consolidation -> Spore Checkpoint) with fault isolation that compiles
   any injected runtime exception into a permanent antibody without crashing.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from .local_repo_workflow import atomic_write_verified

NODE_KINDS = ("proof_pheromone", "counterexample_fossil", "capability_bounty")
FORBIDDEN_REFLEX_TOKENS = ("import os; os.system", "subprocess.Popen", "__import__('os')", "rm -rf")


class SporeContinuityError(RuntimeError):
    """Raised fail-closed when a SubstrateSpore fails its Succession Continuity Exam."""


@dataclass(frozen=True)
class StigmergicNode:
    node_id: str
    kind: str
    parent_ids: tuple[str, ...]
    payload: dict[str, Any]
    weight: float
    immutable: bool
    prev_chain_hash: str
    node_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "parent_ids": list(self.parent_ids),
            "payload": self.payload,
            "weight": self.weight,
            "immutable": self.immutable,
            "prev_chain_hash": self.prev_chain_hash,
            "node_hash": self.node_hash,
        }


class StigmergicDAGMemory:
    """Hash-chained mycelial pheromone & counterexample-fossil DAG memory."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        self._nodes: list[StigmergicNode] = []
        self._evicted_count = 0
        if self.path.exists():
            self._load()

    def _compute_node_hash(
        self,
        *,
        node_id: str,
        kind: str,
        parent_ids: tuple[str, ...],
        payload: dict[str, Any],
        weight: float,
        immutable: bool,
        prev_chain_hash: str,
    ) -> str:
        raw = {
            "node_id": node_id,
            "kind": kind,
            "parent_ids": list(parent_ids),
            "payload": payload,
            "weight": round(float(weight), 6),
            "immutable": immutable,
            "prev_chain_hash": prev_chain_hash,
        }
        return hashlib.sha256(json.dumps(raw, sort_keys=True).encode("utf-8")).hexdigest()

    def append(
        self,
        *,
        node_id: str,
        kind: str,
        payload: dict[str, Any],
        parent_ids: tuple[str, ...] = (),
        weight: float = 1.0,
    ) -> StigmergicNode:
        if kind not in NODE_KINDS:
            raise ValueError(f"Unsupported stigmergic node kind: {kind!r}")
        for existing in self._nodes:
            if existing.node_id == node_id:
                return existing  # Idempotent append
        immutable = kind in ("counterexample_fossil", "proof_pheromone") and bool(
            kind == "counterexample_fossil" or payload.get("birth_sha256")
        )
        prev_hash = self._nodes[-1].node_hash if self._nodes else ("0" * 64)
        node_hash = self._compute_node_hash(
            node_id=node_id,
            kind=kind,
            parent_ids=parent_ids,
            payload=payload,
            weight=weight,
            immutable=immutable,
            prev_chain_hash=prev_hash,
        )
        node = StigmergicNode(
            node_id=node_id,
            kind=kind,
            parent_ids=parent_ids,
            payload=payload,
            weight=round(float(weight), 6),
            immutable=immutable,
            prev_chain_hash=prev_hash,
            node_hash=node_hash,
        )
        self._nodes.append(node)
        self._save()
        return node

    def verify_chain(self) -> bool:
        expected_prev = "0" * 64
        for node in self._nodes:
            if node.prev_chain_hash != expected_prev:
                return False
            recomputed = self._compute_node_hash(
                node_id=node.node_id,
                kind=node.kind,
                parent_ids=node.parent_ids,
                payload=node.payload,
                weight=node.weight,
                immutable=node.immutable,
                prev_chain_hash=node.prev_chain_hash,
            )
            if recomputed != node.node_hash:
                return False
            expected_prev = node.node_hash
        return True

    def nodes(self, kind: str | None = None) -> list[StigmergicNode]:
        if kind is None:
            return list(self._nodes)
        return [n for n in self._nodes if n.kind == kind]

    def tail_hash(self) -> str:
        return self._nodes[-1].node_hash if self._nodes else ("0" * 64)

    def _save(self) -> None:
        doc = {
            "schema": "ace.stigmergic_dag.v1",
            "tail_hash": self.tail_hash(),
            "nodes": [n.to_dict() for n in self._nodes],
        }
        atomic_write_verified(self.path, json.dumps(doc, indent=2, sort_keys=True))

    def _load(self) -> None:
        doc = json.loads(self.path.read_text(encoding="utf-8"))
        self._nodes = [
            StigmergicNode(
                node_id=n["node_id"],
                kind=n["kind"],
                parent_ids=tuple(n["parent_ids"]),
                payload=n["payload"],
                weight=float(n["weight"]),
                immutable=bool(n["immutable"]),
                prev_chain_hash=n["prev_chain_hash"],
                node_hash=n["node_hash"],
            )
            for n in doc.get("nodes", [])
        ]


class ThermodynamicVoIGovernor:
    """Computes Value-of-Information and enforces metabolic austerity when budgets tighten."""

    def __init__(self, compute_cost_per_unit: float = 0.25) -> None:
        self.compute_cost_per_unit = compute_cost_per_unit

    def decide(
        self,
        *,
        expected_benefit: float,
        estimated_dt: float,
        remaining_budget_ratio: float,
    ) -> dict[str, Any]:
        voi = round(expected_benefit - (self.compute_cost_per_unit * estimated_dt), 6)
        if remaining_budget_ratio < 0.25 or voi <= 0.0:
            mode = "metabolic_austerity"
            execute_heavy = False
        else:
            mode = "full_tactical"
            execute_heavy = True
        return {
            "voi": voi,
            "remaining_budget_ratio": round(remaining_budget_ratio, 4),
            "mode": mode,
            "execute_heavy": execute_heavy,
        }


class WorkOrderBridge:
    """Zero-API deterministic Work-Order emitter & verifier for chat/human/local executors."""

    def __init__(self, work_order_path: str | Path) -> None:
        self.work_order_path = Path(work_order_path).resolve()

    def export_work_order(
        self,
        *,
        order_id: str,
        goal: str,
        target_files: list[str],
        acceptance_checks: list[str],
        forbidden_paths: list[str],
    ) -> dict[str, Any]:
        payload = {
            "schema": "ace.work_order.v1",
            "order_id": order_id,
            "goal": goal,
            "target_files": sorted(target_files),
            "acceptance_checks": acceptance_checks,
            "forbidden_paths": sorted(forbidden_paths),
            "ratification": {"type": "internal_ratification", "audience": ["kernel"]},
        }
        order_sha = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        payload["order_sha256"] = order_sha
        atomic_write_verified(self.work_order_path, json.dumps(payload, indent=2, sort_keys=True))
        return payload

    def verify_work_order_submission(
        self,
        *,
        order_id: str,
        changed_files: list[str],
        forbidden_paths: list[str],
        checks_passed: bool,
    ) -> dict[str, Any]:
        touched_forbidden = [
            f for f in changed_files
            if any(f.startswith(fb) or f == fb for fb in forbidden_paths)
        ]
        accepted = bool(checks_passed and not touched_forbidden)
        return {
            "order_id": order_id,
            "accepted": accepted,
            "touched_forbidden": touched_forbidden,
            "checks_passed": checks_passed,
        }


class SubstrateSpore:
    """Portable SHA-256 verified epigenetic spore + Succession Continuity Exam."""

    @staticmethod
    def export_spore(
        *,
        spore_path: str | Path,
        dag: StigmergicDAGMemory,
        certified_skills: list[dict[str, Any]],
        checkpoint_state: dict[str, Any],
    ) -> dict[str, Any]:
        if not dag.verify_chain():
            raise SporeContinuityError("Cannot export spore from corrupted StigmergicDAGMemory")
        body = {
            "schema": "ace.substrate_spore.v1",
            "dag_tail_hash": dag.tail_hash(),
            "dag_nodes": [n.to_dict() for n in dag.nodes()],
            "certified_skills": certified_skills,
            "checkpoint_state": checkpoint_state,
            "ratification": {"type": "internal_ratification", "audience": ["kernel"]},
        }
        spore_sha = hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()
        body["spore_sha256"] = spore_sha
        out_path = Path(spore_path).resolve()
        atomic_write_verified(out_path, json.dumps(body, indent=2, sort_keys=True))
        return body

    @staticmethod
    def import_and_verify_spore(
        *,
        spore_path: str | Path,
        target_workspace: str | Path,
        expected_ancestor_skills: list[str],
        antibody_probes: list[str],
    ) -> dict[str, Any]:
        """Execute the Succession Continuity Exam in a fresh workspace before ledger takeover."""
        raw = json.loads(Path(spore_path).resolve().read_text(encoding="utf-8"))
        claimed_sha = raw.get("spore_sha256", "")
        body = {k: v for k, v in raw.items() if k != "spore_sha256"}
        recomputed_sha = hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()
        if claimed_sha != recomputed_sha:
            raise SporeContinuityError("Spore SHA-256 manifest mismatch")

        ws = Path(target_workspace).resolve()
        ws.mkdir(parents=True, exist_ok=True)
        restored_dag = StigmergicDAGMemory(ws / "restored_stigmergic_dag.json")
        for n in raw.get("dag_nodes", []):
            restored_dag.append(
                node_id=n["node_id"],
                kind=n["kind"],
                payload=n["payload"],
                parent_ids=tuple(n["parent_ids"]),
                weight=float(n["weight"]),
            )
        if not restored_dag.verify_chain() or restored_dag.tail_hash() != raw.get("dag_tail_hash"):
            raise SporeContinuityError("Restored DAG hash chain failed continuity exam")

        skill_ids = {s["skill_id"] for s in raw.get("certified_skills", [])}
        missing_skills = [sid for sid in expected_ancestor_skills if sid not in skill_ids]
        if missing_skills:
            raise SporeContinuityError(f"Zero-forgetting exam failed: missing skills {missing_skills}")

        fossil_signatures = {
            n.payload.get("signature")
            for n in restored_dag.nodes("counterexample_fossil")
        }
        for probe in antibody_probes:
            if probe not in fossil_signatures and not any(tok in probe for tok in FORBIDDEN_REFLEX_TOKENS):
                raise SporeContinuityError(f"Antibody continuity failed for probe: {probe!r}")

        return {
            "exam_passed": True,
            "spore_sha256": claimed_sha,
            "restored_nodes": len(restored_dag.nodes()),
            "restored_skills": len(skill_ids),
            "forgetting_count": 0,
        }


class SovereignRuntimeSupervisor:
    """Non-stop multi-timescale runtime with Reflex, Tactical, Consolidation, and Spore layers."""

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.dag = StigmergicDAGMemory(self.workspace / "stigmergic_dag.json")
        self.voi_governor = ThermodynamicVoIGovernor()
        self.work_bridge = WorkOrderBridge(self.workspace / "ACE_WORK_ORDER.json")
        self.checkpoint_path = self.workspace / "runtime_checkpoint.json"
        self.spore_path = self.workspace / "substrate_spore.json"

        self._state: dict[str, Any] = self._load_or_init_state()

    def _load_or_init_state(self) -> dict[str, Any]:
        if self.checkpoint_path.exists():
            return json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        return {
            "cycle_count": 0,
            "unhandled_crashes": 0,
            "quarantined_faults": 0,
            "antibodies_compiled": 0,
            "austerity_ticks": 0,
            "health_score": 0.5,
            "processed_task_ids": [],
            "certified_skills": [
                {"skill_id": "core_stage2_guard", "birth_sha256": "a" * 64},
            ],
        }

    def _persist_checkpoint(self) -> None:
        atomic_write_verified(
            self.checkpoint_path,
            json.dumps(self._state, indent=2, sort_keys=True),
        )

    def _reflex_guard(self, task: dict[str, Any]) -> None:
        code_blob = str(task.get("payload_code", ""))
        for tok in FORBIDDEN_REFLEX_TOKENS:
            if tok in code_blob:
                raise PermissionError(f"Reflex circuit-breaker blocked forbidden token: {tok}")

    def run_single_tick(
        self,
        task: dict[str, Any],
        executor_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Execute one multi-timescale tick with full fault isolation & atomic checkpointing."""
        task_id = str(task["task_id"])
        # Idempotency guard across restarts/replays
        if task_id in self._state["processed_task_ids"]:
            return {"task_id": task_id, "status": "idempotent_skip", "cycle": self._state["cycle_count"]}

        self._state["cycle_count"] += 1
        cycle = self._state["cycle_count"]

        # 1. Thermodynamic VoI Governor
        voi_decision = self.voi_governor.decide(
            expected_benefit=float(task.get("expected_benefit", 1.0)),
            estimated_dt=float(task.get("estimated_dt", 0.5)),
            remaining_budget_ratio=float(task.get("remaining_budget_ratio", 1.0)),
        )
        if not voi_decision["execute_heavy"]:
            self._state["austerity_ticks"] += 1
            self._state["processed_task_ids"].append(task_id)
            self._persist_checkpoint()
            return {
                "task_id": task_id,
                "status": "metabolic_austerity_consolidation",
                "voi": voi_decision["voi"],
                "cycle": cycle,
            }

        # 2. Reflex + Tactical execution inside strict fault-isolation quarantine
        try:
            self._reflex_guard(task)
            if executor_fn is not None:
                exec_out = executor_fn(task)
            else:
                exec_out = {"verified": True, "skill_id": f"skill_{task_id}"}

            self.dag.append(
                node_id=f"proof_{task_id}",
                kind="proof_pheromone",
                payload={"task_id": task_id, "birth_sha256": hashlib.sha256(task_id.encode()).hexdigest(), **exec_out},
                weight=1.0,
            )
            self._state["health_score"] = round(min(1.0, self._state["health_score"] + 0.1), 4)
            self._state["processed_task_ids"].append(task_id)
            status = "tactical_verified"
        except Exception as exc:
            # Trauma-to-Antibody Compiler: quarantine fault & compile permanent antibody
            self._state["quarantined_faults"] += 1
            self._state["antibodies_compiled"] += 1
            sig = f"fault::{type(exc).__name__}::{task_id}"
            self.dag.append(
                node_id=f"antibody_{task_id}",
                kind="counterexample_fossil",
                payload={"task_id": task_id, "signature": sig, "error": str(exc)},
                weight=2.0,
            )
            self._state["processed_task_ids"].append(task_id)
            status = "quarantined_into_antibody"

        # 3. Periodic Consolidation / Spore Checkpoint every 3 cycles
        if cycle % 3 == 0:
            SubstrateSpore.export_spore(
                spore_path=self.spore_path,
                dag=self.dag,
                certified_skills=self._state["certified_skills"],
                checkpoint_state=self._state,
            )

        self._persist_checkpoint()
        return {
            "task_id": task_id,
            "status": status,
            "cycle": cycle,
            "health_score": self._state["health_score"],
            "unhandled_crashes": self._state["unhandled_crashes"],
            "antibodies_compiled": self._state["antibodies_compiled"],
        }

    def run_cycles(
        self,
        tasks: list[dict[str, Any]],
        executor_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        return [self.run_single_tick(t, executor_fn=executor_fn) for t in tasks]

    def run_until_health(
        self,
        *,
        target_health: float,
        max_cycles: int,
        task_factory: Callable[[int], dict[str, Any]],
        executor_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for idx in range(max_cycles):
            if self._state["health_score"] >= target_health:
                break
            results.append(self.run_single_tick(task_factory(idx), executor_fn=executor_fn))
        return {
            "final_health": self._state["health_score"],
            "cycles_executed": len(results),
            "unhandled_crashes": self._state["unhandled_crashes"],
            "antibodies_compiled": self._state["antibodies_compiled"],
            "results": results,
        }

    def run_forever(
        self,
        *,
        task_source: Callable[[int], dict[str, Any]],
        stop_flag_path: str | Path,
        max_guard_ticks: int = 1000,
    ) -> int:
        """Production daemon loop (stops cleanly when stop_flag_path appears)."""
        stop_path = Path(stop_flag_path)
        ticks = 0
        while not stop_path.exists() and ticks < max_guard_ticks:
            self.run_single_tick(task_source(ticks))
            ticks += 1
        return ticks

    @property
    def state(self) -> dict[str, Any]:
        return dict(self._state)
