"""ACE End-to-End (E2E) Test Suite.

Covers the 10 core engineering backlog requirements across 4 systematic tiers:
Tier 1: Feature Coverage (happy-path isolated verification)
Tier 2: Boundary & Corner Cases (stale tokens, process crashes, AST escapes, empty/invalid inputs)
Tier 3: Cross-Feature Interactions (cross-module invariants, transactional integrity)
Tier 4: Real-World Scenarios (complete loops, simulated recovery, verified receipts)
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure ACE/code is on sys.path for test discovery
_CODE_DIR = Path(__file__).resolve().parent.parent.parent / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))
