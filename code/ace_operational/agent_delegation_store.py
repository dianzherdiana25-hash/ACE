"""Bounded durable coding-agent supervisor on ACE's existing OperationalStore.

Each call runs AT MOST ONE independently verified work order. It writes an
inflight checkpoint BEFORE starting a potentially non-idempotent worker.
After a crash during delegation, a later call requires manual reconciliation;
it MUST NOT blindly replay Codex or Antigravity actions.

The planner/model does not gain authority over quotas, filesystem mutations,
Git merges or worker permissions. No provider is automatically launched.
"""
from __future__ import annotations

import hashlib
import secrets
from typing import Any

from .agent_fabric import (
    AgentDirector, CLIWorker, Verifier, WorkPlan, WorkerResult,
    validate_work_plan, require_isolated_worktree, canonical,
)
from .store import OperationalStore

CHECKPOINT_KIND = "ace.agent_delegation.task.v1"


def _serialized_plan(plan: WorkPlan) -> dict[str, Any]:
    return {
        "goal": plan.goal, "planner": plan.planner,
        "orders": [
            {
                "id": o.order_id, "worker": o.worker, "mode": o.mode,
                "instruction": o.instruction, "depends_on": list(o.depends_on),
            }
            for o in plan.orders
        ],
    }


class DurableAgentSupervisor:
    """Delegation state is stored as an ACE task checkpoint, not a second DB."""

    def __init__(
        self,
        store: OperationalStore,
        worker: CLIWorker,
        verifier: Verifier | None = None,
    ) -> None:
        self.store = store
        self.worker = worker
        self.verifier = verifier

    def submit(self, plan: WorkPlan) -> dict[str, Any]:
        # Revalidate to ensure direct dataclass construction cannot bypass
        # model-order policy checks.
        valid = validate_work_plan(
            plan.goal, {"orders": _serialized_plan(plan)["orders"]},
            planner=plan.planner,
        )
        cp = {
            "kind": CHECKPOINT_KIND,
            "plan": _serialized_plan(valid),
            "plan_digest": valid.plan_digest,
            "step_index": 0,
            "verified": [],
            "inflight": None,
            "receipt_ids": [],
            "scientific_status": "NOT_ASSESSED",
            "release_gate": "BLOCK_RELEASE",
        }
        return self.store.create_task(
            kind="ace_agent_delegation",
            title_id="ACE multi-agent coding delegation",
            user_request=valid.goal, normalized_goal=valid.goal,
            constraints=[
                "Requires explicit host authorization for worker launch",
                "Workspace must be an isolated Git linked worktree",
                "No merge, deploy, purchases, or frozen evidence changes",
            ],
            checkpoint=cp,
        )

    def read(self, task_id: str) -> tuple[dict[str, Any], WorkPlan]:
        task = self.store.get_task(task_id)
        if task is None or task["kind"] != "ace_agent_delegation":
            raise ValueError("not an ACE coding-delegation task")
        cp = task["checkpoint"]
        if cp.get("kind") != CHECKPOINT_KIND:
            raise ValueError("unknown or corrupt delegation checkpoint")
        raw = cp.get("plan")
        if not isinstance(raw, dict):
            raise ValueError("missing checkpoint plan")
        plan = validate_work_plan(
            raw.get("goal"), {"orders": raw.get("orders")},
            planner=raw.get("planner"),
        )
        if cp.get("plan_digest") != plan.plan_digest:
            raise ValueError("delegation checkpoint plan was modified")
        step_index = cp.get("step_index")
        verified = cp.get("verified")
        if (type(step_index) is not int or not 0 <= step_index <= len(plan.orders)
                or not isinstance(verified, list)
                or verified != [o.order_id for o in plan.orders[:step_index]]
                or cp.get("inflight") is not None and
                not isinstance(cp.get("inflight"), dict)):
            raise ValueError("delegation checkpoint progress invalid")
        return task, plan

    def advance(
        self,
        task_id: str,
        workspace: str,
        *,
        authorized: bool = False,
        allow_write: bool = False,
    ) -> dict[str, Any]:
        task, plan = self.read(task_id)
        if task["status"] == "COMPLETED":
            return task
        cp = task["checkpoint"]
        if cp.get("inflight") is not None:
            # The worker might have modified files before a crash. Never
            # replay without a separate human/host reconciliation procedure.
            return {"task_id": task_id, "status": "RECONCILIATION_REQUIRED",
                    "inflight": cp["inflight"]}
        if task["status"] in ("FAILED_WITH_RECOVERY_STATE", "CANCELLED"):
            return {"task_id": task_id, "status": "REVIEW_REQUIRED"}
        if not authorized:
            return {"task_id": task_id, "status": "NOT_AUTHORIZED"}
        if self.verifier is None:
            return {"task_id": task_id, "status": "NO_HOST_VERIFIER"}
        idx = cp["step_index"]
        if idx == len(plan.orders):
            return {"task_id": task_id, "status": "RECONCILIATION_REQUIRED"}
        order = plan.orders[idx]
        # Separate authorization is required for any change to workspace.
        if order.mode == "workspace-write" and not allow_write:
            return {"task_id": task_id, "status": "WRITE_NOT_AUTHORIZED"}
        if not set(order.depends_on).issubset(cp["verified"]):
            return {"task_id": task_id, "status": "DEPENDENCY_NOT_VERIFIED"}
        root = require_isolated_worktree(workspace)

        lease = self.store.fenced.acquire(
            "ace-agent:" + task_id, "ace-agent-" + secrets.token_hex(5),
            ttl=3600.0,
        )
        try:
            # Recheck while holding fenced lease; one process at a time.
            task, plan = self.read(task_id)
            cp = task["checkpoint"]
            if cp.get("inflight") is not None or cp.get("step_index") != idx:
                return {"task_id": task_id, "status": "RECONCILIATION_REQUIRED"}
            self.store.update_task(
                task_id, status="ACTIVE", lease_epoch=lease.epoch,
                checkpoint={"inflight": {"order_id": order.order_id,
                                         "step_index": idx}},
                next_action="run_delegated_agent_and_verify",
            )
            try:
                outcome = self.worker.run(order, root)
                verified = bool(outcome.success and self.verifier(
                    order, root, outcome
                ))
                note = "host_verification_passed" if verified else "host_verification_failed"
            except Exception as exc:
                # A failed launch could have caused partial filesystem edits.
                # Mark unresolved until an operator reconciles the worktree.
                note = f"{type(exc).__name__}: {exc}"[:250]
                self.store.update_task(
                    task_id, status="FAILED_WITH_RECOVERY_STATE",
                    error_summary=note, next_action="reconcile_worktree_before_retry",
                )
                return {"task_id": task_id, "status": "FAILED_WITH_RECOVERY_STATE",
                        "reason": note}

            raw = {
                "step_id": order.order_id,
                "worker": order.worker,
                "protocol_success": outcome.success,
                "host_verified": verified,
                "stdout_digest": outcome.stdout_digest,
                "stderr_digest": outcome.stderr_digest,
                "plan_digest": plan.plan_digest,
            }
            # FencedStore checks active lease. If this write succeeds but the
            # operational checkpoint fails, replay MUST require reconciliation.
            self.store.fenced.append_receipt(lease, f"order-{idx}", raw)
            receipt = self.store.record_receipt(
                task_id=task_id, action_kind="ace_coding_worker",
                input_data=order.instruction,
                output_data=outcome.response,
                command_or_operation=order.worker,
                exit_code=outcome.exit_code,
                stdout_text=outcome.stdout_digest,
                stderr_text=outcome.stderr_digest,
                verified_by="host-verifier:same-process",
                passed=verified,
            )
            updated_verified = cp["verified"] + ([order.order_id] if verified else [])
            updated_receipts = cp["receipt_ids"] + [receipt["receipt_id"]]
            self.store.update_task(
                task_id, status="ACTIVE" if verified else "FAILED_WITH_RECOVERY_STATE",
                checkpoint={
                    "step_index": idx + (1 if verified else 0),
                    "verified": updated_verified,
                    "receipt_ids": updated_receipts,
                    "inflight": None if verified else {
                        "order_id": order.order_id, "step_index": idx,
                        "reason": "verification rejected",
                    },
                },
                error_summary="" if verified else note,
                next_action="verify_next_worker_step" if verified
                else "reconcile_worktree_before_retry",
                lease_epoch=lease.epoch,
            )
            if not verified:
                return {"task_id": task_id, "status": "FAILED_WITH_RECOVERY_STATE",
                        "reason": note}
            if idx + 1 == len(plan.orders):
                self.store.update_task(task_id, status="VERIFYING",
                                       lease_epoch=lease.epoch)
                return self.store.update_task(
                    task_id, status="COMPLETED", lease_epoch=lease.epoch,
                    verification_summary={
                        "delegation_local_verification": True,
                        "scientific_status": "NOT_ASSESSED",
                        "independent_sandbox_verification": False,
                        "release_gate": "BLOCK_RELEASE",
                        "receipt_ids": updated_receipts,
                    },
                    next_action="review_before_merge",
                )
            return self.store.get_task(task_id)
        finally:
            try:
                self.store.fenced.release(lease)
            except Exception:
                # Expiry/crash safety is handled by the inflight checkpoint.
                pass
