#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

python3 "$REPO_ROOT/tools/repo_index.py" \
  --root "$REPO_ROOT" \
  --format markdown \
  --output "$REPO_ROOT/docs/REPO_INDEX.md"
