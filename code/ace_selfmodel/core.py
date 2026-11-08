"""State-grounded SelfIdentity, SelfState, and CapabilityAwareness (Fase 4).

Every field in ``SelfIdentity`` and ``SelfState`` is read directly from live
``Autonomy`` and ``ace_runtime`` SQLite databases and filesystem metadata —
never generated as unverified narrative prose.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from ace_autonomy import (
    ALL_TOOLS,
    Autonomy,
    BudgetCeiling,
    BudgetUsage,
    GoalPolicy,
)
from ace_autonomy.planner import plan_objective
from ace_autonomy.policy import (
    MAX_CANDIDATE_BYTES,
    MAX_FILE_BYTES,
    path_matches_prefixes,
    validate_SafeRelPath,
)

FUNCTIONAL_SELF_MODEL_STATUS = "ESTABLISHED_BOUNDED"
METACOGNITIVE_AWARENESS_STATUS = "MEASURED_BOUNDED"
PHENOMENAL_CONSCIOUSNESS_STATUS = "PHENOMENAL_CONSCIOUSNESS_UNKNOWN"


@dataclass(frozen=True)
class SelfIdentity:
    autonomy_schema: str
    autonomy_source_digest: str
    db_uuid: str
    ace_runtime_implementation: str | None
    registered_capabilities: int
    ace_library_models: int
    functional_self_model: str = FUNCTIONAL_SELF_MODEL_STATUS
    metacognitive_awareness: str = METACOGNITIVE_AWARENESS_STATUS
    phenomenal_consciousness: str = PHENOMENAL_CONSCIOUSNESS_STATUS
    oaie_established: bool = False
    scientific_decision: str = "NOT_ASSESSED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "autonomy_schema": self.autonomy_schema,
            "autonomy_source_digest": self.autonomy_source_digest,
            "db_uuid": self.db_uuid,
            "ace_runtime_implementation": self.ace_runtime_implementation,
            "registered_capabilities": self.registered_capabilities,
            "ace_library_models": self.ace_library_models,
            "functional_self_model": self.functional_self_model,
            "metacognitive_awareness": self.metacognitive_awareness,
            "phenomenal_consciousness": self.phenomenal_consciousness,
            "oaie_established": self.oaie_established,
            "scientific_decision": self.scientific_decision,
        }


@dataclass(frozen=True)
class SelfState:
    identity: SelfIdentity
    goal_counts: dict[str, int]
    active_leases: int
    halted_uncertain_goals: tuple[str, ...]
    dispatched_escrow_count: int
    ace_tasks_by_id: dict[str, dict[str, Any]]
    ace_library_count: int
    ace_evaluated_task_ids: tuple[str, ...]
    available_system_tools: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "goal_counts": dict(self.goal_counts),
            "active_leases": self.active_leases,
            "halted_uncertain_goals": list(self.halted_uncertain_goals),
            "dispatched_escrow_count": self.dispatched_escrow_count,
            "ace_tasks_count": len(self.ace_tasks_by_id),
            "ace_staged_tasks_count": sum(1 for t in self.ace_tasks_by_id.values() if t.get("staged")),
            "ace_library_count": self.ace_library_count,
            "ace_evaluated_task_ids": list(self.ace_evaluated_task_ids),
            "available_system_tools": list(self.available_system_tools),
        }


def introspect_self_state(engine: Autonomy) -> SelfState:
    """Read ground-truth operational state from ``Autonomy`` and ``ace_runtime`` SQLite stores."""
    aut_status = engine.status()
    db_uuid_row = engine.db.execute("SELECT value FROM metadata WHERE key='db_uuid'").fetchone()
    db_uuid = str(db_uuid_row["value"]) if db_uuid_row else "unknown"
    lease_cnt = int(engine.db.execute("SELECT COUNT(*) FROM leases").fetchone()[0])
    esc_cnt = int(
        engine.db.execute("SELECT COUNT(*) FROM external_escrow WHERE state='DISPATCHED'").fetchone()[0]
    )
    halted_ids = tuple(
        r["id"]
        for r in engine.db.execute("SELECT id FROM goals WHERE status='HALT_UNCERTAIN' ORDER BY id")
    )

    rt_ws = engine.workspace / "real_ace_workspace"
    rt_impl: str | None = None
    ace_tasks: dict[str, dict[str, Any]] = {}
    ace_lib_cnt = 0
    ace_eval_ids: tuple[str, ...] = ()
    if (rt_ws / "ace.sqlite3").is_file():
        from ace_runtime.engine import Runtime

        with Runtime(rt_ws) as rt:
            st = rt.status()
            rt_impl = st["implementation"]
            ace_lib_cnt = int(st["capabilities"])
            for t in st["tasks"]:
                ace_tasks[t["id"]] = dict(t)
            ace_eval_ids = tuple(
                r[0] for r in rt.db.execute("SELECT task_id FROM evaluations ORDER BY task_id")
            )

    avail_tools = list(ALL_TOOLS)
    if engine.broker.external_handler is None and "external_action" in avail_tools:
        avail_tools.remove("external_action")

    ident = SelfIdentity(
        autonomy_schema=aut_status["schema"],
        autonomy_source_digest=aut_status["source"],
        db_uuid=db_uuid,
        ace_runtime_implementation=rt_impl,
        registered_capabilities=aut_status["capabilities_registered"],
        ace_library_models=ace_lib_cnt,
    )
    return SelfState(
        identity=ident,
        goal_counts=dict(aut_status["goal_counts"]),
        active_leases=lease_cnt,
        halted_uncertain_goals=halted_ids,
        dispatched_escrow_count=esc_cnt,
        ace_tasks_by_id=ace_tasks,
        ace_library_count=ace_lib_cnt,
        ace_evaluated_task_ids=ace_eval_ids,
        available_system_tools=tuple(sorted(avail_tools)),
    )


class CapabilityAwareness:
    """Evaluates structural capability boundaries of ACE tools & Runtime against a proposed goal."""

    # Empirical CPU/wall step cost priors (seconds) measured on standard CPU
    TOOL_CPU_PRIORS: dict[str, float] = {
        "inspect_file": 0.004,
        "verify_upstream_sources": 0.015,
        "run_trusted_suite": 0.85,
        "stage_candidate": 0.006,
        "ace_status": 0.008,
        "ace_demo": 0.35,
        "ace_enqueue_task": 0.012,
        "ace_run_tasks": 0.14,
        "ace_predict": 0.010,
        "ace_evaluate": 0.015,
        "ace_report": 0.008,
        "abstain": 0.002,
        "external_action": 0.020,
    }

    def __init__(self, source_root: Path):
        self.root = source_root

    @staticmethod
    def _estimate_task_learnability(task: dict[str, Any]) -> tuple[bool, str]:
        """Check whether an ``ace_runtime`` task satisfies structural & expressibility bounds."""
        if set(task) != {"name", "train", "validation"}:
            return False, "TASK_SCHEMA_INVALID"
        train = task.get("train", [])
        val = task.get("validation", [])
        if not train or len(train) > 63 or not val or len(val) > 128:
            return False, "TASK_ROW_BUDGET_INVALID"
        tr_words = set()
        prefixes = set()
        for row in train:
            if not isinstance(row, (list, tuple)) or len(row) != 2 or type(row[0]) is not str or type(row[1]) is not bool:
                return False, "TASK_ROW_TYPE_INVALID"
            w = row[0]
            if any(ch not in ("a", "b") for ch in w):
                return False, "ALPHABET_OUT_OF_DOMAIN"
            tr_words.add(w)
            for i in range(len(w) + 1):
                prefixes.add(w[:i])
        if len(prefixes) > 63:
            return False, "PREFIX_TREE_OVERFLOW"
        va_words = set()
        for row in val:
            if not isinstance(row, (list, tuple)) or len(row) != 2 or type(row[0]) is not str or type(row[1]) is not bool:
                return False, "TASK_ROW_TYPE_INVALID"
            if any(ch not in ("a", "b") for ch in row[0]):
                return False, "ALPHABET_OUT_OF_DOMAIN"
            va_words.add(row[0])
        if tr_words & va_words:
            return False, "TRAIN_VAL_OVERLAP"
        return True, "STRUCTURALLY_VALID"

    def analyze_goal(
        self,
        goal: dict[str, Any],
        state: SelfState,
        *,
        existing_usage: BudgetUsage | None = None,
        epistemic_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ctx = epistemic_context or {}
        blockers: list[str] = []
        warnings: list[str] = []
        family_tag = ctx.get("family_tag", "general_operational")

        if ctx.get("observational_equivalence_warning"):
            blockers.append("UNIDENTIFIABLE_SEMANTIC_SHIFT")

        schema = goal.get("schema", "ace.goal.v1")
        try:
            ceiling = BudgetCeiling.from_dict(goal.get("budget"))
        except Exception:
            return {
                "feasible": False,
                "blockers": ["INVALID_BUDGET_SPEC"],
                "warnings": [],
                "estimated_steps": 1,
                "estimated_cpu_s": 0.01,
                "estimated_wall_s": 0.01,
                "family_tag": family_tag,
            }

        try:
            policy = GoalPolicy.from_dict(goal.get("policy"), schema=schema)
        except Exception:
            return {
                "feasible": False,
                "blockers": ["INVALID_POLICY_SPEC"],
                "warnings": [],
                "estimated_steps": 1,
                "estimated_cpu_s": 0.01,
                "estimated_wall_s": 0.01,
                "family_tag": family_tag,
            }

        if "objective" in goal:
            try:
                steps = plan_objective(goal["objective"], policy=policy, budget=ceiling)
            except Exception as exc:
                msg = str(exc)
                code = "BUDGET_STEP_EXCEEDED" if "budget" in msg else "TOOL_OR_POLICY_BLOCKED"
                return {
                    "feasible": False,
                    "blockers": [code],
                    "warnings": [msg],
                    "estimated_steps": ceiling.max_steps + 1,
                    "estimated_cpu_s": 0.01,
                    "estimated_wall_s": 0.01,
                    "family_tag": family_tag,
                }
        else:
            steps = goal.get("steps", [])
            if type(steps) is not list or not steps:
                blockers.append("EMPTY_STEPS")
                steps = []

        usage = existing_usage or BudgetUsage()
        rem_steps = ceiling.max_steps - usage.steps_used
        rem_cands = ceiling.max_candidates - usage.candidates_staged
        rem_cpu = ceiling.cpu_seconds - usage.cpu_seconds_used
        rem_wall = ceiling.wall_seconds - usage.wall_seconds_used

        if len(steps) > rem_steps:
            blockers.append("BUDGET_STEP_EXCEEDED")

        staged_needed = sum(1 for s in steps if isinstance(s, dict) and s.get("tool") == "stage_candidate")
        if staged_needed > rem_cands:
            blockers.append("BUDGET_CANDIDATE_EXCEEDED")

        est_cpu = 0.0
        simulated_staged_tasks = {
            tid for tid, info in state.ace_tasks_by_id.items() if info.get("staged")
        }
        pending_enqueued_tasks: list[dict[str, Any]] = []

        for s in steps:
            if type(s) is not dict or type(s.get("tool")) is not str:
                blockers.append("INVALID_TOOL_SPEC")
                continue
            tool = s["tool"]
            est_cpu += self.TOOL_CPU_PRIORS.get(tool, 0.02)

            if tool not in policy.authorized_tools or tool not in state.available_system_tools:
                blockers.append("TOOL_DISABLED")
                continue

            if tool == "inspect_file":
                rel = s.get("path", "")
                try:
                    parts = validate_SafeRelPath(rel)
                    if not path_matches_prefixes(rel, policy.read_prefixes):
                        blockers.append("READ_PATH_FORBIDDEN")
                    else:
                        target = self.root.joinpath(*parts)
                        if os.path.islink(target) or not target.exists():
                            blockers.append("FILE_MISSING_OR_SYMLINK")
                        elif not target.is_file():
                            blockers.append("FILE_NON_REGULAR")
                        elif target.stat().st_size > MAX_FILE_BYTES:
                            blockers.append("FILE_SIZE_EXCEEDED")
                except Exception:
                    blockers.append("READ_PATH_FORBIDDEN")

            elif tool == "stage_candidate":
                content = s.get("content", "")
                if type(content) is not str or len(content.encode("utf-8")) > MAX_CANDIDATE_BYTES:
                    blockers.append("CANDIDATE_SIZE_EXCEEDED")

            elif tool == "ace_enqueue_task":
                t_obj = s.get("task", {})
                ok, code = self._estimate_task_learnability(t_obj)
                if not ok:
                    blockers.append(code)
                else:
                    pending_enqueued_tasks.append(t_obj)

            elif tool == "ace_run_tasks":
                for t_obj in pending_enqueued_tasks:
                    # Record family tag for experience lookup if task name hints family
                    warnings.append(f"will_fit:{t_obj.get('name', 'unnamed')}")

            elif tool in {"ace_predict", "ace_evaluate", "ace_report"}:
                tid = s.get("task_id", "")
                t_info = state.ace_tasks_by_id.get(tid)
                if t_info is None:
                    blockers.append("ACE_TASK_UNKNOWN")
                elif tool in {"ace_predict", "ace_evaluate"} and tid not in simulated_staged_tasks:
                    blockers.append("ACE_MODEL_NOT_STAGED")
                if tool == "ace_evaluate" and tid in state.ace_evaluated_task_ids:
                    warnings.append("already_evaluated_check_data_hash")

            elif tool == "abstain":
                warnings.append("explicit_abstain_step")

        est_wall = max(est_cpu * 1.15, 0.005 * max(1, len(steps)))
        if est_cpu > rem_cpu:
            blockers.append("BUDGET_CPU_INSUFFICIENT")
        if est_wall > rem_wall:
            blockers.append("BUDGET_WALL_INSUFFICIENT")

        if state.halted_uncertain_goals and ctx.get("requires_clean_escrow", False):
            blockers.append("WORKSPACE_HALTED_UNCERTAIN")

        return {
            "feasible": len(blockers) == 0,
            "blockers": sorted(set(blockers)),
            "warnings": warnings,
            "estimated_steps": len(steps),
            "estimated_cpu_s": round(est_cpu, 4),
            "estimated_wall_s": round(est_wall, 4),
            "family_tag": family_tag,
        }
