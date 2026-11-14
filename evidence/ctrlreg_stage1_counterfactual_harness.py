"""Control-regression Stage 1 — counterfactual separation
(HARNESS). Implements Stage 1 of the design draft in PR #173
for the two tasks Stage 0 identified (catalog_control-020,
catalog_control-021; evidence PR #174):

  Axis 1 (distractor / leave-one-out): re-solve both tasks
  under arm B's frozen catalog minus, in turn, each key that
  appears in the Stage 0 failing traces, and minus all of
  them together. Restoration under a single-key removal
  makes that key causally necessary for the failure.
  Axis 2 (order): re-solve both tasks under 8 deterministic
  permutations of the admitted-key order (same set).
  Outcome flips across permutations with an unchanged
  scored-variant multiset are the design's M3 signature.
  Cross-cutting: in every run, record whether arm A's
  winning code (hash from Stage 0's A records) was among
  the variants the enriched walk actually SCORED — the
  M1b frontier-starvation test — plus the scored-variant
  multiset hash for cross-run comparison.

Attribution is mechanical, per the design's signatures
(M1a already dead at Stage 0: cap never hit, capped ==
uncapped; M2's named signature — shown-perfect returned
code failing holdout — was absent at Stage 0):
  - LOO(single key) restores AND A-solution was scored in
    the full-catalog walk -> M1b (frontier starvation
    under bounded loop, distractor-triggered).
  - LOO(single key) restores AND A-solution never scored
    -> distractor diversion (search-path), reported as
    M2-diversion (named interaction of M2's distractor
    role with the bounded walk; NOT M2's Stage-0 signature,
    which was absent).
  - No LOO restores, permutations flip the outcome with
    the same scored multiset -> M3.
  - Anything else -> UNATTRIBUTED, pattern described.
Checkpointed per experiment under ctrlreg-stage1-state/.
Nothing touches any kernel or gate.
"""
import hashlib
import json
import random
import sys
import time
from pathlib import Path

BASE = Path("/home/hatch/workspace/ace-omega")
sys.path.insert(0, str(BASE / "wt-abcv3/code"))
sys.path.insert(0, str(BASE))

import abc_v3_run as drv
from ace_operational.grid_adapter import GRID_ADAPTER
from ace_operational.grid_generalization import build_universe
import ace_operational.operator_discovery as od
from ace_operational.operator_discovery import solve_task

SEED = 20261501
CAP = drv.CAP
WALL = drv.WALL_PER_TASK
TASKS = ("catalog_control-020", "catalog_control-021")
STATE = BASE / "ctrlreg-stage1-state"
EVIDENCE = BASE / "evidence" / "ctrlreg_stage1_counterfactual.json"
STATE.mkdir(exist_ok=True)

universe = build_universe(seed=SEED)
split = drv.split_universe(universe["tasks"])
control = {t["task_id"]: t for t in split["control"]}
discovery = json.loads(
    (BASE / "abc-v3-run-state" / f"discovery_{SEED}.json")
    .read_text())
keys, chains = drv._extract_admitted(discovery)
assert drv.catalog_digest(keys, chains) == \
    "a67685635cffb2c20a1c48bedd797b34ab71e93d7325eaae734231036418ee68"

a_records = {r["task_id"]: r for r in json.loads(
    (BASE / "ctrlreg-stage0-state" / "A_capped.json")
    .read_text())["records"]}
A_WIN = {t: a_records[t]["returned_sha256"] for t in TASKS}

_orig = od._safe_score
_rec = {"active": False, "hashes": []}


def _recording(budget, code, seconds=0.5):
    if _rec["active"]:
        _rec["hashes"].append(
            hashlib.sha256(code.encode("utf-8")).hexdigest())
    return _orig(budget, code, seconds)


od._safe_score = _recording


def solve_instr(task, arm_keys, arm_chains=()):
    trace: list = []

    def attempt():
        _rec["hashes"] = []
        _rec["active"] = True
        try:
            code = solve_task(task, GRID_ADAPTER, tuple(arm_keys),
                              tuple(arm_chains),
                              max_score_calls=CAP, trace=trace)
        finally:
            _rec["active"] = False
        budget = GRID_ADAPTER.make_budget(task)
        shown = _orig(budget, code)
        cases = [tuple(c) for c in task["holdout_cases"]]
        npass = GRID_ADAPTER.passes(code, cases,
                                    task["holdout_truth"])
        scored = _rec["hashes"]
        return {
            "task_id": task["task_id"],
            "solved": npass == len(cases),
            "score_calls": len(scored),
            "shown_score": shown,
            "shown_total": len(task["shown_cases"]),
            "returned_sha256": hashlib.sha256(
                code.encode("utf-8")).hexdigest(),
            "a_solution_scored": A_WIN[task["task_id"]] in scored,
            "scored_multiset_sha256": hashlib.sha256(
                "".join(sorted(scored)).encode()).hexdigest(),
            "n_scored": len(scored),
            "trace": [[k, repr(p) if p else None]
                      for k, p in trace],
        }

    out, timed_out = drv._run_with_wall(attempt, WALL)
    if timed_out:
        return {"task_id": task["task_id"], "solved": False,
                "timeout": True}
    out["timeout"] = False
    return out


def run_experiment(name, arm_keys, arm_chains=()):
    ckpt = STATE / f"{name}.json"
    if ckpt.exists():
        print(f"[stage1] {name}: checkpoint, skip", flush=True)
        return json.loads(ckpt.read_text())
    t0 = time.time()
    recs = {t: solve_instr(control[t], arm_keys, arm_chains)
            for t in TASKS}
    out = {"experiment": name, "wall_seconds": round(
        time.time() - t0, 1), "records": recs}
    ckpt.write_text(json.dumps(out, indent=1))
    print(f"[stage1] {name}: " + "; ".join(
        f"{t} solved={r['solved']} calls={r.get('score_calls')} "
        f"a_scored={r.get('a_solution_scored')}"
        for t, r in recs.items()), flush=True)
    return out


def main():
    results = {}
    results["full_B"] = run_experiment("full_B", keys)
    # trace keys (Stage 0): the name_swap permutation keys
    trace_keys = set()
    for cfg in ("B_capped",):
        d = json.loads((BASE / "ctrlreg-stage0-state"
                        / f"{cfg}.json").read_text())
        for r in d["records"]:
            if r["task_id"] in TASKS:
                for kind, payload in r["trace"]:
                    if kind == "key":
                        trace_keys.add(payload)
    print(f"[stage1] trace keys: {sorted(trace_keys)}",
          flush=True)
    loo_names = {}
    for i, raw in enumerate(sorted(trace_keys)):
        k = eval(raw)  # repr of the key tuple, from our own records
        loo_names[raw] = run_experiment(
            f"loo_{i}", [x for x in keys if x != k])
    remaining = [x for x in keys
                 if repr(x) not in trace_keys]
    results["loo_all_trace_keys"] = run_experiment(
        "loo_all_trace_keys", remaining)
    rng = random.Random(20261113)
    perms = {}
    for i in range(8):
        perm = keys[:]
        rng.shuffle(perm)
        perms[f"perm_{i}"] = run_experiment(f"perm_{i}", perm)
    record = {
        "experiment": "ctrlreg-stage1-counterfactual (PR #173)",
        "tasks": list(TASKS),
        "a_winning_returned_sha256": A_WIN,
        "full_B": results["full_B"]["records"],
        "loo_by_trace_key": {raw: r["records"] for raw, r
                             in loo_names.items()},
        "loo_all_trace_keys": results["loo_all_trace_keys"]
        ["records"],
        "permutations": {n: r["records"] for n, r in perms
                         .items()},
    }
    EVIDENCE.write_text(json.dumps(record, indent=1))
    print("[stage1] DONE — evidence written", flush=True)


if __name__ == "__main__":
    main()
