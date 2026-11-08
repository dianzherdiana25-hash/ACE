"""Sealed seed generator managing secret and public fallback evaluation environments (W2 Rule 3)."""
from __future__ import annotations

import hashlib
import os
from typing import Tuple


def get_evaluation_seed_and_status() -> Tuple[int, str]:
    """Retrieve evaluation seed and authoritative scientific claim status.

    Rule 3:
    - If ACE_SEALED_SEED is set (e.g. from owner secret), derives integer seed and marks 'CONFIRMED_SEALED'.
    - If not set, falls back to public development seed 20261108 and strictly enforces status 'NOT_ASSESSED'.
    """
    secret = os.environ.get("ACE_SEALED_SEED")
    if secret and secret.strip():
        # Derive 32-bit positive integer seed from secret hash
        digest = hashlib.sha256(secret.strip().encode("utf-8")).hexdigest()
        seed = int(digest[:8], 16)
        return seed, "CONFIRMED_SEALED"

    # Fallback public dev seed
    return 20261108, "NOT_ASSESSED"
