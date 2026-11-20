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


def _change_rate(decisions):
    if len(decisions) <= 1:
        return 0.0
    changes = sum(1 for prev, curr in zip(decisions, decisions[1:]) if prev != curr)
    return changes / (len(decisions) - 1)


def _run_multiseed_ablation(store, tasks, *, recall=fixture_recall, seed=0, seeds=1, anchored=False):
    if type(seeds) is not int or seeds <= 0:
        raise ValueError("Jumlah --seeds wajib bilangan bulat positif.")
    seed_list = [seed + offset for offset in range(seeds)]
    all_rows = []
    arm_names = ("active", "off", "anchored") if anchored else ("active", "off")
    totals = {arm: 0 for arm in arm_names}
    per_task_arm_decisions = {
        task["id"]: {arm: [] for arm in arm_names}
        for task in sorted(tasks, key=lambda t: t["id"])
    }

    if anchored:
        if __package__ in (None, ""):
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
        from ace_operational.memory_anchor import check_anchors
        references = _FixtureReferences(store)

    for current_seed in seed_list:
        rng = random.Random(current_seed)
        ordered = sorted(tasks, key=lambda task: task["id"])
        rng.shuffle(ordered)
        for task in ordered:
            if anchored:
                raw_arms = _anchored_arms(task["query"], store, recall, references, check_anchors)
                arms = []
                for arm, candidates in raw_arms:
                    cand_list = list(candidates)
                    if recall is fixture_recall and len(cand_list) > 1:
                        rng.shuffle(cand_list)
                    arms.append((arm, cand_list))
            else:
                recalled = recall(task["query"], deepcopy(store))
                if not isinstance(recalled, list) or not all(
                    isinstance(value, str) and value.strip() for value in recalled
                ):
                    raise ValueError("Recall wajib menghasilkan daftar string keputusan.")
                cand_list = list(recalled)
                if recall is fixture_recall and len(cand_list) > 1:
                    rng.shuffle(cand_list)
                arms = (("active", cand_list), ("off", []))
            for arm, candidates in arms:
                decision = candidates[0] if candidates else task["cold_decision"]
                score = int(decision == task["expected"])
                all_rows.append({
                    "seed": current_seed,
                    "arm": arm,
                    "task_id": task["id"],
                    "recalled_count": len(candidates),
                    "decision": decision,
                    "score": score,
                })
                totals[arm] += score
                per_task_arm_decisions[task["id"]][arm].append(decision)

    output = "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in all_rows)
    data = output.encode("utf-8")
    n = len(tasks)
    denom = n * len(seed_list)

    per_task = {}
    stable_tasks = []
    seed_sensitive_tasks = []
    for task_id, arm_map in sorted(per_task_arm_decisions.items()):
        active_decisions = arm_map["active"]
        rate = _change_rate(active_decisions)
        arm_rates = {arm: _change_rate(decs) for arm, decs in arm_map.items()}
        is_sensitive = len(set(active_decisions)) > 1 or any(
            len(set(decs)) > 1 for decs in arm_map.values()
        )
        classification = "seed_sensitive" if is_sensitive else "stable"
        if is_sensitive:
            seed_sensitive_tasks.append(task_id)
        else:
            stable_tasks.append(task_id)
        per_task[task_id] = {
            "task_id": task_id,
            "classification": classification,
            "stable": not is_sensitive,
            "seed_sensitive": is_sensitive,
            "decision_change_rate": rate,
            "arm_change_rates": arm_rates,
            "unique_decisions": sorted(set(active_decisions)),
            "decisions_by_seed": {
                str(s): d for s, d in zip(seed_list, active_decisions)
            },
        }

    mean_rate = (
        sum(item["decision_change_rate"] for item in per_task.values()) / n
        if n else 0.0
    )
    summary = {
        "schema": "ace.recall-ablation.v1",
        "tasks": n,
        "seed": seed,
        "seeds": seed_list,
        "seed_count": len(seed_list),
        "scores": totals,
        "delta": (totals["active"] - totals["off"]) / denom,
        "per_task": per_task,
        "stable_tasks": stable_tasks,
        "seed_sensitive_tasks": seed_sensitive_tasks,
        "stability_counts": {
            "stable": len(stable_tasks),
            "seed_sensitive": len(seed_sensitive_tasks),
        },
        "mean_decision_change_rate": mean_rate,
        "results_sha256": hashlib.sha256(data).hexdigest(),
    }
    if anchored:
        summary["anchored_delta"] = (totals["anchored"] - totals["off"]) / denom
    return data, summary


def run_ablation(store, tasks, *, recall=fixture_recall, seed=0, anchored=False, seeds=None):
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
    if seeds is not None:
        return _run_multiseed_ablation(
            store, tasks, recall=recall, seed=seed, seeds=seeds, anchored=anchored
        )
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
    parser.add_argument("--seeds", type=int, default=None)
    parser.add_argument("--anchored", action="store_true")
    args = parser.parse_args(argv)
    try:
        data, summary = run_ablation(json.loads(args.store.read_text(encoding="utf-8")),
                                    json.loads(args.tasks.read_text(encoding="utf-8")),
                                    seed=args.seed, anchored=args.anchored, seeds=args.seeds)
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
