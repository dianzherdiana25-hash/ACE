#!/usr/bin/env python3
"""Bandingkan dua lengan fixture agar kontribusi recall bisa dihitung ulang.

Store CLI berupa objek query → daftar keputusan berperingkat. Tugas berupa
larik objek id, query, cold_decision, expected (semua string). Keputusan
adalah hasil recall pertama atau cold_decision bila kosong. Skor adalah
kecocokan persis dengan expected. Seed mengatur urutan tugas untuk kedua
lengan. Ringkasan menyimpan hash byte JSONL agar hasil dapat diperiksa.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random


def fixture_recall(query, store):
    if not isinstance(store, dict):
        raise ValueError("Store fixture wajib berupa objek.")
    return store.get(query, [])


def run_ablation(store, tasks, *, recall=fixture_recall, seed=0):
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("Daftar tugas wajib berupa larik berisi.")
    ids = set()
    for task in tasks:
        if not isinstance(task, dict) or not all(
            isinstance(task.get(key), str) and task[key].strip()
            for key in ("id", "query", "cold_decision", "expected")
        ) or task["id"] in ids:
            raise ValueError("Tugas fixture tidak sah atau ID ganda.")
        ids.add(task["id"])
    ordered = sorted(tasks, key=lambda task: task["id"])
    random.Random(seed).shuffle(ordered)
    rows = []
    totals = {"active": 0, "off": 0}
    for task in ordered:
        recalled = recall(task["query"], deepcopy(store))
        if not isinstance(recalled, list) or not all(
            isinstance(value, str) and value.strip() for value in recalled
        ):
            raise ValueError("Recall wajib menghasilkan daftar string keputusan.")
        for arm, candidates in (("active", recalled), ("off", [])):
            decision = candidates[0] if candidates else task["cold_decision"]
            score = int(decision == task["expected"])
            rows.append({"arm": arm, "task_id": task["id"], "recalled_count": len(candidates),
                         "decision": decision, "score": score})
            totals[arm] += score
    output = "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows)
    data = output.encode("utf-8")
    n = len(ordered)
    return data, {"schema": "ace.recall-ablation.v1", "tasks": n, "seed": seed,
                  "scores": totals, "delta": (totals["active"] - totals["off"]) / n,
                  "results_sha256": hashlib.sha256(data).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        data, summary = run_ablation(json.loads(args.store.read_text(encoding="utf-8")),
                                    json.loads(args.tasks.read_text(encoding="utf-8")), seed=args.seed)
        args.output_dir.mkdir()
        (args.output_dir / "results.jsonl").write_bytes(data)
        (args.output_dir / "summary.json").write_text(
            json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
