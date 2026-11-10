#!/usr/bin/env python3
"""Run ACE from a source checkout without installing a package."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "code"))

from ace_runtime.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
