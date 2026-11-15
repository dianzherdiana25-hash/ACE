#!/usr/bin/env python3
"""Operator CLI for the cognitive-memory write path (v1).

Absorption audit (PR #231) item #8 — the Ian + hub
ratification-point entry: when a verdict is sealed, a
mission is ratified, a HIGH finding is opened/closed, or a
skill is verified at a point WE control, record it into
ACE's cognitive memory at that moment, with its evidence
anchored. Run with PYTHONPATH=code from the repo root.

Examples:
  python3 tools/memory_writeback.py record \
      --root /path/to/cognitive_memory \
      --event verdict_sealed \
      --summary "GUARD_ADOPTED (PR #230), act 60fc25e1" \
      --evidence-file evidence/lineage_guard_run.json \
      --subject lineage_guard --predicate status --object adopted

  python3 tools/memory_writeback.py recall \
      --root /path/to/cognitive_memory --query "sovereign_runtime verified"
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from ace_operational.memory_writeback import (  # noqa: E402
    EVENT_CLASSES,
    recall_context,
    record_verified_event,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    rec = sub.add_parser("record", help="record one verified event")
    rec.add_argument("--root", required=True)
    rec.add_argument("--event", required=True, choices=sorted(EVENT_CLASSES))
    rec.add_argument("--summary", required=True)
    rec.add_argument("--evidence-file", required=True)
    rec.add_argument("--confidence", type=float, default=None)
    rec.add_argument("--subject", default=None)
    rec.add_argument("--predicate", default=None)
    rec.add_argument("--object", default=None)

    rc = sub.add_parser("recall", help="recall records for a query")
    rc.add_argument("--root", required=True)
    rc.add_argument("--query", required=True)
    rc.add_argument("--limit", type=int, default=10)

    args = parser.parse_args()
    if args.cmd == "record":
        extra = {}
        for key in ("subject", "predicate", "object"):
            value = getattr(args, key)
            if value is not None:
                extra[key] = value
        record_id = record_verified_event(
            args.root,
            event=args.event,
            summary=args.summary,
            evidence_bytes=Path(args.evidence_file).read_bytes(),
            confidence=args.confidence,
            content_extra=extra or None,
        )
        print(json.dumps({"record_id": record_id}))
        return 0 if record_id else 1
    results = recall_context(args.root, args.query, limit=args.limit)
    print(json.dumps({"returned": len(results), "results": results},
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
