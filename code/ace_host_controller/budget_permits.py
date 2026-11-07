"""Budget and capability permission governance for ACE Host Controller.

Enforces resource limits (time, queries, candidate counts, memory) and
capability permits (network, shell execution, filesystem mutations).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import time
from typing import Any, Optional


class BudgetExceededError(RuntimeError):
    """Raised when an allocated compute or query budget is exhausted."""


class PermitDeniedError(PermissionError):
    """Raised when an unauthorized capability or operation is requested."""


@dataclass
class ExecutionBudget:
    """Execution budget enforced by the Host Controller."""

    max_execution_seconds: float = 300.0
    max_queries: int = 1000
    max_candidates: int = 50
    max_memory_mb: float = 1024.0
    used_seconds: float = 0.0
    used_queries: int = 0
    candidates_evaluated: int = 0
    _start_wall_time: Optional[float] = field(default=None, repr=False)

    def start_timer(self) -> None:
        """Start tracking wall-clock time."""
        if self._start_wall_time is None:
            self._start_wall_time = time.monotonic()

    def sync_wall_clock(self) -> None:
        """Sync elapsed wall-clock time against budget."""
        if self._start_wall_time is not None:
            now = time.monotonic()
            elapsed = now - self._start_wall_time
            self._start_wall_time = now
            self.consume_time(elapsed)

    def consume_time(self, seconds: float) -> None:
        """Record consumed execution seconds."""
        if seconds < 0:
            raise ValueError("Consumed time cannot be negative")
        self.used_seconds += seconds
        if self.used_seconds > self.max_execution_seconds:
            raise BudgetExceededError(
                f"Execution time budget exceeded: {self.used_seconds:.2f}s > {self.max_execution_seconds:.2f}s"
            )

    def consume_queries(self, count: int = 1) -> None:
        """Record consumed epistemic or evaluation queries."""
        if count < 0:
            raise ValueError("Query count cannot be negative")
        self.used_queries += count
        if self.used_queries > self.max_queries:
            raise BudgetExceededError(
                f"Query budget exceeded: {self.used_queries} > {self.max_queries}"
            )

    def record_candidate_eval(self) -> None:
        """Increment count of evaluated candidates."""
        self.candidates_evaluated += 1
        if self.candidates_evaluated > self.max_candidates:
            raise BudgetExceededError(
                f"Candidate evaluation limit exceeded: {self.candidates_evaluated} > {self.max_candidates}"
            )

    @property
    def remaining_seconds(self) -> float:
        """Seconds remaining in execution budget."""
        return max(0.0, self.max_execution_seconds - self.used_seconds)

    @property
    def remaining_queries(self) -> int:
        """Queries remaining in epistemic query budget."""
        return max(0, self.max_queries - self.used_queries)

    def to_dict(self) -> dict[str, Any]:
        """Serialize budget state to dictionary."""
        return {
            "max_execution_seconds": self.max_execution_seconds,
            "max_queries": self.max_queries,
            "max_candidates": self.max_candidates,
            "max_memory_mb": self.max_memory_mb,
            "used_seconds": round(self.used_seconds, 4),
            "used_queries": self.used_queries,
            "candidates_evaluated": self.candidates_evaluated,
            "remaining_seconds": round(self.remaining_seconds, 4),
            "remaining_queries": self.remaining_queries,
        }


@dataclass(frozen=True)
class CapabilityPermit:
    """Explicit capability authorization granted to a research candidate or process."""

    allowed_capabilities: frozenset[str] = frozenset({"hypothesis_eval", "ast_inspect"})
    allow_network: bool = False
    allow_filesystem_write: bool = False
    allow_shell_exec: bool = False
    max_ast_nodes: int = 5000

    def verify_capability(self, capability: str) -> None:
        """Verify that a named capability is granted."""
        if capability not in self.allowed_capabilities:
            raise PermitDeniedError(
                f"Capability '{capability}' is not granted by permit. Allowed: {sorted(self.allowed_capabilities)}"
            )

    def verify_operation(self, op: str) -> None:
        """Verify safety properties of an operation."""
        if op == "network" and not self.allow_network:
            raise PermitDeniedError("Network access strictly denied by Host Controller permit")
        if op == "fs_write" and not self.allow_filesystem_write:
            raise PermitDeniedError("Direct filesystem mutation strictly denied by Host Controller permit")
        if op == "shell_exec" and not self.allow_shell_exec:
            raise PermitDeniedError("Direct shell/subprocess execution strictly denied by Host Controller permit")

    def to_dict(self) -> dict[str, Any]:
        """Serialize permit to dictionary."""
        return {
            "allowed_capabilities": sorted(self.allowed_capabilities),
            "allow_network": self.allow_network,
            "allow_filesystem_write": self.allow_filesystem_write,
            "allow_shell_exec": self.allow_shell_exec,
            "max_ast_nodes": self.max_ast_nodes,
        }
