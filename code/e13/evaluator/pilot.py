"""Run a reproducible, development-only pilot with isolated candidate fitting."""

import argparse
import hashlib
import json
import platform
import random
import subprocess
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from time import perf_counter_ns, process_time_ns

from ..contract import canonical_json, parse_fit_request
from ..dsl import Fuel, FuelExhausted, predict
from ..isolation import WorkerError, fit_isolated
from .bank import bank_digest, development_bank


POLICIES = ("fixed", "catalog", "blind", "beam")
_ROOT = Path(__file__).resolve().parents[1]


def source_digest():
    files = sorted(path for path in _ROOT.rglob("*.py") if not path.name.startswith("test_"))
    records = {path.relative_to(_ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in files}
    return hashlib.sha256(canonical_json(records)).hexdigest()


def _record(episode, policy):
    request = parse_fit_request(episode.fit_request)
    row = {"task_id": request.task_id, "family": episode.family, "regime": episode.regime,
           "seed": request.seed, "policy": policy}
    scores = {
        "ordinary": {"correct": 0, "total": len(episode.in_distribution), "failures": 0},
        "extrapolation": {"correct": 0, "total": len(episode.extrapolation), "failures": 0},
    }
    try:
        fit = fit_isolated(episode.fit_request, policy=policy)
    except WorkerError as error:
        for score in scores.values():
            score["failures"] = score["total"]
        return {**row, "scores": scores, "fit_status": "worker_error",
                "error": str(error)}

    scoring_cpu = process_time_ns()
    fuel = Fuel(request.fuel)
    outcomes = score_probes(episode, fit.program.ast, fuel)
    scores = {size: summarize_outcomes(values) for size, values in outcomes.items()}
    return {**row, "scores": scores, "fit_status": fit.status,
            "ast_sha256": fit.program.sha256, "proposals": fit.candidates, "fit_steps": fit.steps,
            "predict_steps": fuel.used, "worker": asdict(fit.metrics),
            "scoring_cpu_us": (process_time_ns() - scoring_cpu) // 1_000}


def score_probes(episode, ast, fuel, *, allow_extension=False):
    outcomes = {}
    for size, probes in (("ordinary", episode.in_distribution),
                         ("extrapolation", episode.extrapolation)):
        matches = []
        for probe in probes:
            try:
                answer = predict(ast, probe.input, fuel, allow_extension=allow_extension)
            except FuelExhausted:
                matches.append(None)
            else:
                matches.append(answer == probe.expected)
        outcomes[size] = matches
    return outcomes


def summarize_outcomes(values):
    return {"correct": sum(value is True for value in values),
            "total": len(values), "failures": sum(value is None for value in values)}


def summarize(rows):
    totals = defaultdict(lambda: {"correct": 0, "total": 0, "failures": 0})
    for row in rows:
        for size, scores in row["scores"].items():
            key = (row["policy"], row["family"], row["regime"], size)
            for metric, value in scores.items():
                totals[key][metric] += value
    return [{**dict(zip(("policy", "family", "regime", "size"), key, strict=True)), **values}
            for key, values in sorted(totals.items())]


def run_pilot(*, bank_seed=1304, order_seed=130413):
    machine = {
        "platform": platform.machine(),
        "kernel": platform.release(),
        "evaluator_python": platform.python_version(),
        "worker_python": subprocess.check_output(["/usr/bin/python3", "-V"], text=True).strip(),
    }
    wall_started, cpu_started = perf_counter_ns(), process_time_ns()
    episodes, _, _ = development_bank(bank_seed)
    bank_cpu = (process_time_ns() - cpu_started) // 1_000
    schedule = [(episode, policy) for episode in episodes for policy in POLICIES]
    random.Random(order_seed).shuffle(schedule)
    rows = [_record(episode, policy) for episode, policy in schedule]
    return {
        "mode": "development", "purpose": "engineering pilot",
        "bank_seed": bank_seed, "order_seed": order_seed, "machine": machine,
        "source_sha256": source_digest(), "bank_sha256": bank_digest(episodes),
        "bank_cpu_us": bank_cpu,
        "evaluator_total_cpu_us": (process_time_ns() - cpu_started) // 1_000,
        "wall_us": (perf_counter_ns() - wall_started) // 1_000,
        "summary": summarize(rows), "runs": rows,
    }


def verify_replay(reference, replay):
    """Compare every deterministic field while allowing host/timing variation."""
    def comparable(report):
        record = dict(report)
        for key in ("machine", "bank_cpu_us", "evaluator_total_cpu_us", "wall_us"):
            record.pop(key, None)
        measurements = {"worker", "scoring_cpu_us"}
        record["runs"] = [{key: value for key, value in row.items() if key not in measurements}
                          for row in report["runs"]]
        return record

    if comparable(reference) != comparable(replay):
        raise ValueError("pilot replay differs in deterministic fields")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank-seed", type=int, default=1304)
    parser.add_argument("--order-seed", type=int, default=130413)
    parser.add_argument("--verify", type=Path, help="compare with a saved pilot JSON")
    args = parser.parse_args()
    report = run_pilot(bank_seed=args.bank_seed, order_seed=args.order_seed)
    if args.verify is not None:
        verify_replay(json.loads(args.verify.read_text()), report)
    print(json.dumps(report, indent=2))
    return int(any(run["fit_status"] == "worker_error" or any(s["failures"] for s in run["scores"].values())
                   for run in report["runs"]))


if __name__ == "__main__":
    raise SystemExit(main())
