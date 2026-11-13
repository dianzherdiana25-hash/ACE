"""Control-regression Stage 0 — identification replay (HARNESS).

Implements Stage 0 of the design draft in PR #173
(ACE_CONTROL_REGRESSION_DESIGN_DRAFT_20261113.md): reconstruct
band 20261501's control set and frozen admitted catalog from
the v3 run's own checkpoints, then replay arms A/B/C over the
CONTROL set only, x {capped 4000, uncapped}, fully
instrumented, recording per-task outcomes the original run
never recorded.

Instrumentation: operator_discovery._safe_score is wrapped
(counting + recording every scored variant, in order) ONLY
around each solve_task call; solve_task itself is the v3
build's own, unmodified. Returned code's shown score is
computed afterwards with the unwrapped scorer. The wall
guard (60 s/task, signal-based) and the solved() rule
(holdout passes == all cases; a wall overrun counts
unsolved) are the v3 driver's own, mirrored exactly.

REPRODUCTION FENCE (design Stage 0): the capped replay MUST
reproduce the recorded control counts A 34/34, B 32/34,
C 32/34 exactly. If it does not, the replay stops after the
capped configurations and the verdict is ARTIFACT_SUSPECT —
the uncapped configurations are not run.

Outputs (checkpointed per configuration under
ctrlreg-stage0-state/ so a VM replacement loses little):
  evidence/ctrlreg_stage0_replay.json — final record.
Nothing here touches any kernel, gate, or the v3 evidence.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

BASE = Path("/home/hatch/workspace/ace-omega")
sys.path.insert(0, str(BASE / "wt-abcv3/code"))
sys.path.insert(0, str(BASE))

import abc_v3_run as drv  # the v3 driver: split/digest/wall
from ace_operational.grid_adapter import GRID_ADAPTER
from ace_operational.grid_generalization import build_universe
import ace_operational.operator_discovery as od
from ace_operational.operator_discovery import solve_task

SEED = 20261501
CAP = drv.CAP
WALL = drv.WALL_PER_TASK
STATE = BASE / "ctrlreg-stage0-state"
EVIDENCE = BASE / "evidence" / "ctrlreg_stage0_replay.json"
EXPECTED_DIGEST = "a67685635cffb2c20a1c48bedd797b34ab71e93d7325eaae734231036418ee68"
FENCE = {"A": 34, "B": 32, "C": 32}

STATE.mkdir(exist_ok=True)

# --- reconstruct the control set + frozen catalog ----------
universe = build_universe(seed=SEED)
split = drv.split_universe(universe["tasks"])
control = split["control"]
discovery = json.loads(
    (BASE / "abc-v3-run-state" / f"discovery_{SEED}.json")
    .read_text())
keys, chains = drv._extract_admitted(discovery)
digest = drv.catalog_digest(keys, chains)
assert digest == EXPECTED_DIGEST, f"catalog digest {digest}"
assert len(control) == 34, len(control)
print(f"[stage0] control={len(control)} keys={len(keys)} "
      f"chains={len(chains)} digest OK", flush=True)

ARMS = {"A": ((), ()), "B": (tuple(keys), ()),
        "C": (tuple(keys), tuple(chains))}

# --- instrumented _safe_score -------------------------------
_orig_safe_score = od._safe_score
_counter = {"calls": 0, "scored": [], "active": False}


def _counting_safe_score(budget, code, seconds=0.5):
    if _counter["active"]:
        _counter["calls"] += 1
        _counter["scored"].append(
            hashlib.sha256(code.encode("utf-8")).hexdigest())
    return _orig_safe_score(budget, code, seconds)


od._safe_score = _counting_safe_score


def replay_task(task, arm_keys, arm_chains, cap):
    """One instrumented solve. Mirrors drv.solved() exactly,
    plus: score-call count, scored-variant hashes (ordered),
    trace, returned-code hash + shown score."""
    trace: list = []

    def attempt():
        _counter["calls"] = 0
        _counter["scored"] = []
        _counter["active"] = True
        try:
            code = solve_task(task, GRID_ADAPTER, tuple(arm_keys),
                              tuple(arm_chains),
                              max_score_calls=cap, trace=trace)
        finally:
            _counter["active"] = False
        budget = GRID_ADAPTER.make_budget(task)
        shown = _orig_safe_score(budget, code)
        cases = [tuple(c) for c in task["holdout_cases"]]
        npass = GRID_ADAPTER.passes(code, cases,
                                    task["holdout_truth"])
        return {
            "task_id": task["task_id"],
            "solved": npass == len(cases),
            "holdout_passes": npass,
            "holdout_total": len(cases),
            "shown_score": shown,
            "shown_total": len(task["shown_cases"]),
            "score_calls": _counter["calls"],
            "scored_variants": len(_counter["scored"]),
            "cap_hit": cap is not None and _counter["calls"] >= cap,
            "returned_sha256": hashlib.sha256(
                code.encode("utf-8")).hexdigest(),
            "trace": [[kind, repr(payload) if payload else None]
                      for kind, payload in trace],
        }

    outcome, timed_out = drv._run_with_wall(attempt, WALL)
    if timed_out:
        return {"task_id": task["task_id"], "solved": False,
                "timeout": True}
    outcome["timeout"] = False
    return outcome


def run_config(arm, cap):
    name = f"{arm}_{'capped' if cap else 'uncapped'}"
    ckpt = STATE / f"{name}.json"
    records, done_ids = [], set()
    prior_wall = 0.0
    if ckpt.exists():
        prior = json.loads(ckpt.read_text())
        if prior.get("complete"):
            print(f"[stage0] {name}: complete checkpoint, skip",
                  flush=True)
            return prior
        records = prior["records"]
        done_ids = {r["task_id"] for r in records}
        prior_wall = prior.get("wall_seconds", 0.0)
        print(f"[stage0] {name}: resuming, {len(records)} tasks "
              f"already recorded", flush=True)
    arm_keys, arm_chains = ARMS[arm]
    t0 = time.time()
    for task in control:
        if task["task_id"] in done_ids:
            continue
        rec = replay_task(task, arm_keys, arm_chains, cap)
        records.append(rec)
        wall = round(prior_wall + time.time() - t0, 1)
        ckpt.write_text(json.dumps(
            {"arm": arm, "cap": cap, "complete": False,
             "solved": sum(1 for r in records if r["solved"]),
             "total": len(records), "wall_seconds": wall,
             "records": records}, indent=1))
        print(f"[stage0] {name} {rec['task_id']} "
              f"solved={rec['solved']} calls={rec.get('score_calls')}",
              flush=True)
    out = {"arm": arm, "cap": cap, "complete": True,
           "solved": sum(1 for r in records if r["solved"]),
           "total": len(records),
           "wall_seconds": round(prior_wall + time.time() - t0, 1),
           "records": records}
    ckpt.write_text(json.dumps(out, indent=1))
    print(f"[stage0] {name}: {out['solved']}/{out['total']} "
          f"wall={out['wall_seconds']}s", flush=True)
    return out


def main():
    results = {}
    for arm in ("A", "B", "C"):
        results[f"{arm}_capped"] = run_config(arm, CAP)
    fence_ok = all(
        results[f"{arm}_capped"]["solved"] == FENCE[arm]
        for arm in ("A", "B", "C"))
    record = {
        "experiment": "ctrlreg-stage0-replay (design PR #173)",
        "seed": SEED, "catalog_digest": digest,
        "n_keys": len(keys), "n_chains": len(chains),
        "fence_expected_capped": FENCE,
        "fence_reproduced": fence_ok,
        "configurations": {
            name: {"solved": cfg["solved"], "total": cfg["total"],
                   "wall_seconds": cfg["wall_seconds"]}
            for name, cfg in results.items()},
    }
    if not fence_ok:
        record["verdict"] = "ARTIFACT_SUSPECT"
        record["note"] = ("Capped replay did not reproduce the "
                          "recorded 34/32/32; uncapped "
                          "configurations NOT run (design "
                          "Stage 0 fence).")
        EVIDENCE.write_text(json.dumps(record, indent=1))
        print("[stage0] FENCE FAILED -> ARTIFACT_SUSPECT",
              flush=True)
        return
    failed = {}
    for arm in ("B", "C"):
        failed[arm] = sorted(
            r["task_id"] for r in results[f"{arm}_capped"]["records"]
            if not r["solved"])
    record["capped_failed_task_ids"] = failed
    record["same_tasks_B_C"] = failed["B"] == failed["C"]
    for arm in ("A", "B", "C"):
        results[f"{arm}_uncapped"] = run_config(arm, None)
        record["configurations"][f"{arm}_uncapped"] = {
            "solved": results[f"{arm}_uncapped"]["solved"],
            "total": results[f"{arm}_uncapped"]["total"],
            "wall_seconds": results[f"{arm}_uncapped"]["wall_seconds"]}
    record["verdict"] = "REPRODUCED"
    record["note"] = ("Capped replay reproduced 34/32/32 "
                      "exactly; per-task records in "
                      "ctrlreg-stage0-state/. Mechanism "
                      "attribution is Stage 1, not claimed here.")
    EVIDENCE.write_text(json.dumps(record, indent=1))
    print("[stage0] DONE — REPRODUCED", flush=True)


if __name__ == "__main__":
    main()
