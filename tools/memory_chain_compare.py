"""Perbandingan dua ujung rantai hash cognitive memory JSONL (AG51).

Membandingkan dua berkas rantai memori JSONL (``--left`` dan ``--right``) dan
mengklasifikasikan hubungannya menjadi:
- ``identical``: ujung rantai dan seluruh entri identik persis,
- ``fast_forward``: satu sisi merupakan perpanjangan ekor sah dari sisi lainnya
  (ekor lebih panjang, BUKAN fork),
- ``diverged``: bercabang sejak entri ketidaksamaan pertama beserta titik
  divergensi persis (``seq``, ``hash_left``, ``hash_right``, ``last_common_hash``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.memory-chain-compare.v1"
GENESIS_PREV = "GENESIS"


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _compute_hash(prev: str, event: Any) -> str:
    return hashlib.sha256(_canonical({"prev": prev, "event": event}).encode("utf-8")).hexdigest()


def load_and_verify_chain(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Muat berkas JSONL rantai hash memori secara read-only dan cek integritasnya."""
    entries: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    expected_prev = GENESIS_PREV
    expected_seq = 1

    for line_no, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            errors.append({"line": line_no, "reason": "invalid_json", "detail": str(exc)})
            continue
        if not isinstance(obj, dict):
            errors.append({"line": line_no, "reason": "entry_not_object"})
            continue

        seq = obj.get("seq")
        prev = obj.get("prev")
        event = obj.get("event")
        digest = obj.get("hash")

        if seq != expected_seq:
            errors.append(
                {
                    "line": line_no,
                    "reason": "seq_mismatch",
                    "expected_seq": expected_seq,
                    "actual_seq": seq,
                }
            )
        if prev != expected_prev:
            errors.append(
                {
                    "line": line_no,
                    "reason": "prev_mismatch",
                    "expected_prev": expected_prev,
                    "actual_prev": prev,
                }
            )
        if not isinstance(event, dict) or not isinstance(digest, str) or not digest:
            errors.append({"line": line_no, "reason": "missing_event_or_hash"})
        else:
            expected_digest = _compute_hash(str(prev or ""), event)
            if digest != expected_digest:
                errors.append(
                    {
                        "line": line_no,
                        "reason": "hash_mismatch",
                        "expected_hash": expected_digest,
                        "actual_hash": digest,
                    }
                )

        entries.append(obj)
        expected_seq = (seq + 1) if isinstance(seq, int) and not isinstance(seq, bool) else (expected_seq + 1)
        if isinstance(digest, str) and digest:
            expected_prev = digest

    return entries, errors


def _head_summary(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not entries:
        return {"length": 0, "head_seq": 0, "head_hash": GENESIS_PREV}
    tail = entries[-1]
    return {
        "length": len(entries),
        "head_seq": tail.get("seq"),
        "head_hash": tail.get("hash"),
    }


def compare_memory_chains(left_path: Path, right_path: Path) -> dict[str, Any]:
    """Bandingkan dua rantai memory JSONL dan tentukan identical/fast_forward/diverged."""
    left_entries, left_errors = load_and_verify_chain(left_path)
    right_entries, right_errors = load_and_verify_chain(right_path)

    min_len = min(len(left_entries), len(right_entries))
    common_count = 0
    last_common_seq: int | None = 0
    last_common_hash: str = GENESIS_PREV
    first_divergence: dict[str, Any] | None = None

    for idx in range(min_len):
        le = left_entries[idx]
        re_ = right_entries[idx]
        same_entry = (
            le.get("seq") == re_.get("seq")
            and le.get("prev") == re_.get("prev")
            and le.get("hash") == re_.get("hash")
        )
        if same_entry:
            common_count += 1
            last_common_seq = le.get("seq")
            last_common_hash = str(le.get("hash") or "")
        else:
            first_divergence = {
                "index": idx,
                "seq_left": le.get("seq"),
                "seq_right": re_.get("seq"),
                "prev_left": le.get("prev"),
                "prev_right": re_.get("prev"),
                "hash_left": le.get("hash"),
                "hash_right": re_.get("hash"),
                "last_common_seq": last_common_seq,
                "last_common_hash": last_common_hash,
            }
            break

    if first_divergence is not None:
        status = "diverged"
        is_fork = True
        ahead_side: str | None = None
        ahead_entries = 0
    elif len(left_entries) == len(right_entries):
        status = "identical"
        is_fork = False
        ahead_side = None
        ahead_entries = 0
    elif len(right_entries) > len(left_entries):
        status = "fast_forward"
        is_fork = False
        ahead_side = "right"
        ahead_entries = len(right_entries) - len(left_entries)
    else:
        status = "fast_forward"
        is_fork = False
        ahead_side = "left"
        ahead_entries = len(left_entries) - len(right_entries)

    return {
        "schema": SCHEMA,
        "status": status,
        "is_fork": is_fork,
        "ahead_side": ahead_side,
        "ahead_entries": ahead_entries,
        "common_prefix_length": common_count,
        "last_common_seq": last_common_seq,
        "last_common_hash": last_common_hash,
        "first_divergence": first_divergence,
        "left": {
            "path": str(left_path),
            **_head_summary(left_entries),
            "integrity_valid": len(left_errors) == 0,
            "integrity_errors": left_errors,
        },
        "right": {
            "path": str(right_path),
            **_head_summary(right_entries),
            "integrity_valid": len(right_errors) == 0,
            "integrity_errors": right_errors,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bandingkan dua kepala rantai hash cognitive memory JSONL."
    )
    parser.add_argument("--left", required=True, help="Path memory.jsonl kiri.")
    parser.add_argument("--right", required=True, help="Path memory.jsonl kanan.")
    parser.add_argument("--out", help="Path output JSON opsional (default stdout).")
    args = parser.parse_args(argv)

    try:
        report = compare_memory_chains(Path(args.left), Path(args.right))
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
