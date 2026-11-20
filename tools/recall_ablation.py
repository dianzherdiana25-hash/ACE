#!/usr/bin/env python3
"""Bandingkan dua lengan fixture agar kontribusi recall bisa dihitung ulang.

Store CLI berupa objek query → daftar keputusan berperingkat. Tugas berupa
larik objek id, query, cold_decision, expected (semua string). Keputusan
adalah hasil recall pertama atau cold_decision bila kosong. Skor adalah
kecocokan persis dengan expected. Seed mengatur urutan tugas untuk kedua
lengan. Ringkasan menyimpan hash byte JSONL agar hasil dapat diperiksa.

Mode `--anchored` memakai store berisi records (query → daftar objek
decision dan based_on) serta verified_refs. Hanya kandidat dengan semua
ref terverifikasi yang masuk ke lengan anchored.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import sys


def fixture_recall(query, store):
    if not isinstance(store, dict):
        raise ValueError("Store fixture wajib berupa objek.")
    return store.get(query, [])


class _FixtureReferences:
    def __init__(self, store):
        refs = store.get("verified_refs") if isinstance(store, dict) else None
        if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
            raise ValueError("Store anchored memerlukan verified_refs berupa daftar string.")
        self.refs = set(refs)

    def verify_ref(self, ref):
        return ref in self.refs


def _anchored_arms(query, store, recall, references, check_anchors):
    recalled = (fixture_recall(query, store.get("records")) if recall is fixture_recall
                else recall(query, deepcopy(store)))
    if not isinstance(recalled, list) or any(
        not isinstance(item, dict) or not isinstance(item.get("decision"), str)
        or not item["decision"].strip() or not isinstance(item.get("based_on"), list)
        for item in recalled
    ):
        raise ValueError("Recall anchored wajib menghasilkan objek decision dan daftar based_on.")
    active = []
    qualified = []
    for item in recalled:
        active.append(item["decision"])
        if check_anchors(item["based_on"], references)["status"] == "anchored":
            qualified.append(item["decision"])
    return (("active", active), ("off", []), ("anchored", qualified))


def run_ablation(store, tasks, *, recall=fixture_recall, seed=0, anchored=False):
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
    if anchored:
        if __package__ in (None, ""):
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
        from ace_operational.memory_anchor import check_anchors

        references = _FixtureReferences(store)
        totals["anchored"] = 0
    for task in ordered:
        if anchored:
            arms = _anchored_arms(task["query"], store, recall, references, check_anchors)
        else:
            recalled = recall(task["query"], deepcopy(store))
            if not isinstance(recalled, list) or not all(
                isinstance(value, str) and value.strip() for value in recalled
            ):
                raise ValueError("Recall wajib menghasilkan daftar string keputusan.")
            arms = (("active", recalled), ("off", []))
        for arm, candidates in arms:
            decision = candidates[0] if candidates else task["cold_decision"]
            score = int(decision == task["expected"])
            rows.append({"arm": arm, "task_id": task["id"], "recalled_count": len(candidates),
                         "decision": decision, "score": score})
            totals[arm] += score
    output = "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows)
    data = output.encode("utf-8")
    n = len(ordered)
    summary = {"schema": "ace.recall-ablation.v1", "tasks": n, "seed": seed,
               "scores": totals, "delta": (totals["active"] - totals["off"]) / n,
               "results_sha256": hashlib.sha256(data).hexdigest()}
    if anchored:
        summary["anchored_delta"] = (totals["anchored"] - totals["off"]) / n
    return data, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--anchored", action="store_true")
    args = parser.parse_args(argv)
    try:
        data, summary = run_ablation(json.loads(args.store.read_text(encoding="utf-8")),
                                    json.loads(args.tasks.read_text(encoding="utf-8")),
                                    seed=args.seed, anchored=args.anchored)
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
