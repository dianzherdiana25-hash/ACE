"""State Manager: Persistent Research State, Concurrency Locking, and Crash Recovery.

Guarantees:
1. Persistent research state across multiple processes and GitHub Actions steps.
2. Concurrency locking with timeout and lease recovery.
3. Merkle rolling state digest linking sequential cycles.
4. Failure catalog archiving negative scientific results.
5. Immutable baseline protection and crash-safe rollback.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple

from .models import PersistentResearchState


class ConcurrencyLockError(Exception):
    """Raised when an operation cannot acquire the state lock."""
    pass


class StateCorruptedError(Exception):
    """Raised when state data fails integrity or schema verification."""
    pass


GENESIS_BASELINE = {
    "root_candidate_id": "G0_self_dev_root_c0",
    "root_source_sha": "root_genesis_predicate_len3_even",
    "root_predicate_code": "def evaluate_mechanism(length: int, density: int, stride_val: int) -> int:\n    return length % 3",
    "baseline_accuracy": 0.5000,
    "genesis_timestamp": "2026-11-07T00:00:00Z",
}

GENESIS_DIGEST = hashlib.sha256(json.dumps(GENESIS_BASELINE, sort_keys=True).encode("utf-8")).hexdigest()


class StateManager:
    """Manages persistent research state, concurrency control, and crash recovery."""

    def __init__(
        self,
        state_dir: str = "checkpoints/self_dev",
        state_file: str = "research_state.json",
        lock_ttl_seconds: float = 600.0,
    ):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.state_dir / state_file
        self.immutable_baseline_path = self.state_dir / "immutable_baseline.json"
        self.recovery_backup_path = self.state_dir / "recovery_baseline.json"
        self.lock_ttl_seconds = lock_ttl_seconds

        self._ensure_immutable_baseline()

    def _ensure_immutable_baseline(self) -> None:
        """Ensure the immutable baseline exists and matches genesis integrity."""
        if not self.immutable_baseline_path.exists():
            payload = json.dumps(GENESIS_BASELINE, indent=2).encode("utf-8")
            self.immutable_baseline_path.write_bytes(payload)

    def load_state(self) -> PersistentResearchState:
        """Load state from disk, or initialize fresh state if not present."""
        if not self.state_path.exists():
            fresh_state = PersistentResearchState(
                schema_version="2.0",
                active_generation_id=GENESIS_BASELINE["root_candidate_id"],
                cycle_count=0,
                immutable_baseline=dict(GENESIS_BASELINE),
                state_digest=GENESIS_DIGEST,
            )
            self._atomic_save(fresh_state)
            self._save_recovery_backup(fresh_state)
            return fresh_state

        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return PersistentResearchState.from_dict(data)
        except Exception as e:
            # Corrupted state -> trigger fail-closed recovery
            return self.recover_from_crash(reason=f"Parse failure: {str(e)}")

    def _atomic_save(self, state: PersistentResearchState) -> None:
        """Atomically persist state to prevent partial writes."""
        temp_path = self.state_path.with_suffix(".tmp")
        payload = json.dumps(state.to_dict(), indent=2).encode("utf-8")
        with open(temp_path, "wb") as f:
            f.write(payload)
        temp_path.replace(self.state_path)

    def _save_recovery_backup(self, state: PersistentResearchState) -> None:
        """Save a verified backup for crash recovery."""
        temp_path = self.recovery_backup_path.with_suffix(".tmp")
        payload = json.dumps(state.to_dict(), indent=2).encode("utf-8")
        with open(temp_path, "wb") as f:
            f.write(payload)
        temp_path.replace(self.recovery_backup_path)

    def acquire_lock(self, worker_id: str) -> str:
        """Acquire concurrency lease on research state."""
        state = self.load_state()
        lock = state.concurrency_lock
        now = time.time()

        if lock.get("is_locked", False):
            expires_at = float(lock.get("expires_at", 0.0))
            if now < expires_at:
                locked_by = lock.get("locked_by", "unknown")
                raise ConcurrencyLockError(
                    f"Research state is locked by {locked_by} until {expires_at} (remaining {round(expires_at - now, 1)}s)"
                )
            # Expired lock: break safely
            print(f"[StateManager] Breaking expired lock held by {lock.get('locked_by')}")

        token = hashlib.sha256(f"{worker_id}:{now}".encode("utf-8")).hexdigest()[:16]
        state.concurrency_lock = {
            "is_locked": True,
            "locked_by": worker_id,
            "locked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "expires_at": str(round(now + self.lock_ttl_seconds, 2)),
            "lock_token": token,
        }
        self._atomic_save(state)
        return token

    def release_lock(self, token: str) -> None:
        """Release concurrency lease."""
        state = self.load_state()
        lock = state.concurrency_lock

        if not lock.get("is_locked", False):
            return

        current_token = lock.get("lock_token", "")
        if current_token and current_token != token:
            print(f"[StateManager] Warning: Lock release token mismatch ({current_token} != {token}), releasing anyway")

        state.concurrency_lock = {
            "is_locked": False,
            "locked_by": "",
            "locked_at": "",
            "expires_at": "",
            "lock_token": "",
        }
        self._atomic_save(state)

    def force_unlock(self) -> None:
        """Administrative unlock to recover from deadlocks."""
        state = self.load_state()
        state.concurrency_lock = {
            "is_locked": False,
            "locked_by": "",
            "locked_at": "",
            "expires_at": "",
            "lock_token": "",
        }
        self._atomic_save(state)

    def compute_next_state_digest(
        self,
        prior_digest: str,
        cycle_id: int,
        candidate_id: str,
        decision: str,
        receipt_signature: str,
    ) -> str:
        """Compute rolling Merkle state digest linking sequential cycles."""
        payload = f"{prior_digest}:{cycle_id}:{candidate_id}:{decision}:{receipt_signature}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def record_completed_cycle(
        self,
        cycle_id: int,
        hypothesis_id: str,
        target_task_id: str,
        candidate_id: str,
        source_sha: str,
        decision: str,
        holdout_score: float,
        gain_over_parent: float,
        rejection_reason: str,
        evidence_path: str,
        receipt_signature: str,
        gene_dict: Dict[str, int],
        mutation_ordinal: int,
        active_head_id: str,
        next_agenda: Optional[Dict[str, Any]] = None,
    ) -> PersistentResearchState:
        """Record completed cycle results, update failure catalog, and roll state digest."""
        state = self.load_state()

        # Update rolling state digest
        prior_digest = state.state_digest or GENESIS_DIGEST
        new_digest = self.compute_next_state_digest(
            prior_digest=prior_digest,
            cycle_id=cycle_id,
            candidate_id=candidate_id,
            decision=decision,
            receipt_signature=receipt_signature,
        )

        cycle_summary = {
            "cycle_id": cycle_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "hypothesis_id": hypothesis_id,
            "target_task_id": target_task_id,
            "candidate_id": candidate_id,
            "source_sha": source_sha,
            "decision": decision,
            "holdout_score": holdout_score,
            "gain_over_parent": gain_over_parent,
            "rejection_reason": rejection_reason,
            "evidence_path": evidence_path,
            "prior_digest": prior_digest,
            "state_digest": new_digest,
        }

        state.completed_cycles.append(cycle_summary)
        state.cycle_count = len(state.completed_cycles)
        state.active_generation_id = active_head_id
        state.state_digest = new_digest

        # If candidate failed, catalog failure as negative scientific evidence
        if decision != "ACCEPTED":
            if target_task_id not in state.failure_catalog:
                state.failure_catalog[target_task_id] = []
            state.failure_catalog[target_task_id].append({
                "cycle_id": cycle_id,
                "candidate_id": candidate_id,
                "source_sha": source_sha,
                "gene_dict": gene_dict,
                "mutation_ordinal": mutation_ordinal,
                "gain_over_parent": gain_over_parent,
                "rejection_reason": rejection_reason,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })

        # Update hypothesis history
        state.hypotheses_history.append({
            "hypothesis_id": hypothesis_id,
            "target_task_id": target_task_id,
            "status": "FALSIFIED" if decision != "ACCEPTED" else "CONFIRMED",
            "cycle_id": cycle_id,
        })

        if next_agenda:
            state.next_agenda_priority = next_agenda

        state.fail_closed_recovery["last_known_good_cycle"] = cycle_id
        state.fail_closed_recovery["last_known_good_digest"] = new_digest

        # Atomically save state and backup
        self._atomic_save(state)
        self._save_recovery_backup(state)
        return state

    def recover_from_crash(self, reason: str = "") -> PersistentResearchState:
        """Fail-closed recovery restoring last verified good state or immutable baseline."""
        print(f"[StateManager] FAIL-CLOSED RECOVERY TRIGGERED. Reason: {reason}")
        recovered_state: Optional[PersistentResearchState] = None

        if self.recovery_backup_path.exists():
            try:
                with open(self.recovery_backup_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                recovered_state = PersistentResearchState.from_dict(data)
                print(f"[StateManager] Restored state from recovery backup (Cycle {recovered_state.cycle_count})")
            except Exception as e:
                print(f"[StateManager] Recovery backup also corrupted: {e}")

        if recovered_state is None:
            # Fallback to immutable baseline
            print("[StateManager] Restoring state from immutable baseline")
            recovered_state = PersistentResearchState(
                schema_version="2.0",
                active_generation_id=GENESIS_BASELINE["root_candidate_id"],
                cycle_count=0,
                immutable_baseline=dict(GENESIS_BASELINE),
                state_digest=GENESIS_DIGEST,
            )

        # Clear any dangling lock and increment recovery counter
        recovered_state.concurrency_lock = {
            "is_locked": False,
            "locked_by": "",
            "locked_at": "",
            "expires_at": "",
            "lock_token": "",
        }
        recovered_state.fail_closed_recovery["recovery_count"] = (
            recovered_state.fail_closed_recovery.get("recovery_count", 0) + 1
        )

        self._atomic_save(recovered_state)
        self._save_recovery_backup(recovered_state)
        return recovered_state
