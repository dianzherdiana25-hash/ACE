"""Replayable public pilot for state expansion, inheritance and its controls."""

import argparse
import hashlib
import json
import platform
import random
import subprocess
from dataclasses import asdict
from pathlib import Path
from time import perf_counter_ns, process_time_ns

from ..contract import canonical_json, parse_fit_request
from ..dsl import Fuel, predict
from ..extension import POLICIES
from ..isolation import WorkerError, fit_isolated, replay_isolated
from .bank import bank_digest
from .pilot import POLICIES as BASELINES
from .pilot import score_probes, source_digest, summarize, summarize_outcomes, verify_replay
from .transfer_bank import transfer_bank


def _witnesses(raw, ast):
    request = json.loads(raw)
    matches = []
    fuel = Fuel(request["fuel"])
    for index, demo in enumerate(request["target"]):
        answer = predict(ast, canonical_json(demo["input"]), fuel, allow_extension=True)
        if canonical_json(answer) == canonical_json(demo["output"]):
            matches.append(index)
    return matches


def _replay(episode, policy, fit):
    parent = fit.trace["source_definition"] if policy == "c_extend" else None
    fresh = replay_isolated(episode.fit_request, parent)
    same = (fresh.program.ast == fit.program.ast and fresh.status == fit.status
            and all(fresh.trace[key] == fit.trace[key]
                    for key in ("parent", "target", "target_steps", "target_definition")))
    return {"match": same, "ast_sha256": fresh.program.sha256, "parent": fresh.trace["parent"]}


def _record(episode, policy):
    request = parse_fit_request(episode.fit_request)
    row = {
        "task_id": request.task_id, "family": episode.family, "regime": episode.regime,
        "policy": policy, "seed": request.seed, "request_sha256": hashlib.sha256(
            episode.fit_request,
        ).hexdigest(),
    }
    try:
        fit = fit_isolated(episode.fit_request, policy=policy)
    except WorkerError as error:
        outcomes = {"ordinary": [None] * len(episode.in_distribution),
                    "extrapolation": [None] * len(episode.extrapolation)}
        return {**row, "fit_status": "worker_error", "error": str(error), "outcomes": outcomes,
                "scores": {name: summarize_outcomes(values) for name, values in outcomes.items()}}

    started = process_time_ns()
    fuel = Fuel(request.fuel)
    outcomes = score_probes(episode, fit.program.ast, fuel, allow_extension=policy in POLICIES)
    row.update({
        "fit_status": fit.status, "ast": json.loads(fit.program.ast),
        "ast_sha256": fit.program.sha256, "states": len(fit.program.table),
        "proposals": fit.candidates, "fit_steps": fit.steps, "predict_steps": fuel.used,
        "worker": asdict(fit.metrics), "scoring_cpu_us": (process_time_ns() - started) // 1_000,
        "outcomes": outcomes, "scores": {name: summarize_outcomes(values)
                                        for name, values in outcomes.items()},
    })
    if fit.trace is not None:
        row["trace"] = fit.trace
        row["target_demo_matches"] = _witnesses(episode.fit_request, fit.program.ast)
        row["semantic_status"] = "UNKNOWN"
    if policy in ("c_extend", "c_no_transfer"):
        try:
            row["fresh_replay"] = _replay(episode, policy, fit)
        except WorkerError as error:
            row["fresh_replay"] = {"match": False, "error": str(error)}
    return row


def _paired(rows):
    index = {(row["task_id"], row["policy"]): row for row in rows}
    contrasts = []
    for row in rows:
        if row["policy"] != "c_extend":
            continue
        for control in ("c_no_extend", "c_no_transfer", "c_sham"):
            other = index[row["task_id"], control]
            pairs = [(a, b) for size in row["outcomes"]
                     for a, b in zip(row["outcomes"][size], other["outcomes"][size], strict=True)]
            contrasts.append({
                "task_id": row["task_id"], "family": row["family"], "regime": row["regime"],
                "control": control, "gains": sum(a is True and b is not True for a, b in pairs),
                "losses": sum(a is not True and b is True for a, b in pairs), "total": len(pairs),
            })
    return contrasts


def _index_traces(rows):
    """Store each repeated proposal digest only once in the evidence file."""
    digests = sorted({digest for row in rows if "trace" in row
                      for stage in ("source", "target") for digest, _ in row["trace"][stage]})
    indices = {digest: i for i, digest in enumerate(digests)}
    for row in rows:
        if "trace" in row:
            for stage in ("source", "target"):
                row["trace"][stage] = [[indices[digest], score]
                                       for digest, score in row["trace"][stage]]
    return digests


def run_pilot():
    seed, order_seed = 131503, 131504
    machine = {"platform": platform.machine(), "kernel": platform.release(),
               "evaluator_python": platform.python_version(),
               "worker_python": subprocess.check_output(["/usr/bin/python3", "-V"], text=True).strip()}
    start_wall, start_cpu = perf_counter_ns(), process_time_ns()
    episodes = transfer_bank(seed)
    bank_cpu = (process_time_ns() - start_cpu) // 1_000
    schedule = [(episode, policy) for episode in episodes for policy in (*BASELINES, *POLICIES)]
    random.Random(order_seed).shuffle(schedule)
    rows = [_record(episode, policy) for episode, policy in schedule]
    digests = _index_traces(rows)
    return {
        "mode": "development", "purpose": "public engineered state and transfer diagnostics",
        "bank_seed": seed, "order_seed": order_seed, "machine": machine,
        "bank_sha256": bank_digest(episodes), "source_sha256": source_digest(),
        "bank_cpu_us": bank_cpu, "evaluator_total_cpu_us": (process_time_ns() - start_cpu) // 1_000,
        "wall_us": (perf_counter_ns() - start_wall) // 1_000,
        "proposal_sha256_by_index": digests, "summary": summarize(rows), "paired": _paired(rows),
        "runs": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    report = run_pilot()
    if args.verify is not None:
        verify_replay(json.loads(args.verify.read_text()), report)
    print(json.dumps(report, separators=(",", ":")))
    return int(any(row["fit_status"] == "worker_error"
                   or any(s["failures"] for s in row["scores"].values())
                   or not row.get("fresh_replay", {"match": True})["match"]
                   for row in report["runs"]))


if __name__ == "__main__":
    raise SystemExit(main())
