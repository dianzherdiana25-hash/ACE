"""OW-1A: local, evidence-gated execution over ACE's existing durable store.

Only operator-registered *trusted in-process pure functions* are supported.
No sandbox, external API, model-generated code, remote worker or automatic
promotion is provided. Planning, tool execution and verification remain
separate and failures are recorded without fabricating success.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import secrets
from typing import Any, Callable, Mapping

from .open_world_planner import Capability, CapabilityRegistry, plan_capabilities
from .store import OperationalStore

MAX_JSON_BYTES = 262_144
CHECKPOINT_KIND = "ace.open_world.local.v1"


def _canonical(value: Any) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"), allow_nan=False)
    if len(serialized.encode("utf-8")) > MAX_JSON_BYTES:
        raise ValueError("artifact exceeds bounded JSON size")
    return serialized


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LocalAdapter:
    """An explicit trusted callable plus separate, trusted verification hook.

    Both callbacks run in the same process: this is NOT sandbox isolation or
    independent scientific evaluation. They must be provisioned by the host,
    never loaded dynamically from untrusted task or LLM output.
    """

    provider: str
    execute: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    verify: Callable[[Mapping[str, Any], Mapping[str, Any]], bool]
    verifier_id: str = "local-verification"

    def __post_init__(self) -> None:
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise ValueError("provider required")
        if not callable(self.execute) or not callable(self.verify):
            raise TypeError("execute and verify must be callable")
        if self.execute is self.verify:
            raise ValueError("execution cannot be its own verifier")
        if not isinstance(self.verifier_id, str) or not self.verifier_id.strip():
            raise ValueError("verifier_id required")


def _manifest_hash(registry: CapabilityRegistry) -> str:
    contracts = [
        {
            "capability_id": c.capability_id,
            "consumes": sorted(c.consumes),
            "produces": sorted(c.produces),
            "provider": c.provider,
            "evidence_ref": c.evidence_ref,
            "status": c.status,
            "effect": c.effect,
            "cost_units": c.cost_units,
        }
        for c in registry.list_all()
    ]
    return _digest(contracts)


class OpenWorldLocalExecutor:
    """Execute a bounded typed plan with persistent ACE task/checkpoint/receipts.

    It uses FencedStore for task admission and its own idempotency receipts;
    OperationalStore task checkpoints are a DIFFERENT SQLite transaction.
    There is no cross-database atomic commit. The local demo is retryable
    only because adapters must be pure and deterministic.
    """

    def __init__(
        self,
        store: OperationalStore,
        registry: CapabilityRegistry,
        adapters: Mapping[str, LocalAdapter],
    ):
        self.store = store
        self.registry = registry
        self.adapters = dict(adapters)

    def _eligible_registry(self) -> CapabilityRegistry:
        frontier = {c["capability_id"]: c for c in self.store.list_frontier()}
        eligible = CapabilityRegistry()
        for cap in self.registry.list_all():
            saved = frontier.get(cap.capability_id)
            trusted = bool(
                cap.status == "VERIFIED"
                and cap.evidence_ref.strip()
                and saved is not None
                and saved["status"] == "KNOWN_AND_TESTED"
                and saved["evidence_ref"] == cap.evidence_ref
            )
            eligible.register(cap if trusted else replace(cap, status="UNVERIFIED"))
        return eligible

    def submit(
        self, *,
        request: str,
        available_values: Mapping[str, Any],
        goal_types: set[str] | frozenset[str],
        max_steps: int = 12,
        max_expansions: int = 1000,
        max_cost_units: int = 100,
    ) -> dict[str, Any]:
        if not request.strip():
            raise ValueError("request required")
        if not isinstance(available_values, Mapping):
            raise TypeError("available_values must be a mapping")
        values = dict(available_values)
        goals = sorted(goal_types)
        _canonical(values)
        if not goals:
            raise ValueError("goal_types required")
        # Explicit budget limits are persisted, so restart does not silently
        # expand the previous research or compute authority.
        bounds = dict(max_steps=max_steps, max_expansions=max_expansions,
                      max_cost_units=max_cost_units)
        checkpoint = {
            "kind": CHECKPOINT_KIND,
            "manifest_digest": _manifest_hash(self.registry),
            "available_values": values,
            "goal_types": goals,
            "bounds": bounds,
            "next_index": 0,
            "plan_ids": [],
            "receipts": [],
        }
        task = self.store.create_task(
            kind="open_world_local",
            title_id="Open-world typed local execution",
            user_request=request,
            normalized_goal=request,
            acceptance_criteria=[f"Output type tersedia: {g}" for g in goals],
            checkpoint=checkpoint,
        )
        return task

    def run(self, task_id: str) -> dict[str, Any]:
        task = self.store.get_task(task_id)
        if task is None or task["kind"] != "open_world_local":
            raise ValueError("not an open-world local task")
        if task["status"] == "COMPLETED":
            return task
        cp = task["checkpoint"]
        if cp.get("kind") != CHECKPOINT_KIND:
            raise ValueError("unknown or missing task checkpoint")
        if cp.get("manifest_digest") != _manifest_hash(self.registry):
            raise ValueError("manifest changed since task submission; explicit replan required")

        job_id = "open-world:" + task_id
        # Fenced admission prevents two active writers to the same task.
        lease = self.store.fenced.acquire(job_id, "ow-local-" + secrets.token_hex(5),
                                          ttl=120.0)
        try:
            return self._run_under_lease(task_id, lease, cp)
        finally:
            # Do not suppress errors from the actual execution; leases naturally
            # expire after process death. This caller may no longer own the lease.
            try:
                self.store.fenced.release(lease)
            except Exception:
                pass

    def _run_under_lease(self, task_id: str, lease: Any, checkpoint: dict[str, Any]) -> dict[str, Any]:
        cp = dict(checkpoint)
        values = dict(cp["available_values"])
        goals = frozenset(cp["goal_types"])
        bounds = cp["bounds"]
        result = plan_capabilities(
            self._eligible_registry(),
            available_types=set(values), goal_types=goals,
            allowed_effects=("none",),
            **bounds,
        )
        if result.status != "READY":
            return self.store.update_task(
                task_id, status="WAITING_FOR_DEPENDENCY",
                checkpoint={"plan_status": result.status,
                            "missing_types": sorted(result.missing_types)},
                next_action="supply_verified_capability_and_replan",
                error_summary="No verified pure local capability chain within budget",
            )

        ids = list(result.capability_ids)
        previous = cp.get("plan_ids", [])
        if previous and previous != ids:
            raise ValueError("verified capability graph changed; explicit replan required")
        cp["plan_ids"] = ids
        next_index = int(cp.get("next_index", 0))
        if next_index < 0 or next_index > len(ids):
            raise ValueError("corrupt checkpoint next_index")
        capabilities = {c.capability_id: c for c in self.registry.list_all()}

        # Preflight all capabilities prior to invoking even the first adapter.
        for cid in ids:
            cap = capabilities[cid]
            adapter = self.adapters.get(cid)
            if (adapter is None or adapter.provider != cap.provider or
                    cap.effect != "none"):
                return self.store.update_task(
                    task_id, status="WAITING_FOR_DEPENDENCY",
                    checkpoint={"plan_ids": ids, "plan_status": "MISSING_TRUSTED_ADAPTER"},
                    next_action="supply_trusted_local_adapter",
                    error_summary=f"no trusted pure local adapter for {cid}",
                )

        self.store.update_task(task_id, status="ACTIVE",
                               checkpoint={"plan_ids": ids, "plan_status": "READY"},
                               next_action="execute_verified_local_step")
        for index in range(next_index, len(ids)):
            cap = capabilities[ids[index]]
            adapter = self.adapters[cap.capability_id]
            current_inputs = {k: values[k] for k in sorted(cap.consumes)}
            input_digest = _digest(current_inputs)
            try:
                result_values = adapter.execute(dict(current_inputs))
                if not isinstance(result_values, Mapping):
                    raise ValueError("adapter output must be a mapping")
                outputs = dict(result_values)
                if set(outputs) != cap.produces:
                    raise ValueError("adapter output types do not match declared contract")
                output_digest = _digest(outputs)
                if adapter.verify(dict(current_inputs), dict(outputs)) is not True:
                    raise ValueError("local verification rejected adapter output")
                # Receipt is committed to FencedStore first. An interruption
                # between this and the operational checkpoint is conservatively
                # detected on replay rather than silently declaring success.
                self.store.fenced.append_receipt(
                    lease, f"step-{index}",
                    {"capability_id": cap.capability_id,
                     "input_digest": input_digest,
                     "output_digest": output_digest,
                     "verifier_id": adapter.verifier_id},
                )
                rcpt = self.store.record_receipt(
                    task_id=task_id,
                    action_kind="open_world_local_step",
                    input_data=_canonical(current_inputs),
                    output_data=_canonical(outputs),
                    command_or_operation=cap.capability_id,
                    exit_code=0,
                    verified_by=adapter.verifier_id + ":same-process",
                    passed=True,
                )
                values.update(outputs)
                cp["available_values"] = values
                cp["next_index"] = index + 1
                cp["plan_ids"] = ids
                cp.setdefault("receipts", []).append(rcpt["receipt_id"])
                self.store.update_task(task_id,
                                       checkpoint=cp,
                                       next_action="execute_next_local_step")
            except Exception as exc:
                # Error text is bounded. No fabricated completion or silent
                # fallback to a different capability is permitted.
                return self.store.update_task(
                    task_id, status="FAILED_WITH_RECOVERY_STATE",
                    error_summary=(f"{type(exc).__name__}: {exc}")[:300],
                    checkpoint={"failed_step": index, "failed_capability": cap.capability_id},
                    next_action="review_failure_then_resume",
                )

        missing = goals - set(values)
        if missing:
            return self.store.update_task(
                task_id, status="FAILED_WITH_RECOVERY_STATE",
                error_summary=f"goal outputs missing: {sorted(missing)}",
                next_action="review_missing_goal",
            )
        self.store.update_task(task_id, status="VERIFYING",
                               checkpoint={"next_index": len(ids)})
        return self.store.update_task(
            task_id, status="COMPLETED",
            verification_summary={
                "goal_types_satisfied": sorted(goals),
                "local_verification": True,
                "independent_sandbox_verification": False,
                "execution_kind": "trusted_pure_in_process",
                "receipts": list(cp.get("receipts", [])),
            },
            checkpoint={"available_values": values,
                        "completed": True,
                        "next_index": len(ids)},
            next_action="none",
        )
