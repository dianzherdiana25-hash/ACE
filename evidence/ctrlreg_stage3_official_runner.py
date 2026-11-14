"""ACE Ω — OFFICIAL Stage 3 run (control-regression).

Authority: preregistration draft PR #184 as ratified
internally (PR #173 §16, hub act 2026-11-13 22:45 WIB):
bands 20261601–20261603; arms S (6/4) / R (12/4) /
F (6/8), uncapped; conditions clean x infected;
recovery = solved (§8(c)); per-task recording from
the start (milestone K1 pattern); atomic checkpoint
writes (PR #187 pattern).

Disclosed readings where texts differed:
- Infected construction follows the DRAFT §2.3
  operational form (registered 'nc' key injected at
  the END of the band's admitted catalog — the
  inoculation battery's injection form). The §16
  ratification's summary wording ("natural admission
  position") is experimentally indistinguishable on
  the record: Stage 1 measured the order axis inert
  (8/8 permutations, byte-identical scored
  multisets) and Stage 2 showed presence, not
  position, is the step variable.
- The 3x cost rule follows the HUB ACT's form
  (a per-task ceiling on infected cells = 3x the
  same band's clean-S median score calls, overruns
  recorded cost_abort — never solved/failed),
  superseding the draft §2.5 reporting-only form;
  both medians are recorded so the §2.5 reading
  remains computable from this record.

Prerequisites executed before any fresh band:
(a) the §2.6 harness extension (per-round frontier
    provenance in the round log) — harness_ext.py;
(b) re-gate of the extended harness on the
    development witnesses (separate record,
    dev_regate) — gate PASS + uncapped control
    reproduction required, else this run does not
    start.
Per band (§2.2): the logging-invariance gate is
re-run on the band's first two control tasks before
the band's cells are read; a gate failure voids
the band (stop, record, report).
"""
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = Path("/home/hatch/workspace/ace-omega")
sys.path.insert(0, str(BASE / "wt-abcv3/code"))
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(HERE))

import abc_v3_run as drv
import harness_ext as hx
from ace_operational.grid_adapter import GRID_ADAPTER
from ace_operational.grid_generalization import build_universe
from ace_operational.operator_discovery import solve_task
import ace_operational.operator_discovery as od

BANDS = (20261601, 20261602, 20261603)
NC_KEY = ("name_swap", (5, 2, 3, 0, 1, 4), "nc")
CAP = drv.CAP
WALL = drv.WALL_PER_TASK
STATE = HERE / "state"
STATE.mkdir(exist_ok=True)
EVIDENCE = HERE / "stage3_official_record.json"
ARMS = {"S": {"rounds": 6, "frontier_width": 4},
        "R": {"rounds": 12, "frontier_width": 4},
        "F": {"rounds": 6, "frontier_width": 8}}


def _atomic_write(path, text):
    import os as _os
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        _os.fsync(fh.fileno())
    _os.replace(tmp, path)


def _save(name, obj):
    _atomic_write(STATE / name,
                  json.dumps(drv._tuples_out(obj), indent=1))


def _load(name):
    p = STATE / name
    if not p.exists():
        return None
    return drv._tuples_in(json.loads(p.read_text()))


def _sha(code):
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def solve_rec(task, keys, *, rounds, frontier_width, cap,
              target_sha=None, with_log=True):
    """One instrumented solve (mirrors the prep
    harness's run_solve, generalised: target sha and
    cost ceiling are parameters)."""
    trace: list = []
    round_log: list = []

    def attempt():
        hx._rec["hashes"] = []
        hx._rec["active"] = True
        try:
            code, info = hx.solve_task_param(
                task, GRID_ADAPTER, tuple(keys), (),
                max_score_calls=cap, rounds=rounds,
                frontier_width=frontier_width, trace=trace,
                round_log=round_log if with_log else None,
                true_path_sha=target_sha)
        finally:
            hx._rec["active"] = False
        budget = GRID_ADAPTER.make_budget(task)
        shown = hx._orig_safe_score(budget, code)
        cases = [tuple(c) for c in task["holdout_cases"]]
        npass = GRID_ADAPTER.passes(
            code, cases, task["holdout_truth"])
        rec = {
            "task_id": task["task_id"],
            "solved": npass == len(cases),
            "holdout_passes": npass,
            "holdout_total": len(cases),
            "shown_score": shown,
            "score_calls": len(hx._rec["hashes"]),
            "returned_sha256": _sha(code),
            "termination": info["termination"],
            "trace": [[k, repr(p) if p else None]
                      for k, p in trace],
        }
        assert info["score_calls_internal"] == \
            rec["score_calls"]
        if with_log:
            rec["round_log"] = [
                {k: e[k] for k in (
                    "round", "n_candidates_generated",
                    "n_scored", "cap_break",
                    "best_score_after", "frontier_size",
                    "frontier_cutoff_score", "true_path",
                    "frontier_provenance") if k in e}
                for e in round_log]
            if target_sha is not None:
                rec["true_path_classification"] = \
                    hx.classify_true_path(
                        round_log, rec["returned_sha256"],
                        target_sha)
        return rec

    out, timed_out = drv._run_with_wall(attempt, WALL)
    if timed_out:
        return {"task_id": task["task_id"], "solved": False,
                "timeout": True, "score_calls": None,
                "termination": "wall_timeout"}
    out["timeout"] = False
    return out


def band_gate(band, control_tasks, keys):
    """§2.2 per-band gate: first two control tasks,
    stock vs param (no-log / log) at defaults, capped."""
    ck = _load(f"gate_{band}.json")
    if ck is not None:
        return ck
    comparisons = []
    ok_all = True
    for task in control_tasks[:2]:
        modes = {}
        trace_s: list = []
        code = solve_task(task, GRID_ADAPTER, tuple(keys), (),
                          max_score_calls=CAP, trace=trace_s)
        budget = GRID_ADAPTER.make_budget(task)
        cases = [tuple(c) for c in task["holdout_cases"]]
        modes["stock"] = {
            "returned_sha256": _sha(code),
            "solved": GRID_ADAPTER.passes(
                code, cases, task["holdout_truth"]) == len(cases),
            "trace": [[k, repr(p) if p else None]
                      for k, p in trace_s]}
        # stock score_calls are not recorder-visible in
        # this flavour; the prep gate compared via its
        # own wrapper — here param modes carry the count
        # comparison and stock carries sha/solved/trace.
        for name, wl in (("param_nolog", False),
                         ("param_log", True)):
            r = solve_rec(task, keys, rounds=6,
                          frontier_width=4, cap=CAP,
                          with_log=wl)
            modes[name] = r
        same = (
            modes["stock"]["returned_sha256"]
            == modes["param_nolog"]["returned_sha256"]
            == modes["param_log"]["returned_sha256"]
            and modes["stock"]["solved"]
            == modes["param_nolog"]["solved"]
            == modes["param_log"]["solved"]
            and modes["stock"]["trace"]
            == modes["param_log"]["trace"]
            and modes["param_nolog"]["score_calls"]
            == modes["param_log"]["score_calls"])
        ok_all = ok_all and same
        comparisons.append({
            "task_id": task["task_id"], "identical": same,
            "returned_sha256":
                modes["param_log"]["returned_sha256"],
            "solved": modes["param_log"]["solved"],
            "score_calls": modes["param_log"]["score_calls"]})
        print(f"[stage3] band {band} gate "
              f"{task['task_id']}: identical={same}",
              flush=True)
    out = {"band": band,
           "verdict": "PASS" if ok_all else "FAIL",
           "comparisons": comparisons}
    _save(f"gate_{band}.json", out)
    return out


def run_cell(band, condition, arm, tasks, keys, ceiling,
             targets=None):
    name = f"cell_{band}_{condition}_{arm}.json"
    ck = _load(name)
    if ck is not None:
        print(f"[stage3] {name}: checkpoint, skip", flush=True)
        return ck
    cfg = ARMS[arm]
    t0 = time.time()
    recs = {}
    for task in tasks:
        cap = ceiling if condition == "infected" else None
        r = solve_rec(
            task, keys, rounds=cfg["rounds"],
            frontier_width=cfg["frontier_width"], cap=cap,
            target_sha=(targets or {}).get(task["task_id"])
            if (condition == "infected" and arm == "S")
            else None)
        if condition == "infected" and ceiling is not None \
                and not r["solved"] \
                and r["score_calls"] is not None \
                and r["score_calls"] >= ceiling:
            r["cost_abort"] = True
            r["termination_effective"] = "cost_abort"
        else:
            r["cost_abort"] = False
            r["termination_effective"] = r["termination"]
        recs[task["task_id"]] = r
    out = {"band": band, "condition": condition, "arm": arm,
           "config": cfg, "ceiling": ceiling,
           "wall_seconds": round(time.time() - t0, 1),
           "solved_count": sum(1 for r in recs.values()
                               if r["solved"]),
           "total": len(recs), "records": recs}
    _save(name, out)
    print(f"[stage3] band {band} {condition} {arm}: "
          f"{out['solved_count']}/{out['total']} "
          f"wall={out['wall_seconds']}s", flush=True)
    return out


def run_band(band):
    ck = _load(f"band_{band}.json")
    if ck is not None:
        print(f"[stage3] band {band}: complete, skip",
              flush=True)
        return ck
    t0 = time.time()
    universe = build_universe(seed=band)
    split = drv.split_universe(universe["tasks"])
    pool, evaluation = split["pool"], split["evaluation"]
    control_tasks = sorted(split["control"],
                           key=lambda t: t["task_id"])
    disc = _load(f"discovery_{band}.json")
    if disc is None:
        disc = drv.run_discovery(
            pool=pool, evaluation=evaluation,
            control=split["control"],
            pair_pool=split["pair_pool"],
            chain_pool=split["pair_pool"],
            adapter=GRID_ADAPTER)
        _save(f"discovery_{band}.json", disc)
    keys, chains = drv._extract_admitted(disc)
    digest = drv.catalog_digest(keys, chains)
    print(f"[stage3] band {band}: control="
          f"{len(control_tasks)} keys={len(keys)} "
          f"digest={digest[:12]}", flush=True)
    gate = band_gate(band, control_tasks, keys)
    if gate["verdict"] != "PASS":
        out = {"band": band, "verdict": "BAND_VOID_GATE_FAIL",
               "gate": gate, "catalog_digest": digest,
               "wall_seconds": round(time.time() - t0, 1)}
        _save(f"band_{band}.json", out)
        return out
    cells = {}
    for arm in ("S", "R", "F"):
        cells[f"clean_{arm}"] = run_cell(
            band, "clean", arm, control_tasks, keys, None)
    clean_s_calls = [r["score_calls"] for r in
                     cells["clean_S"]["records"].values()
                     if r["score_calls"] is not None]
    ceiling = max(1, int(3 * statistics.median(clean_s_calls)))
    naturally = NC_KEY in keys
    infected_keys = list(keys) if naturally else \
        list(keys) + [NC_KEY]
    targets = {tid: r["returned_sha256"] for tid, r in
               cells["clean_S"]["records"].items()}
    for arm in ("S", "R", "F"):
        cells[f"infected_{arm}"] = run_cell(
            band, "infected", arm, control_tasks,
            infected_keys, ceiling, targets=targets)
    # --- per-band prediction readings (§2.4/§2.5) ------
    cs = cells["clean_S"]["records"]
    is_ = cells["infected_S"]["records"]
    p1_failures = sorted(
        tid for tid in cs
        if cs[tid]["solved"] and not is_[tid]["solved"])
    recovered_R = sorted(
        tid for tid in p1_failures
        if cells["infected_R"]["records"][tid]["solved"])
    recovered_F = sorted(
        tid for tid in p1_failures
        if cells["infected_F"]["records"][tid]["solved"])
    p3 = {tid: is_[tid].get("true_path_classification")
          for tid in p1_failures}
    out = {"band": band, "catalog_digest": digest,
           "n_keys": len(keys), "n_chains": len(chains),
           "nc_naturally_present": naturally,
           "ceiling_calls": ceiling,
           "clean_S_median_calls":
               statistics.median(clean_s_calls),
           "gate": gate,
           "cells": {k: {"solved_count": c["solved_count"],
                         "total": c["total"],
                         "wall_seconds": c["wall_seconds"]}
                     for k, c in cells.items()},
           "p1_failures": p1_failures,
           "recovered_by_R": recovered_R,
           "recovered_by_F": recovered_F,
           "p3_classifications": p3,
           "wall_seconds": round(time.time() - t0, 1)}
    _save(f"band_{band}.json", out)
    print(f"[stage3] band {band} DONE: P1 failures="
          f"{p1_failures} R_rec={recovered_R} "
          f"F_rec={recovered_F} p3={p3}", flush=True)
    return out


def main():
    regate = HERE / "dev_regate_verdict.json"
    if not regate.exists():
        print("[stage3] DEV RE-GATE record missing — "
              "refusing to start", flush=True)
        sys.exit(3)
    rv = json.loads(regate.read_text())
    if rv.get("verdict") != "PASS":
        print("[stage3] DEV RE-GATE not PASS — refusing",
              flush=True)
        sys.exit(3)
    bands = [run_band(b) for b in BANDS]
    live = [b for b in bands
            if b.get("verdict") != "BAND_VOID_GATE_FAIL"]
    all_p1 = sorted({t for b in live
                     for t in b["p1_failures"]})
    p1_fired = [b["band"] for b in live if b["p1_failures"]]
    any_recovery = sorted(
        {t for b in live for t in
         b["recovered_by_R"] + b["recovered_by_F"]})
    p3_all = {}
    for b in live:
        p3_all.update({f"{b['band']}:{t}": c
                       for t, c in
                       b["p3_classifications"].items()})
    if not p1_fired:
        verdict = "NOT_REPRODUCED"
        p2 = p3 = "MOOT (P1 did not fire)"
    else:
        verdict = "P1_REPRODUCED"
        p2 = ("REFUTED — recovery reopens attribution: "
              + repr(any_recovery)) if any_recovery else \
            "HELD — neither R nor F recovered any " \
            "infected failure"
        vals = list(p3_all.values())
        if all(v == "never_generated" for v in vals):
            p3 = "HELD — never_generated on every " \
                 "infected S failure"
        elif vals.count("scored_pruned_below_frontier") \
                * 2 > len(vals):
            p3 = "CONTRADICTED — majority " \
                 "scored_pruned_below_frontier; " \
                 "diversion account reopens"
        else:
            p3 = "WEAKENED — mixed classifications: " \
                 + repr(p3_all)
    record = {
        "experiment": "ctrlreg-stage3-official "
                      "(PR #184 draft, PR #173 §16 "
                      "ratification, hub act 22:45)",
        "bands": bands,
        "pooled": {"p1_fired_on_bands": p1_fired,
                   "p1_failure_tasks": all_p1,
                   "any_recovery": any_recovery,
                   "p3_classifications": p3_all},
        "verdicts": {"P1": verdict, "P2": p2, "P3": p3},
        "recovery_criterion": "solved = passes ALL "
                              "holdout cases (§8(c))",
    }
    _atomic_write(EVIDENCE, json.dumps(record, indent=1))
    print(f"[stage3] OFFICIAL DONE — P1={verdict} "
          f"P2={p2} P3={p3}", flush=True)


if __name__ == "__main__":
    main()
