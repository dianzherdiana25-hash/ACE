#!/usr/bin/env python3
"""Top-level CLI launcher for ACE Autonomous Runtime."""
from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from ace_autonomy.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
