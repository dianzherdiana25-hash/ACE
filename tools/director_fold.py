#!/usr/bin/env python3
"""Rencanakan lipatan ekspor proposal supaya duplikat bisa ditelaah lokal.

JSONL memuat task_id, based_on (daftar ref), status, dan created_at
berzona. Field bukti dan batas dampak opsional mengikuti director_classes.
Semua status ekspor ikut rencana. Kelas kelompok memakai kelas paling
ketat dari anggotanya. Kelompok multi-gap minimal B.
"""
import argparse
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from ace_operational.director_classes import classify_proposal


_RANK = {"A": 0, "B": 1, "C": 2}


def fold_proposals(rows):
    groups = defaultdict(list)
    seen = set()
    for index, row in enumerate(rows, 1):
        if (not isinstance(row, dict) or not all(
            isinstance(row.get(key), str) and row[key].strip()
            for key in ("task_id", "status", "created_at")
        ) or row["task_id"] in seen):
            raise ValueError(f"Proposal {index} tidak sah atau ID ganda.")
        refs = row.get("based_on")
        if not isinstance(refs, list) or any(
            not isinstance(ref, str) or not ref.strip() for ref in refs
        ):
            raise ValueError(f"based_on proposal {index} tidak sah.")
        try:
            stamp = datetime.fromisoformat(row["created_at"])
            if stamp.utcoffset() is None:
                raise ValueError
        except ValueError:
            raise ValueError(f"created_at proposal {index} wajib berzona.") from None
        unique = sorted(set(refs))
        key = ("gap", unique[0]) if len(unique) == 1 else ("multi_gap" if unique else "unattributed", "")
        groups[key].append((stamp, row["task_id"], row))
        seen.add(row["task_id"])

    folded = []
    for (kind, gap), entries in sorted(groups.items()):
        entries.sort(key=lambda entry: entry[:2])
        classes = []
        refs = set()
        for _, task_id, row in entries:
            refs.update(row["based_on"])
            result = classify_proposal({"kind": "director_proposal", "checkpoint": row})
            classes.append({"task_id": task_id, **result})
        suggested = max((entry["class"] for entry in classes), key=_RANK.get)
        if kind == "multi_gap" and suggested == "A":
            suggested = "B"
        folded.append({"kind": kind, "based_on": [gap] if gap else sorted(refs),
                       "representative": entries[0][1], "duplicates": [entry[1] for entry in entries[1:]],
                       "initial_class": suggested, "classifications": classes})
    return {"schema": "ace.director-fold-plan.v1", "proposal_count": len(seen), "groups": folded}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposals", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.proposals.open(encoding="utf-8") as source:
            result = fold_proposals(json.loads(line) for line in source if line.strip())
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
