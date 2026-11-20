#!/usr/bin/env python3
"""Rencanakan lipatan ekspor proposal supaya duplikat bisa ditelaah lokal.

JSONL memuat task_id, based_on (daftar ref), status, dan created_at
berzona. Field bukti dan batas dampak opsional mengikuti director_classes.
Semua status ekspor ikut rencana. Kelas kelompok memakai kelas paling
ketat dari anggotanya. Kelompok multi-gap minimal B.
--require-anchored memeriksa kelas A terhadap --store, objek JSON dengan
verified_refs berupa daftar string. Ref yang masih dangling menurunkan kelas ke B.
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
from ace_operational.memory_anchor import check_anchors


_RANK = {"A": 0, "B": 1, "C": 2}


class _FixtureStore:
    def __init__(self, data):
        refs = data.get("verified_refs") if isinstance(data, dict) else None
        if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
            raise ValueError("Store memerlukan verified_refs berupa daftar string.")
        self.refs = frozenset(refs)

    def verify_ref(self, ref):
        return ref in self.refs


def fold_proposals(rows, *, anchor_store=None):
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
        group = {"kind": kind, "based_on": sorted(refs),
                 "representative": entries[0][1], "duplicates": [entry[1] for entry in entries[1:]],
                 "initial_class": suggested, "classifications": classes}
        if (anchor_store is not None and suggested == "A"
                and check_anchors(group["based_on"], anchor_store)["status"] != "anchored"):
            group["initial_class"] = "B"
            group["class_reasons"] = ["unanchored"]
        folded.append(group)
    return {"schema": "ace.director-fold-plan.v1", "proposal_count": len(seen), "groups": folded}


def build_fold_plan_view(folded: dict) -> dict:
    """Bentuk rencana lipat JSON read-only berisi perwakilan, duplikat, dan payung multi-gap."""
    groups = folded["groups"]
    umbrella = [group for group in groups if group["kind"] == "multi_gap"]
    return {
        "schema": folded["schema"],
        "mode": "plan_only",
        "read_only": True,
        "proposal_count": folded["proposal_count"],
        "representative_count": len(groups),
        "duplicate_count": sum(len(group["duplicates"]) for group in groups),
        "umbrella_count": len(umbrella),
        "representatives": [group["representative"] for group in groups],
        "umbrella_groups": umbrella,
        "duplicates_by_group": {
            group["representative"]: {
                "kind": group["kind"],
                "based_on": group["based_on"],
                "duplicate_count": len(group["duplicates"]),
                "duplicates": group["duplicates"],
                "initial_class": group["initial_class"],
            }
            for group in groups
        },
        "groups": groups,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposals", type=Path)
    parser.add_argument("--plan", action="store_true", help="Keluarkan ringkasan rencana lipat JSON tanpa mengubah berkas.")
    parser.add_argument("--require-anchored", action="store_true")
    parser.add_argument("--store", type=Path)
    args = parser.parse_args(argv)
    if args.require_anchored != (args.store is not None):
        parser.error("--require-anchored dan --store wajib dipakai bersama.")
    try:
        store = _FixtureStore(json.loads(args.store.read_text(encoding="utf-8"))) if args.store else None
        with args.proposals.open(encoding="utf-8") as source:
            result = fold_proposals((json.loads(line) for line in source if line.strip()), anchor_store=store)
        if args.plan:
            result = build_fold_plan_view(result)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
