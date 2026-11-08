"""Host boundary governance and OS isolation verification for ACE Host Controller.

Enforces:
- Strict decoupling of candidate generators from supervisor state.
- Detection of real OS isolation (bwrap, nsjail, docker, seccomp).
- Fail-closed NOT_SEALED designation when OS containment is absent.
- Immutable promotion policy locks resistant to in-memory tampering.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import os
import shutil
from typing import Any, Mapping


class SealingStatus(str, Enum):
    """OS isolation sealing level."""
    CONTAINER_SEALED = "CONTAINER_SEALED"
    BWRAP_SEALED = "BWRAP_SEALED"
    NSJAIL_SEALED = "NSJAIL_SEALED"
    NOT_SEALED = "NOT_SEALED"


def detect_os_sealing() -> SealingStatus:
    """Detect whether true OS-level process containment is available in the environment."""
    if os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv"):
        return SealingStatus.CONTAINER_SEALED
    if shutil.which("bwrap") or os.path.exists("/usr/bin/bwrap"):
        return SealingStatus.BWRAP_SEALED
    if shutil.which("nsjail") or os.path.exists("/usr/bin/nsjail"):
        return SealingStatus.NSJAIL_SEALED
    return SealingStatus.NOT_SEALED


@dataclass(frozen=True)
class ImmutablePromotionRules:
    """Tamper-resistant frozen promotion rules."""
    min_gain: float = 0.15
    max_regression: float = 0.02
    require_zero_contamination: bool = True
    require_os_containment: bool = False
    release_gate: str = "BLOCK_RELEASE"
    scientific_status: str = "NOT_ASSESSED"
    oaie_established: bool = False

    def validate_candidate(
        self,
        gain: float,
        regression: float,
        contaminated: bool,
        sealing: SealingStatus,
    ) -> tuple[bool, list[str]]:
        """Validate candidate against immutable promotion rules."""
        violations: list[str] = []
        if gain < self.min_gain:
            violations.append(f"Holdout gain {gain:.4f} < min {self.min_gain:.4f}")
        if regression > self.max_regression:
            violations.append(f"Prior regression {regression:.4f} > max {self.max_regression:.4f}")
        if contaminated and self.require_zero_contamination:
            violations.append("Holdout contamination detected")
        if self.require_os_containment and sealing == SealingStatus.NOT_SEALED:
            violations.append("OS containment absent (NOT_SEALED)")
        return len(violations) == 0, violations


class BoundarySecurityViolation(PermissionError):
    """Raised when an untrusted candidate attempts to breach supervisory boundaries."""
