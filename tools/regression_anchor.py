"""Regression anchor (HARNESS, not repo code).

Whenever the operator catalog changes, ACE should know
exactly what it lost. This harness runs a FIXED capability
battery — the A/B/C v4 protocol's evaluation split (grid
family), built by the same split construction the
replication guards use — through the extended solver twice:
once restricted to a BASELINE catalog's admitted keys and
chains, once restricted to a CANDIDATE catalog's. It records
per-class solved counts for both and derives the regression /
improvement classes and a verdict as an evidence artifact:

    evidence/regression_anchor_<label>.json
    {battery_id, baseline: {per_class, total, ...},
     candidate: {...}, regressions: [...],
     improvements: [...],
     verdict: REGRESSION_FOUND | NO_REGRESSION}

Solving follows the G4 WITH-arm precedent (g4_arm.py): the
catalog is the whole admitted key/chain set, parsed from the
recorded string forms with ast.literal_eval; a task counts
solved iff the solver's best code passes every holdout case
(the run_discovery solved() rule, including its 5 s passes()
guard). Per-class attribution is by the task's own defects:
single-defect tasks under their class, two-defect tasks
under "mixed".

Catalog specs: "v4" (evidence/operator_discovery_v4.json),
"empty", or a path to a JSON file in either the discovery
evidence shape ({by_class: {cls: {admitted_operators,
admitted_chains}}}) or the materialised catalog artifact
shape ({classes: {cls: {operators, chains}}}).

Battery sizes: "full" = all 29 evaluation tasks; "smoke" =
a stratified round-robin subsample (buckets: the four
single-defect classes, then mixed) capped at --battery-size
tasks (default 16, <= 24). Same code path; only the cap
differs. If baseline and candidate catalogs have the same
digest, the battery is solved once and mirrored (pass
--no-dedupe to force two passes, e.g. to exercise
determinism in the self-test).

--self-test runs the anchor's own acceptance checks on the
smoke battery in one process (one universe build, three
passes): (1) v4 vs v4 with dedupe disabled must give
NO_REGRESSION with identical numbers; (2) v4 vs empty must
give REGRESSION_FOUND with regressions exactly on the
classes the v4 catalog covers on this battery (baseline
solved > 0) and an empty-candidate total of 0.

Code lineage: the v3 solver lift (wt-p1) — module-level
solve_task, behaviour-identical to the v4 protocol's solver.
Override with ACE_CODE_DIR.
"""
import argparse
import ast
import hashlib
import json
import os
import signal
import sys
import time
from pathlib import Path

BASE = Path("/home/hatch/workspace/ace-omega")
CODE_DIR = os.environ.get(
    "ACE_CODE_DIR", str(BASE / "wt-p1" / "code"))
sys.path.insert(0, CODE_DIR)

from ace_operational.grid_adapter import GRID_ADAPTER  # noqa: E402
from ace_operational.grid_generalization import build_universe  # noqa: E402
from ace_operational.operator_discovery import (  # noqa: E402
    _ScoreTimeout, _alarm_handler, solve_task)


def _atomic_write(path, text):
    """Crash-safe write: temp file in the same
    directory, fsync, then os.replace — the PR #181
    pattern generalized (2026-11-13). A host death
    mid-write leaves the old file or the new one,
    never a torn one."""
    import os as _os
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        _os.fsync(fh.fileno())
    _os.replace(tmp, path)


EVIDENCE = BASE / "evidence"
V4_EVIDENCE = EVIDENCE / "operator_discovery_v4.json"
CLASSES = ("bounds_off_by_one", "dist_step_2",
           "returns_start_distance", "wall_char_x")
BUCKETS = CLASSES + ("mixed",)


# ------------------------------------------------------------------
# battery construction — the v4 split, verbatim from the guards
# ------------------------------------------------------------------
def build_battery(size: int | None) -> list[dict]:
    """The v4 evaluation split (per-class first-3 singles to
    the pool, pair pool = first 6 mixed), then the battery:
    all evaluation tasks (size None) or a stratified
    round-robin subsample capped at `size`."""
    universe = build_universe()
    tasks = universe["tasks"]
    new_only = [t for t in tasks if t["subset"] == "new_only"]
    singles = [t for t in new_only if len(t["defects"]) == 1]
    mixed = [t for t in new_only if len(t["defects"]) == 2]
    pool, evaluation = [], []
    per_class_count: dict[str, int] = {}
    for task in singles:
        cls = task["defects"][0]
        per_class_count[cls] = per_class_count.get(cls, 0) + 1
        (pool if per_class_count[cls] <= 3 else evaluation).append(task)
    pool_ids = {t["task_id"] for t in pool}
    evaluation += [t for t in new_only
                   if t["task_id"] not in pool_ids
                   and t not in evaluation]
    pair_pool = mixed[:6]
    pair_ids = {t["task_id"] for t in pair_pool}
    evaluation = [t for t in evaluation if t["task_id"] not in pair_ids]
    if size is None or size >= len(evaluation):
        return evaluation
    buckets: dict[str, list] = {b: [] for b in BUCKETS}
    for task in evaluation:
        buckets[bucket_of(task)].append(task)
    battery, idx = [], 0
    while len(battery) < size:
        progressed = False
        for bucket in BUCKETS:
            if idx < len(buckets[bucket]) and len(battery) < size:
                battery.append(buckets[bucket][idx])
                progressed = True
        idx += 1
        if not progressed:
            break
    return battery


def bucket_of(task) -> str:
    return task["defects"][0] if len(task["defects"]) == 1 else "mixed"


def battery_id_of(battery) -> str:
    ids = "\n".join(t["task_id"] for t in battery)
    return hashlib.sha256(ids.encode()).hexdigest()


# ------------------------------------------------------------------
# catalogs
# ------------------------------------------------------------------
def load_catalog(spec: str):
    """Returns (extra_keys, extra_chains, digest, description)."""
    if spec == "empty":
        keys, chains, desc = [], [], "empty catalog"
    else:
        path = V4_EVIDENCE if spec == "v4" else Path(spec)
        data = json.loads(path.read_text())
        keys, chains = [], []
        if "by_class" in data:
            classes = {cls: {"operators": rec["admitted_operators"],
                             "chains": rec["admitted_chains"]}
                       for cls, rec in data["by_class"].items()}
        elif "classes" in data:
            classes = data["classes"]
        else:
            raise ValueError(f"{path}: neither discovery evidence "
                             "nor catalog artifact shape")
        for cls in sorted(classes):
            for text in classes[cls].get("operators", []):
                key = ast.literal_eval(text)
                if not isinstance(key, tuple):
                    raise ValueError(f"operator key in {cls!r} is "
                                     f"not a tuple: {text!r}")
                keys.append(key)
            for text in classes[cls].get("chains", []):
                chain = ast.literal_eval(text)
                if not isinstance(chain, tuple):
                    raise ValueError(f"chain in {cls!r} is not a "
                                     f"tuple: {text!r}")
                chains.append(chain)
        desc = f"{spec} ({path.name})"
    canonical = json.dumps(
        {"keys": sorted(str(k) for k in keys),
         "chains": sorted(str(c) for c in chains)}, sort_keys=True)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return tuple(keys), tuple(chains), digest, desc


# ------------------------------------------------------------------
# one battery pass under one catalog
# ------------------------------------------------------------------
def run_pass(battery, extra_keys, extra_chains) -> dict:
    per_class = {b: {"tasks": 0, "solved": 0, "solved_ids": []}
                 for b in BUCKETS}
    for task in battery:
        bucket = bucket_of(task)
        per_class[bucket]["tasks"] += 1
        code = solve_task(task, GRID_ADAPTER, extra_keys, extra_chains)
        cases = [tuple(c) for c in task["holdout_cases"]]
        previous = signal.signal(signal.SIGALRM, _alarm_handler)
        signal.setitimer(signal.ITIMER_REAL, 5.0)
        try:
            passed = GRID_ADAPTER.passes(code, cases,
                                         task["holdout_truth"])
        except _ScoreTimeout:
            passed = -1
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
        if passed == len(cases):
            per_class[bucket]["solved"] += 1
            per_class[bucket]["solved_ids"].append(task["task_id"])
    total = sum(v["solved"] for v in per_class.values())
    return {"per_class": per_class, "total": total,
            "tasks": len(battery)}


def compare(battery, base_spec, cand_spec, base_pass, cand_pass,
            base_meta, cand_meta, deduped, wall) -> dict:
    regressions, improvements = [], []
    for bucket in BUCKETS:
        b = base_pass["per_class"][bucket]["solved"]
        c = cand_pass["per_class"][bucket]["solved"]
        if c < b:
            regressions.append(bucket)
        elif c > b:
            improvements.append(bucket)
    return {
        "artifact": "ace.regression_anchor.v1",
        "battery_id": battery_id_of(battery),
        "battery_tasks": [t["task_id"] for t in battery],
        "baseline": {"catalog": base_meta, **base_pass},
        "candidate": {"catalog": cand_meta, **cand_pass},
        "regressions": regressions,
        "improvements": improvements,
        "verdict": "REGRESSION_FOUND" if regressions
                   else "NO_REGRESSION",
        "deduped": deduped,
        "code_dir": CODE_DIR,
        "wall_seconds": round(wall, 1)}


def run_inoculation(cand_keys, registry_path):
    """Distractor-inoculation battery (design:
    ACE_DISTRACTOR_INOCULATION_DESIGN_20261113) run
    against the CANDIDATE catalog's keys. The battery
    module ships next to the registry file. Witnesses
    are the registry's own universe (abc-v3 band
    20261501 control split, reconstructed via the v3
    harness's split — a disclosed harness dependency);
    solving mirrors the Stage 0/1 protocol (cap 4000,
    60 s per-task wall)."""
    import importlib.util
    registry_path = Path(registry_path)
    spec = importlib.util.spec_from_file_location(
        "distractor_inoculation",
        registry_path.parent / "distractor_inoculation.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Load the v3 harness for split_universe/_run_with_wall
    # only. Its top-level scorer import belongs to the
    # wt-abcv3 tree, which is not this process's package
    # tree; stub it (the wiring never calls the scorer).
    import types
    if "ace_operational.abc_v3_scorer" not in sys.modules:
        stub = types.ModuleType("ace_operational.abc_v3_scorer")
        stub.assess_abc_v3 = None
        sys.modules["ace_operational.abc_v3_scorer"] = stub
    dspec = importlib.util.spec_from_file_location(
        "abc_v3_run_wiring", BASE / "abc_v3_run.py")
    drv = importlib.util.module_from_spec(dspec)
    dspec.loader.exec_module(drv)
    from ace_operational.grid_generalization import \
        build_universe
    universe = build_universe(seed=20261501)
    control = {t["task_id"]: t for t in
               drv.split_universe(universe["tasks"])["control"]}

    def solve(task_id, keys):
        task = control[task_id]

        def attempt():
            code = solve_task(task, GRID_ADAPTER, tuple(keys),
                              (), max_score_calls=4000)
            cases = [tuple(c) for c in task["holdout_cases"]]
            return GRID_ADAPTER.passes(
                code, cases, task["holdout_truth"]) == len(cases)

        out, timed_out = drv._run_with_wall(attempt, 60.0)
        return bool(out) and not timed_out

    registry = mod.load_registry(registry_path)
    return mod.run_battery(catalog_keys=list(cand_keys),
                           solve=solve, registry=registry)


def run_anchor(battery, base_spec, cand_spec, label, dedupe=True,
               inoculate_registry=None):
    t0 = time.time()
    b_keys, b_chains, b_digest, b_desc = load_catalog(base_spec)
    c_keys, c_chains, c_digest, c_desc = load_catalog(cand_spec)
    base_meta = {"spec": base_spec, "description": b_desc,
                 "digest": b_digest, "operators": len(b_keys),
                 "chains": len(b_chains)}
    cand_meta = {"spec": cand_spec, "description": c_desc,
                 "digest": c_digest, "operators": len(c_keys),
                 "chains": len(c_chains)}
    base_pass = run_pass(battery, b_keys, b_chains)
    deduped = False
    if dedupe and b_digest == c_digest:
        cand_pass = json.loads(json.dumps(base_pass))
        deduped = True
    else:
        cand_pass = run_pass(battery, c_keys, c_chains)
    out = compare(battery, base_spec, cand_spec, base_pass, cand_pass,
                  base_meta, cand_meta, deduped, time.time() - t0)
    if inoculate_registry:
        out["inoculation"] = run_inoculation(
            c_keys, inoculate_registry)
    dest = EVIDENCE / f"regression_anchor_{label}.json"
    _atomic_write(dest, json.dumps(out, indent=1))
    return out, dest


# ------------------------------------------------------------------
# self-test
# ------------------------------------------------------------------
def self_test(battery_size: int) -> int:
    battery = build_battery(battery_size)
    print(f"smoke battery: {len(battery)} tasks, "
          f"id {battery_id_of(battery)[:16]}...")
    ok = True
    # (1) identical catalogs, dedupe OFF: two real passes
    same, dest1 = run_anchor(battery, "v4", "v4",
                             "selftest-identical", dedupe=False)
    identical = (same["baseline"]["per_class"]
                 == same["candidate"]["per_class"]
                 and same["baseline"]["total"]
                 == same["candidate"]["total"])
    print(f"[1] v4 vs v4: verdict={same['verdict']} "
          f"identical_numbers={identical} "
          f"total={same['baseline']['total']}/{len(battery)} "
          f"wall={same['wall_seconds']}s -> {dest1.name}")
    ok &= identical and same["verdict"] == "NO_REGRESSION" \
        and not same["regressions"]
    # (2) empty candidate
    diff, dest2 = run_anchor(battery, "v4", "empty",
                             "selftest-empty")
    covered = sorted(b for b in BUCKETS
                     if diff["baseline"]["per_class"][b]["solved"] > 0)
    print(f"[2] v4 vs empty: verdict={diff['verdict']} "
          f"candidate_total={diff['candidate']['total']} "
          f"regressions={diff['regressions']} "
          f"covered={covered} wall={diff['wall_seconds']}s "
          f"-> {dest2.name}")
    ok &= (diff["verdict"] == "REGRESSION_FOUND"
           and diff["candidate"]["total"] == 0
           and sorted(diff["regressions"]) == covered)
    print("SELF-TEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", default="v4")
    ap.add_argument("--candidate", default="v4")
    ap.add_argument("--label", default="run")
    ap.add_argument("--battery", default="smoke",
                    help="'full', 'smoke', or an integer cap")
    ap.add_argument("--battery-size", type=int, default=16,
                    help="smoke cap (default 16, must be <= 24)")
    ap.add_argument("--no-dedupe", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--inoculate", action="store_true",
                    help="also run the distractor-inoculation "
                         "battery against the candidate catalog")
    ap.add_argument("--registry", default=None,
                    help="path to distractor_registry.json "
                         "(required with --inoculate; the "
                         "battery module ships next to it)")
    args = ap.parse_args()
    if args.battery_size > 24:
        ap.error("--battery-size must be <= 24 (smoke fence)")
    if args.self_test:
        return self_test(args.battery_size)
    size = None if args.battery == "full" else (
        args.battery_size if args.battery == "smoke"
        else int(args.battery))
    battery = build_battery(size)
    if args.inoculate and not args.registry:
        ap.error("--inoculate requires --registry")
    out, dest = run_anchor(
        battery, args.baseline, args.candidate, args.label,
        dedupe=not args.no_dedupe,
        inoculate_registry=args.registry if args.inoculate
        else None)
    print(f"battery {len(battery)} tasks "
          f"({out['battery_id'][:16]}...): "
          f"baseline {out['baseline']['total']} -> "
          f"candidate {out['candidate']['total']}; "
          f"regressions={out['regressions']} "
          f"improvements={out['improvements']}; "
          f"verdict={out['verdict']}; wall={out['wall_seconds']}s")
    if "inoculation" in out:
        print(f"inoculation: overall="
              f"{out['inoculation']['overall']}")
    print("saved:", dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
