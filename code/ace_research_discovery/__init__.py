"""ACE Fase 6: Automated typed structural abstraction discovery & cross-family transfer.

Pure Python standard library only. Strictly isolated from upstream pinned files
and `code/ace_runtime/` implementation bytes.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA = "ace.novel_discovery.v1"
PRESCORE_COMMIT = "6e0eae81e4a0b9c1bf7f1d2e5c7fabd19f47d175"
PRESCORE_SHA256 = "0ada99092e3e88a345d375d763bf529e38bac06138b74c58fb319d8072bd77fd"


def canonical_json(value: Any) -> bytes:
    """Deterministic UTF-8 canonical JSON serialization without NaN/Infinity."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")


def digest(value: Any) -> str:
    """FIPS 180-4 SHA-256 hex digest of canonical JSON representation."""
    return hashlib.sha256(canonical_json(value)).hexdigest()
