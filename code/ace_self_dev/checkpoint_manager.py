"""Checkpoint Manager: Manages crash-safe persistence and recovery for self-development cycles."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .models import CycleCheckpoint


class CheckpointManager:
    """Provides atomic, crash-safe checkpoint persistence and state resumption."""

    def __init__(self, checkpoint_dir: str = "checkpoints/self_dev"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, cycle_id: int) -> Path:
        return self.checkpoint_dir / f"cycle_{cycle_id:04d}.json"

    def save_checkpoint(self, checkpoint: CycleCheckpoint) -> str:
        """Atomically persist cycle state."""
        target_path = self._get_path(checkpoint.cycle_id)
        temp_path = target_path.with_suffix(".tmp")
        payload = json.dumps(checkpoint.to_dict(), indent=2).encode("utf-8")
        with open(temp_path, "wb") as f:
            f.write(payload)
        temp_path.replace(target_path)
        return str(target_path)

    def load_checkpoint(self, cycle_id: int) -> Optional[CycleCheckpoint]:
        """Load checkpoint if it exists."""
        target_path = self._get_path(cycle_id)
        if not target_path.exists():
            return None
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return CycleCheckpoint.from_dict(data)

    def has_checkpoint(self, cycle_id: int) -> bool:
        return self._get_path(cycle_id).exists()
