"""A/B/C v3 run driver (HARNESS, not repo code).

Runs the preregistered v3 pilot (draft
ACE_ABC_V3_PREREGISTRATION_DRAFT_20261113.md) once the
preregistration is submitted — per band 20261501 /
20261502 / 20261503:

  build_universe -> census split -> run_discovery ONCE
  over the pool -> freeze admitted catalog + chains +
  digest -> arms A/B/C via solve_task (shared cap 4000
  score calls, 60 s/task wall via a signal guard;
  exceeding the wall counts the task unsolved for that
  arm and is listed, never a silent abstain) -> solved
  sets per task + S2-usage traces (distinct admitted
  keys in a B-solve trace >= 2) -> DI per band + pooled
  via the DI scorer -> evidence/abc_v3_run.json.

THIS DRIVER IS NOT RUN ON THE RUN BANDS in the build
track (midday track (a)): executing it on bands
20261501-20261503 IS the gate run, which needs a
submitted preregistration. The unit tests in
test_abc_v3_run.py exercise the split, the trace hook
on a synthetic task, the wall guard, and the DI
computation — never a real band.

solve_task returns a code STRING, never a bool: a task
is solved iff that code passes ALL holdout cases via
adapter.passes(...) (the census wrapper; the boolean-
string bug voided the first band-2 calibration run).
"""
import ast
import hashlib
import json
import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, "/home/hatch/workspace/ace-omega/wt-abcv3/code")

from ace_operational.abc_v3_scorer import assess_abc_v3
from ace_operational.grid_adapter import GRID_ADAPTER
from ace_operational.grid_generalization import build_universe
from ace_operational.operator_discovery import (
    run_discovery, solve_task)

CAP = 4000
WALL_PER_TASK = 60.0
BANDS = (20261501, 20261502, 20261503)
EVIDENCE_PATH = Path("/home/hatch/workspace/ace-omega/evidence/"
                     "abc_v3_run.json")
STATE_DIR = Path("/home/hatch/workspace/ace-omega/abc-v3-run-state")


# --- Incremental checkpointing (added 2026-11-13 after
# invocation 1 of abc-v3-01 was VOIDED by a VM replacement:
# the driver held every result in memory until the final
# write and ~100 CPU-minutes were lost. Persistence only —
# no measurement code changes; see
# evidence/abc_v3_run_notes.json.) ---

def _tuples_out(obj):
    """Recursively encode tuples so JSON round-trips them."""
    if isinstance(obj, tuple):
        return {"__tuple__": [_tuples_out(x) for x in obj]}
    if isinstance(obj, list):
        return [_tuples_out(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _tuples_out(v) for k, v in obj.items()}
    return obj


def _tuples_in(obj):
    if isinstance(obj, dict) and set(obj) == {"__tuple__"}:
        return tuple(_tuples_in(x) for x in obj["__tuple__"])
    if isinstance(obj, list):
        return [_tuples_in(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _tuples_in(v) for k, v in obj.items()}
    return obj


def _atomic_write(path, text):
    """Crash-safe write: temp file in the same
    directory, fsync, then os.replace. A host death
    mid-write (this VM rebooted five times on
    2026-11-13) leaves either the old file or the new
    one, never a torn one — the transactional
    discipline of harvest #6 §2 applied to the
    driver's own state."""
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _save_checkpoint(name, obj):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_write(STATE_DIR / name,
                  json.dumps(_tuples_out(obj), indent=1))


def _load_checkpoint(name):
    path = STATE_DIR / name
    if not path.exists():
        return None
    return _tuples_in(json.loads(path.read_text()))


def _heartbeat(**fields):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    fields["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _atomic_write(STATE_DIR / "heartbeat.json",
                  json.dumps(fields, indent=1))


class _TaskTimeout(Exception):
    pass


def _alarm_handler(signum, frame):
    raise _TaskTimeout()


def _run_with_wall(fn, wall_seconds):
    """Run fn() under a wall clock. Returns (result,
    timed_out). Signal-based, main thread only — the
    same discipline as run_discovery's solved()."""
    previous = signal.signal(signal.SIGALRM, _alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, wall_seconds)
    try:
        return fn(), False
    except _TaskTimeout:
        return None, True
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def split_universe(tasks):
    """The census split, verbatim (v3_census.py): pool =
    first 3 singles per defect class; evaluation = the
    rest of new_only (singles + mixed) minus the pair
    pool; pair_pool = first 6 mixed; control =
    catalog_control."""
    new_only = [t for t in tasks if t["subset"] == "new_only"]
    singles = [t for t in new_only if len(t["defects"]) == 1]
    mixed = [t for t in new_only if len(t["defects"]) == 2]
    pool, evaluation = [], []
    per_class: dict[str, int] = {}
    for task in singles:
        cls = task["defects"][0]
        per_class[cls] = per_class.get(cls, 0) + 1
        (pool if per_class[cls] <= 3 else evaluation).append(task)
    pool_ids = {t["task_id"] for t in pool}
    evaluation += [t for t in new_only
                   if t["task_id"] not in pool_ids
                   and t not in evaluation]
    pair_pool = mixed[:6]
    pair_ids = {t["task_id"] for t in pair_pool}
    evaluation = [t for t in evaluation
                  if t["task_id"] not in pair_ids]
    control = [t for t in tasks
               if t["subset"] == "catalog_control"]
    return {"pool": pool, "evaluation": evaluation,
            "pair_pool": pair_pool, "control": control}


def solved(task, adapter, keys=(), chains=(), trace=None,
           cap=CAP, wall=WALL_PER_TASK):
    """The census's solved() wrapper: solve_task's code
    string passes ALL holdout cases. Returns
    {"solved": bool, "timeout": bool}. A wall overrun
    counts the task unsolved for that arm."""
    def attempt():
        code = solve_task(task, adapter, tuple(keys),
                          tuple(chains), max_score_calls=cap,
                          trace=trace)
        cases = [tuple(c) for c in task["holdout_cases"]]
        return adapter.passes(code, cases,
                              task["holdout_truth"]) == len(cases)

    outcome, timed_out = _run_with_wall(attempt, wall)
    return {"solved": bool(outcome) if not timed_out else False,
            "timeout": timed_out}


def catalog_digest(keys, chains):
    """Deterministic digest of the frozen admitted
    catalog + chains (order-insensitive)."""
    payload = json.dumps(
        {"keys": sorted(repr(k) for k in keys),
         "chains": sorted(repr(c) for c in chains)},
        sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def distinct_keys_in_trace(trace):
    """Distinct admitted keys applied in a solve trace:
    ("key", k) entries directly, ("chain", chain)
    entries expanded to the chain's constituent keys.
    ("baseline", None) entries contribute nothing."""
    found = set()
    for entry in trace or []:
        kind, payload = entry
        if kind == "key":
            found.add(payload)
        elif kind == "chain":
            found.update(payload)
    return found


def s2_usage(task_traces):
    """S2 usage stratum (draft §5): task ids whose
    B-solve trace applies >= 2 distinct admitted keys
    in sequence. Telemetry, not a gate."""
    return sorted(tid for tid, trace in task_traces.items()
                  if len(distinct_keys_in_trace(trace)) >= 2)


def band_report(counts, control_counts, gate_passed, complete=True):
    """Assemble the scorer report from solve counts and
    score it. counts/control_counts map arm -> (solved,
    total)."""
    arms = {arm: 100.0 * solved_n / max(total, 1)
            for arm, (solved_n, total) in counts.items()}
    control = {arm: 100.0 * solved_n / max(total, 1)
               for arm, (solved_n, total) in control_counts.items()}
    return assess_abc_v3(report={
        "arms": arms, "control": control,
        "calibration_gate_passed": gate_passed,
        "complete": complete})


def _extract_admitted(report):
    keys, chains = [], []
    for block in report["by_class"].values():
        for raw in block.get("admitted_operators", []):
            key = ast.literal_eval(raw)
            if key not in keys:
                keys.append(key)
        for raw in block.get("admitted_chains", []):
            chain = ast.literal_eval(raw)
            if chain not in chains:
                chains.append(chain)
    return keys, chains


def run_band(seed):
    """One run band: discovery once, three arms, DI.
    Returns the band's record (JSON-serializable).
    Discovery and each arm are checkpointed under
    STATE_DIR and resumed when present (see the
    checkpointing note at STATE_DIR)."""
    t0 = time.time()
    universe = build_universe(seed=seed)
    split = split_universe(universe["tasks"])
    pool, evaluation = split["pool"], split["evaluation"]
    control = split["control"]
    _heartbeat(band=seed, phase="discovery")
    discovery = _load_checkpoint(f"discovery_{seed}.json")
    if discovery is None:
        discovery = run_discovery(pool=pool, evaluation=evaluation,
                                  control=control,
                                  pair_pool=split["pair_pool"],
                                  chain_pool=split["pair_pool"],
                                  adapter=GRID_ADAPTER)
        _save_checkpoint(f"discovery_{seed}.json", discovery)
    keys, chains = _extract_admitted(discovery)
    digest = catalog_digest(keys, chains)

    counts: dict[str, list[int]] = {}
    control_counts: dict[str, list[int]] = {}
    timeouts: dict[str, list[str]] = {}
    per_task: dict[str, dict] = {}
    b_traces: dict[str, list] = {}
    arms = {"A": ((), ()), "B": (tuple(keys), ()),
            "C": (tuple(keys), tuple(chains))}
    for arm, (arm_keys, arm_chains) in arms.items():
        _heartbeat(band=seed, phase=f"arm_{arm}")
        saved = _load_checkpoint(f"arm_{seed}_{arm}.json")
        if saved is not None:
            counts[arm] = saved["counts"]
            control_counts[arm] = saved["control_counts"]
            timeouts[arm] = saved["timeouts"]
            # Additive (first-usefulness milestone,
            # 2026-11-13): per-task results recorded by
            # default. Checkpoints written before the
            # milestone carry no per_task key -> {}.
            per_task[arm] = saved.get("per_task", {})
            if arm == "B":
                b_traces = saved["b_traces"]
            continue
        solved_n = 0
        timeouts[arm] = []
        arm_traces: dict[str, list] = {}
        eval_per_task: dict[str, dict] = {}
        for task in evaluation:
            trace: list = []
            result = solved(task, GRID_ADAPTER, arm_keys,
                            arm_chains, trace=trace)
            eval_per_task[task["task_id"]] = {
                "solved": bool(result["solved"]),
                "timeout": bool(result["timeout"])}
            if result["timeout"]:
                timeouts[arm].append(task["task_id"])
            if result["solved"]:
                solved_n += 1
                if arm == "B":
                    arm_traces[task["task_id"]] = trace
        counts[arm] = [solved_n, len(evaluation)]
        ctrl_n = 0
        ctrl_per_task: dict[str, dict] = {}
        for task in control:
            result = solved(task, GRID_ADAPTER, arm_keys,
                            arm_chains)
            ctrl_per_task[task["task_id"]] = {
                "solved": bool(result["solved"]),
                "timeout": bool(result["timeout"])}
            if result["timeout"]:
                timeouts[arm].append(task["task_id"])
            if result["solved"]:
                ctrl_n += 1
        control_counts[arm] = [ctrl_n, len(control)]
        per_task[arm] = {"evaluation": eval_per_task,
                         "control": ctrl_per_task}
        if arm == "B":
            b_traces = arm_traces
        _save_checkpoint(f"arm_{seed}_{arm}.json", {
            "counts": counts[arm],
            "control_counts": control_counts[arm],
            "timeouts": timeouts[arm],
            "per_task": per_task[arm],
            "b_traces": arm_traces if arm == "B" else {}})

    # Calibration re-check on this band's own numbers
    # (draft §3): arm A pooled over evaluation + control.
    pooled_a = (counts["A"][0] + control_counts["A"][0]) / max(
        counts["A"][1] + control_counts["A"][1], 1)
    gate_passed = 0.10 < pooled_a < 0.90
    assessment = band_report(
        {arm: tuple(v) for arm, v in counts.items()},
        {arm: tuple(v) for arm, v in control_counts.items()},
        gate_passed)
    return {
        "seed": seed,
        "pool": len(pool), "evaluation": len(evaluation),
        "control": len(control),
        "admitted_keys": len(keys), "admitted_chains": len(chains),
        "catalog_digest": digest,
        "counts": counts, "control_counts": control_counts,
        "per_task": per_task,
        "timeouts": timeouts,
        "s2_usage_task_ids": s2_usage(b_traces),
        "s2_usage_n": len(s2_usage(b_traces)),
        "calibration_gate_passed": gate_passed,
        "arm_A_pooled_rate": pooled_a,
        "assessment": assessment,
        "wall_seconds": round(time.time() - t0, 1),
    }


def run_all(bands=BANDS, evidence_path=EVIDENCE_PATH):
    """All three bands + pooled DI. Writes the evidence
    file. A band that raises is recorded as failed and
    the pooled report is INCONCLUSIVE (complete False),
    never silently completed."""
    t0 = time.time()
    band_records = []
    failures = []
    _heartbeat(band=None, phase="run_all_start",
               bands_total=len(bands))
    for seed in bands:
        saved_band = _load_checkpoint(f"band_{seed}.json")
        if saved_band is not None:
            band_records.append(saved_band)
            _heartbeat(band=seed, phase="band_resumed",
                       bands_done=len(band_records))
            continue
        try:
            record = run_band(seed)
            band_records.append(record)
            _save_checkpoint(f"band_{seed}.json", record)
            _heartbeat(band=seed, phase="band_done",
                       bands_done=len(band_records))
        except Exception as exc:  # noqa: BLE001 - recorded, not hidden
            failures.append({"seed": seed,
                             "error": f"{type(exc).__name__}: {exc}"})
    complete = not failures and len(band_records) == len(bands)
    pooled_counts: dict[str, list[int]] = {}
    pooled_control: dict[str, list[int]] = {}
    for arm in ("A", "B", "C"):
        pooled_counts[arm] = [
            sum(r["counts"][arm][0] for r in band_records),
            sum(r["counts"][arm][1] for r in band_records)]
        pooled_control[arm] = [
            sum(r["control_counts"][arm][0] for r in band_records),
            sum(r["control_counts"][arm][1] for r in band_records)]
    pooled_a = (pooled_counts["A"][0] + pooled_control["A"][0]) / max(
        pooled_counts["A"][1] + pooled_control["A"][1], 1)
    pooled_gate = 0.10 < pooled_a < 0.90
    pooled_assessment = band_report(
        {arm: tuple(v) for arm, v in pooled_counts.items()},
        {arm: tuple(v) for arm, v in pooled_control.items()},
        pooled_gate, complete=complete)
    out = {
        "experiment": "abc-v3-01",
        "bands": list(bands),
        "score_call_cap": CAP,
        "wall_per_task_seconds": WALL_PER_TASK,
        "band_records": band_records,
        "band_failures": failures,
        "pooled_counts": pooled_counts,
        "pooled_control_counts": pooled_control,
        "pooled_calibration_gate_passed": pooled_gate,
        "pooled_assessment": pooled_assessment,
        "complete": complete,
        "wall_seconds": round(time.time() - t0, 1),
    }
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(out, indent=1))
    _heartbeat(band=None, phase="complete", complete=complete)
    return out


def main():
    out = run_all()
    print(json.dumps({
        "complete": out["complete"],
        "pooled_overall":
            out["pooled_assessment"]["overall"],
        "pooled_DI":
            out["pooled_assessment"]["differentiation_index_pp"],
        "per_band": [
            {"seed": r["seed"],
             "overall": r["assessment"]["overall"],
             "DI": r["assessment"]["differentiation_index_pp"]}
            for r in out["band_records"]],
        "wall_seconds": out["wall_seconds"],
    }, indent=1))
    print("saved:", EVIDENCE_PATH)


if __name__ == "__main__":
    main()
