#!/usr/bin/env python3
"""Bandingkan hasil fixture warisan dan dingin dengan tugas yang sama.

Snapshot dan tugas ialah JSON. Tugas berupa larik objek dengan id unik.
Runner tepercaya memakai argv JSON, token literal {snapshot} dan {tasks}
diganti dengan path salinan fixture. Stdout runner ialah objek id → boolean.
Dry-run membaca peta id → boolean pada field passes di setiap snapshot.
"""
import argparse
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


def _check_results(result, ids):
    if not isinstance(result, dict) or result.keys() != ids or any(
        type(value) is not bool for value in result.values()
    ):
        raise ValueError("Runner harus memberi tepat satu boolean per ID tugas.")
    return result


def _run_command(template, snapshot, tasks, timeout):
    with TemporaryDirectory(prefix="ace-inheritance-fixture-") as directory:
        root = Path(directory)
        events = {"{snapshot}": root / "snapshot.json", "{tasks}": root / "tasks.json"}
        for key, payload in (("{snapshot}", snapshot), ("{tasks}", tasks)):
            events[key].write_text(json.dumps(payload), encoding="utf-8")
        argv = [str(events[part]) if part in events else part for part in template]
        proc = subprocess.run(argv, cwd=root, check=True, capture_output=True, timeout=timeout)
        return json.loads(proc.stdout)


def compare(inherited, cold, tasks, *, dry_run=False, runner=None, timeout=30):
    if not isinstance(tasks, list) or not tasks or any(
        not isinstance(task, dict) or not isinstance(task.get("id"), str) or not task["id"].strip()
        for task in tasks
    ):
        raise ValueError("Tugas wajib berupa larik berisi ID string.")
    ids = {task["id"] for task in tasks}
    if len(ids) != len(tasks):
        raise ValueError("ID tugas ganda.")
    if not dry_run and (not isinstance(runner, list) or not all(
        isinstance(arg, str) and arg for arg in runner
    ) or not {"{snapshot}", "{tasks}"}.issubset(runner)
                        or type(timeout) is not int or timeout <= 0):
        raise ValueError("Runner memerlukan argv JSON dengan token {snapshot} dan {tasks}, serta timeout positif.")
    outcomes = []
    for snapshot in (inherited, cold):
        if not isinstance(snapshot, dict):
            raise ValueError("Snapshot harus berupa objek JSON.")
        result = snapshot.get("passes") if dry_run else _run_command(runner, snapshot, tasks, timeout)
        outcomes.append(_check_results(result, ids))
    warm_results, cold_results = outcomes
    rows = [{"id": task["id"], "inherited": warm_results[task["id"]],
             "cold": cold_results[task["id"]]} for task in tasks]
    totals = {"inherited": sum(warm_results.values()), "cold": sum(cold_results.values())}
    return {"schema": "ace.inheritance-probe.v1", "mode": "dry_run" if dry_run else "fixture_runner",
            "tasks": rows, "pass_counts": totals,
            "delta": (totals["inherited"] - totals["cold"]) / len(tasks)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("inherited", "cold", "tasks"):
        parser.add_argument(f"--{flag}", required=True, type=Path)
    parser.add_argument("--runner-argv", type=Path)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        def read(path):
            return json.loads(path.read_text(encoding="utf-8"))
        runner = read(args.runner_argv) if args.runner_argv and not args.dry_run else None
        result = compare(read(args.inherited), read(args.cold), read(args.tasks),
                         dry_run=args.dry_run, runner=runner, timeout=args.timeout)
    except subprocess.SubprocessError:
        parser.exit(2, "Runner fixture gagal atau habis waktu.\n")
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
