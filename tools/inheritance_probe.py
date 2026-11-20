#!/usr/bin/env python3
"""Bandingkan hasil fixture warisan dan dingin dengan tugas yang sama.

Snapshot dan tugas ialah JSON. Tugas berupa larik objek dengan id unik.
Runner tepercaya memakai argv JSON, token literal {snapshot} dan {tasks}
diganti dengan path salinan fixture. Stdout runner ialah objek id → boolean.
Dry-run membaca peta id → boolean pada field passes di setiap snapshot.
CLI menulis manifest baru sebelum menjalankan probe. Default
`inheritance-manifest.json` di direktori kerja. Gunakan `--verify-manifest`
untuk mengulang dari berkas dan byte yang sama.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory


PROVENANCE_SCHEMA = "ace.inheritance-provenance.v1"


def _prepare_inputs(paths):
    inputs = {}
    contents = {}
    for label, path in paths.items():
        if path is None:
            inputs[label] = None
            continue
        resolved = path.resolve()
        data = resolved.read_bytes()
        contents[label] = data
        inputs[label] = {"path": str(resolved), "sha256": hashlib.sha256(data).hexdigest(),
                         "size_bytes": len(data)}
    return {"schema": PROVENANCE_SCHEMA, "inputs": inputs}, contents


def _verify_manifest(expected, observed):
    if (not isinstance(expected, dict) or expected.get("schema") != PROVENANCE_SCHEMA
            or not isinstance(expected.get("inputs"), dict)):
        raise ValueError("Skema manifest provenance tidak sah.")
    checked = expected["inputs"]
    inputs = observed["inputs"]
    if checked.keys() != inputs.keys():
        raise ValueError("Daftar masukan manifest tidak sah.")
    for label, current in inputs.items():
        if checked[label] != current:
            name = Path(current["path"]).name if current else label
            raise ValueError(f"Manifest tidak cocok untuk {label} ({name}).")


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
    provenance = parser.add_mutually_exclusive_group()
    provenance.add_argument("--manifest", type=Path,
                            help="Berkas manifest baru. Default inheritance-manifest.json.")
    provenance.add_argument("--verify-manifest", type=Path, help="Verifikasi manifest sebelum lari.")
    args = parser.parse_args(argv)
    try:
        manifest, data = _prepare_inputs({
            "inherited": args.inherited, "cold": args.cold, "tasks": args.tasks,
            "runner_argv": args.runner_argv,
        })
        if args.verify_manifest:
            _verify_manifest(json.loads(args.verify_manifest.read_bytes()), manifest)
        inherited, cold, tasks = (json.loads(data[key]) for key in ("inherited", "cold", "tasks"))
        runner = json.loads(data["runner_argv"]) if args.runner_argv and not args.dry_run else None
        if not args.verify_manifest:
            target = args.manifest or Path("inheritance-manifest.json")
            with target.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        result = compare(inherited, cold, tasks,
                         dry_run=args.dry_run, runner=runner, timeout=args.timeout)
    except subprocess.SubprocessError:
        parser.exit(2, "Runner fixture gagal atau habis waktu.\n")
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
