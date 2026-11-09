#!/usr/bin/env python3
"""Read-only ACE ask-ai consultation scoring via the safe, bounded AST interpreter.

Does not execute AI-generated Python, call external services, change checkpoint
files, or promote candidates. Never infer upstream provider identity from labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))

from ace_code_agent.static_probe import UnsafeOrUnsupported, public_diagnostic


def audit_consultations(path: Path, limit: int = 5) -> dict:
    if not 1 <= limit <= 30:
        raise ValueError("limit must be between 1 and 30")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("consultation file must contain a JSON list")
    records = []
    for record in data[-limit:]:
        if not isinstance(record, dict):
            records.append({"status": "REJECTED_MALFORMED_RECORD"})
            continue
        source = record.get("ai_answered")
        entry = {
            "timestamp": str(record.get("timestamp", "")),
            "hypothesis_id": str(record.get("hypothesis_id", "")),
            "declared_provider_label_unverified": str(record.get("engine", "")),
            "provider_verified": False,
            "candidate_source_sha256": (
                hashlib.sha256(source.encode("utf-8")).hexdigest()
                if isinstance(source, str) else None
            ),
            "candidate_python_executed": False,
            "connected_to_active_algorithm": False,
            "scientific_status": "NOT_ASSESSED",
        }
        if not isinstance(source, str):
            entry["status"] = "NO_CANDIDATE_SOURCE"
        else:
            try:
                entry["public_diagnostic"] = public_diagnostic(source)
                entry["status"] = "PUBLIC_DIAGNOSTIC_ONLY"
            except UnsafeOrUnsupported as exc:
                entry["status"] = "UNSUPPORTED_STATIC_GRAMMAR"
                entry["reason"] = str(exc)
            except Exception:
                entry["status"] = "PUBLIC_DIAGNOSTIC_ERROR"
                entry["reason"] = "Unexpected interpreter failure; no candidate execution."
        records.append(entry)
    return {
        "schema": "ace.ask_ai.public_diagnostic.v1",
        "records_scored": len(records),
        "records": records,
        "release_gate": "BLOCK_RELEASE",
        "scientific_status": "NOT_ASSESSED",
        "candidate_deployed": False,
        "note": (
            "Public synthetic diagnostics, not a sealed evaluator. "
            "No model identity verification, network invocation or candidate promotion."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "checkpoints" / "self_dev" / "ai_consultations.json",
    )
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    try:
        result = audit_consultations(args.input, args.limit)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "ERROR", "reason": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
