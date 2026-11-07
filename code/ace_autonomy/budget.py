"""Real wall-clock, process/child CPU, step, candidate, and retry BudgetController."""
from __future__ import annotations

from dataclasses import dataclass
import resource
import time
from typing import Any

from .errors import BudgetExhaustedError
from .policy import BudgetCeiling


def total_process_cpu_seconds() -> float:
    """Measured user + system CPU seconds across current process and waited children."""
    self_r = resource.getrusage(resource.RUSAGE_SELF)
    child_r = resource.getrusage(resource.RUSAGE_CHILDREN)
    return float(self_r.ru_utime + self_r.ru_stime + child_r.ru_utime + child_r.ru_stime)


@dataclass
class BudgetUsage:
    steps_used: int = 0
    candidates_staged: int = 0
    wall_seconds_used: float = 0.0
    cpu_seconds_used: float = 0.0
    retries_by_step: dict[str, int] | None = None

    def __post_init__(self) -> None:
        if self.retries_by_step is None:
            self.retries_by_step = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps_used": int(self.steps_used),
            "candidates_staged": int(self.candidates_staged),
            "wall_seconds_used": round(float(self.wall_seconds_used), 6),
            "cpu_seconds_used": round(float(self.cpu_seconds_used), 6),
            "retries_by_step": {str(k): int(v) for k, v in (self.retries_by_step or {}).items()},
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> BudgetUsage:
        if not raw:
            return cls()
        return cls(
            steps_used=int(raw.get("steps_used", 0)),
            candidates_staged=int(raw.get("candidates_staged", 0)),
            wall_seconds_used=float(raw.get("wall_seconds_used", 0.0)),
            cpu_seconds_used=float(raw.get("cpu_seconds_used", 0.0)),
            retries_by_step={str(k): int(v) for k, v in raw.get("retries_by_step", {}).items()},
        )


class BudgetController:
    """Enforces declared step, candidate, retry, wall-time, and CPU-time ceilings."""

    def __init__(self, ceiling: BudgetCeiling, usage: BudgetUsage | None = None):
        self.ceiling = ceiling
        self.usage = usage or BudgetUsage()

    def check_pre_step(self, step_index: int, action: dict[str, Any]) -> None:
        if self.usage.steps_used >= self.ceiling.max_steps:
            raise BudgetExhaustedError(
                f"step budget exhausted ({self.usage.steps_used}/{self.ceiling.max_steps})"
            )
        if action.get("tool") == "stage_candidate" and self.usage.candidates_staged >= self.ceiling.max_candidates:
            raise BudgetExhaustedError(
                f"candidate budget exhausted ({self.usage.candidates_staged}/{self.ceiling.max_candidates})"
            )
        if self.usage.wall_seconds_used >= self.ceiling.wall_seconds:
            raise BudgetExhaustedError(
                f"wall budget exhausted ({self.usage.wall_seconds_used:.4f}s/{self.ceiling.wall_seconds:.4f}s)"
            )
        if self.usage.cpu_seconds_used >= self.ceiling.cpu_seconds:
            raise BudgetExhaustedError(
                f"cpu budget exhausted ({self.usage.cpu_seconds_used:.4f}s/{self.ceiling.cpu_seconds:.4f}s)"
            )

    def remaining_wall_seconds(self) -> float:
        return max(0.001, self.ceiling.wall_seconds - self.usage.wall_seconds_used)

    def remaining_cpu_seconds(self) -> float:
        return max(0.001, self.ceiling.cpu_seconds - self.usage.cpu_seconds_used)

    def can_retry_local_step(self, step_index: int, *, is_external: bool) -> bool:
        if is_external:
            return False
        used = int((self.usage.retries_by_step or {}).get(str(step_index), 0))
        return used < self.ceiling.max_retries_per_step

    def record_retry(self, step_index: int) -> None:
        assert self.usage.retries_by_step is not None
        key = str(step_index)
        self.usage.retries_by_step[key] = int(self.usage.retries_by_step.get(key, 0)) + 1

    def begin_measurement(self) -> tuple[float, float]:
        return time.monotonic(), total_process_cpu_seconds()

    def finish_measurement(
        self,
        start_tokens: tuple[float, float],
        *,
        step_completed: bool,
        staged_candidate: bool = False,
    ) -> None:
        wall_start, cpu_start = start_tokens
        wall_delta = max(0.0, time.monotonic() - wall_start)
        cpu_delta = max(0.0, total_process_cpu_seconds() - cpu_start)
        self.usage.wall_seconds_used += wall_delta
        self.usage.cpu_seconds_used += cpu_delta
        if step_completed:
            self.usage.steps_used += 1
        if staged_candidate:
            self.usage.candidates_staged += 1

        if self.usage.wall_seconds_used > self.ceiling.wall_seconds:
            raise BudgetExhaustedError(
                f"wall budget exceeded ({self.usage.wall_seconds_used:.4f}s > {self.ceiling.wall_seconds:.4f}s)"
            )
        if self.usage.cpu_seconds_used > self.ceiling.cpu_seconds:
            raise BudgetExhaustedError(
                f"cpu budget exceeded ({self.usage.cpu_seconds_used:.4f}s > {self.ceiling.cpu_seconds:.4f}s)"
            )
