"""EXTENDED COPY for the OFFICIAL Stage 3 run (hub act 2026-11-13): prep harness + §2.6 frontier-provenance extension. Original docstring follows.

Control-regression Stage 3 PREP — one-variable intervention
harness (design PR #173 §7 + §8). PREPARATION ONLY: every run
here is on the DEVELOPMENT witnesses (catalog_control-020 /
-021, band 20261501, arm B's frozen catalog infected by the
causal 'nc' key). No official Stage 3 run exists in this file;
the fresh-band run is a separate act gated on the Stage 3
preregistration's internal ratification (PR #173 §10 framing).

What this harness adds over Stages 0–2 (PR #174), per §7:

  1. LOGGING-INVARIANCE GATE (prerequisite, runs first).
     §7.2: logging alone must not change solver outputs or
     decision traces; if it does, diagnosis stops. The gate
     compares, per witness task x {arm A, arm B} x capped:
       (a) the STOCK v3 solver (wt-abcv3 solve_task, trace on),
       (b) this harness's parameterised solver at the stock
           defaults (rounds=6, frontier=4), logging OFF,
       (c) the same parameterised solver, logging ON
           (score recorder + per-round ranking trace).
     PASS requires identical returned-code sha256, solved,
     score-call count and provenance trace across (a)/(b)/(c),
     AND (c) must reproduce the Stage 0 recorded hashes
     (arm A: the A-winning hash; arm B: the failing returned
     hashes from PR #174's Stage 0 state). Any mismatch ->
     gate FAIL, the harness exits non-zero and NO
     intervention cell is run or read.

  2. PER-ROUND RANKING TRACE of the true-path candidate
     (§7.3). Candidate identity = arm A's returned_sha256
     (6504b23b… for both witnesses, PR #174). Per round the
     log records whether that exact code text was GENERATED
     (in the round's candidate list), SCORED (and its rank
     in the round's stable score-sorted order + its score),
     admitted to the FRONTIER, or made BEST — separating
     "never generated" from "generated, never scored"
     (cap-orphaned via `seen`), "scored but pruned below
     the frontier cutoff" and "reached the frontier". The
     holdout is never used for identification.

  3. ONE-VARIABLE INTERVENTION CELLS (§7.1, §8). Strictly
     separate, both UNCAPPED (the §8(d) control form):
       control      rounds=6,  frontier=4  (must STILL FAIL
                    on both witnesses before any comparison
                    may be read — §8(d))
       rounds_only  rounds=12, frontier=4
       frontier_only rounds=6, frontier=8
     Nothing raises both at once. Recovery criterion (§8(c)):
     SOLVED = returned code passes ALL holdout cases. Hash
     equality with arm A's solution is recorded for
     information only and is NEVER the criterion.

The parameterised solver below is a line-faithful copy of
wt-abcv3's solve_task loop with exactly two substitutions —
range(6) -> range(rounds), scored[:4] -> scored[:frontier_
width] — plus observation-only logging hooks that run after
each round's selection is complete. Its equivalence at the
defaults is not assumed: it is what the gate in (1) proves,
against the stock solver and the Stage 0 record, before any
intervention number exists. The stock solver, the v3 kernel
and the frozen evidence packages are READ ONLY here; the
inoculation battery (PR #175) is not touched.

Runtime custody (same pattern as the Stage 0–2 harnesses):
the v3 solver and the frozen admitted catalog live outside
this repo (ACE_OMEGA_BASE, default /home/hatch/workspace/
ace-omega: wt-abcv3/code, abc_v3_run.py, abc-v3-run-state/
discovery_20261501.json). The catalog digest is asserted
against the Stage 0/1 frozen value before anything runs.

Outputs (checkpointed per cell under evidence/
ctrlreg_stage3_state/ so a VM replacement loses little):
  evidence/ctrlreg_stage3_intervention.json — final record.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = Path(sys.argv[sys.argv.index("--base") + 1]) \
    if "--base" in sys.argv else \
    Path("/home/hatch/workspace/ace-omega")
sys.path.insert(0, str(BASE / "wt-abcv3/code"))
sys.path.insert(0, str(BASE))

import abc_v3_run as drv  # the v3 driver: split/digest/wall
from ace_operational.grid_adapter import GRID_ADAPTER
from ace_operational.grid_generalization import build_universe
import ace_operational.operator_discovery as od
from ace_operational.operator_discovery import (
    apply_chain, apply_operator, solve_task)

SEED = 20261501
CAP = drv.CAP
WALL = drv.WALL_PER_TASK
TASKS = ("catalog_control-020", "catalog_control-021")
NC_KEY = ("name_swap", (5, 2, 3, 0, 1, 4), "nc")
EXPECTED_DIGEST = \
    "a67685635cffb2c20a1c48bedd797b34ab71e93d7325eaae734231036418ee68"
# Stage 0 record (PR #174): arm A's winning returned hash —
# identical code text wins on both witness tasks.
A_WIN = {t: "6504b23bd0f407d222f3453430cb5edd92f87fc65dc5a0b07e19080068098322" for t in TASKS}
# Stage 0 record (PR #174): arm B capped failing returns.
B_FAIL_RETURNED = {
    "catalog_control-020":
        "dcfb155f27659d3eae8732a49957c2f357e0bddc34721e6c92e6505ea06a5c09",
    "catalog_control-021":
        "6577e3eecf247df1555e9279b8057bb2ce5d882fa8de2a6fa95a0dbe3c49062b",
}
assert all(len(h) == 64 for h in
           list(A_WIN.values()) + list(B_FAIL_RETURNED.values()))
STOCK_ROUNDS = 6
STOCK_FRONTIER = 4

STATE = HERE / "ctrlreg_stage3_state"
EVIDENCE = HERE / "ctrlreg_stage3_intervention.json"
STATE.mkdir(exist_ok=True)

# --- reconstruct the control tasks + frozen catalog --------
universe = build_universe(seed=SEED)
split = drv.split_universe(universe["tasks"])
control = {t["task_id"]: t for t in split["control"]}
discovery = json.loads(
    (BASE / "abc-v3-run-state" / f"discovery_{SEED}.json")
    .read_text())
keys, chains = drv._extract_admitted(discovery)
digest = drv.catalog_digest(keys, chains)
assert digest == EXPECTED_DIGEST, f"catalog digest {digest}"
assert NC_KEY in keys, "causal 'nc' key missing from catalog"
assert all(t in control for t in TASKS)
print(f"[stage3] control={len(split['control'])} "
      f"keys={len(keys)} chains={len(chains)} digest OK; "
      f"'nc' key present at position "
      f"{keys.index(NC_KEY) + 1}", flush=True)

# --- score recorder (observation only) ---------------------
_orig_safe_score = od._safe_score
_rec = {"active": False, "hashes": []}


def _recording_safe_score(budget, code, seconds=0.5):
    if _rec["active"]:
        _rec["hashes"].append(
            hashlib.sha256(code.encode("utf-8")).hexdigest())
    return _orig_safe_score(budget, code, seconds)


od._safe_score = _recording_safe_score


def _sha(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


# --- parameterised solver ----------------------------------
def solve_task_param(task, adapter, extra_keys=(),
                     extra_chains=(), *,
                     max_score_calls=None, rounds=STOCK_ROUNDS,
                     frontier_width=STOCK_FRONTIER,
                     trace=None, round_log=None,
                     true_path_sha=None):
    """Line-faithful copy of wt-abcv3 solve_task with rounds
    and frontier width parameterised (defaults = stock).
    When round_log is a list, one observation-only entry per
    round is appended AFTER that round's selection; the
    entries never feed back into the search. Returns
    (best_code, info) — info carries the termination reason
    and the internal score-call count."""
    provenance: dict[str, tuple] = {}

    def extended_variants(code):
        variants = adapter.baseline_variants(code)
        if trace is not None:
            for text in variants:
                provenance.setdefault(text, ("baseline", None))
        for key in extra_keys:
            text = apply_operator(code, key)
            if text is not None and text not in variants:
                variants.append(text)
                if trace is not None:
                    provenance.setdefault(text, ("key", key))
        for chain in extra_chains:
            text = apply_chain(code, chain)
            if text is not None and text not in variants:
                variants.append(text)
                if trace is not None:
                    provenance.setdefault(text, ("chain", chain))
        return variants

    budget = adapter.make_budget(task)
    calls = 0

    def score(code):
        nonlocal calls
        calls += 1
        return _recording_safe_score(budget, code)

    start = task["buggy_code"]
    best_code, best_score = start, score(start)
    frontier, seen = [start], {start}
    termination = "rounds_exhausted"
    for rnd in range(1, rounds + 1):
        if best_score >= len(task["shown_cases"]):
            termination = "shown_perfect_exit"
            break
        candidates = []
        for code in frontier:
            for variant in extended_variants(code):
                if variant not in seen:
                    seen.add(variant)
                    candidates.append(variant)
        if not candidates:
            termination = "no_candidates"
            break
        scored_pairs = []
        cap_break = False
        for candidate in candidates:
            if max_score_calls is not None and \
                    calls >= max_score_calls:
                cap_break = True
                break
            scored_pairs.append((score(candidate), candidate))
        if not scored_pairs:
            termination = "no_scored_pairs_cap"
            break
        scored = sorted(scored_pairs, key=lambda pair: -pair[0])
        if scored[0][0] > best_score:
            best_code, best_score = scored[0][1], scored[0][0]
            if trace is not None:
                trace.append(provenance[scored[0][1]])
        new_frontier = [c for s, c in
                        scored[:frontier_width]
                        if s >= best_score]
        if round_log is not None:
            round_log.append(_round_entry(
                rnd, candidates, scored, new_frontier,
                best_code, best_score, cap_break,
                true_path_sha, provenance))
        frontier = new_frontier
        if not frontier:
            termination = "frontier_empty"
            break
    return best_code, {"termination": termination,
                       "score_calls_internal": calls}


def _round_entry(rnd, candidates, scored, frontier, best_code,
                 best_score, cap_break, true_path_sha,
                 provenance=None):
    entry = {
        "round": rnd,
        "n_candidates_generated": len(candidates),
        "n_scored": len(scored),
        "cap_break": cap_break,
        "best_score_after": best_score,
        "frontier_size": len(frontier),
        "frontier_cutoff_score": (
            min(s for s, c in scored if c in frontier)
            if frontier else None),
    }
    if provenance is not None:
        # NAMED EXTENSION for the official Stage 3 run
        # (prereg draft §2.6): per-round frontier
        # PROVENANCE composition. Observation-only —
        # derived from the already-selected frontier,
        # never fed back into the search.
        comp = {"root": 0, "baseline": 0, "key": 0,
                "chain": 0}
        key_lineages = set()
        for code in frontier:
            kind, detail = provenance.get(
                code, ("root", None))
            comp[kind] = comp.get(kind, 0) + 1
            if kind == "key":
                key_lineages.add(repr(detail))
        entry["frontier_provenance"] = {
            "composition": comp,
            "key_lineages_present": sorted(key_lineages),
        }
    if true_path_sha is not None:
        tp = {"generated": False, "scored": False,
              "rank": None, "score": None,
              "in_frontier": False, "is_best": False}
        gen_hashes = [_sha(c) for c in candidates]
        if true_path_sha in gen_hashes:
            tp["generated"] = True
        for i, (s, c) in enumerate(scored):
            if _sha(c) == true_path_sha:
                tp["scored"] = True
                tp["rank"] = i + 1
                tp["score"] = s
                break
        tp["in_frontier"] = any(
            _sha(c) == true_path_sha for c in frontier)
        tp["is_best"] = _sha(best_code) == true_path_sha
        entry["true_path"] = tp
    return entry


def classify_true_path(round_log, returned_sha, target_sha):
    """§7.3 discrimination, mechanical: where did the
    true-path candidate's journey end?"""
    if returned_sha == target_sha:
        return "returned"
    gen = any(e.get("true_path", {}).get("generated")
              for e in round_log)
    sco = any(e.get("true_path", {}).get("scored")
              for e in round_log)
    fro = any(e.get("true_path", {}).get("in_frontier")
              for e in round_log)
    bes = any(e.get("true_path", {}).get("is_best")
              for e in round_log)
    if bes:
        return "became_best_then_displaced"
    if fro:
        return "reached_frontier_not_returned"
    if sco:
        return "scored_pruned_below_frontier"
    if gen:
        return "generated_never_scored"
    return "never_generated"


# --- one instrumented solve, any solver flavour ------------
def run_solve(task, arm_keys, *, flavour, cap,
              rounds=STOCK_ROUNDS, frontier_width=STOCK_FRONTIER,
              with_log=False):
    """flavour: 'stock' (wt-abcv3 solve_task) or 'param'.
    Returns the per-solve record; solved per §8(c)."""
    trace: list = []
    round_log: list = []

    def attempt():
        _rec["hashes"] = []
        _rec["active"] = True
        try:
            if flavour == "stock":
                code = solve_task(
                    task, GRID_ADAPTER, tuple(arm_keys), (),
                    max_score_calls=cap, trace=trace)
                info = {"termination": None,
                        "score_calls_internal": None}
            else:
                code, info = solve_task_param(
                    task, GRID_ADAPTER, tuple(arm_keys), (),
                    max_score_calls=cap, rounds=rounds,
                    frontier_width=frontier_width, trace=trace,
                    round_log=round_log if with_log else None,
                    true_path_sha=A_WIN[task["task_id"]])
        finally:
            _rec["active"] = False
        budget = GRID_ADAPTER.make_budget(task)
        shown = _orig_safe_score(budget, code)
        cases = [tuple(c) for c in task["holdout_cases"]]
        npass = GRID_ADAPTER.passes(code, cases,
                                    task["holdout_truth"])
        rec = {
            "task_id": task["task_id"],
            "solved": npass == len(cases),
            "holdout_passes": npass,
            "holdout_total": len(cases),
            "shown_score": shown,
            "shown_total": len(task["shown_cases"]),
            "score_calls": len(_rec["hashes"]),
            "returned_sha256": _sha(code),
            "returned_is_a_solution": _sha(code)
            == A_WIN[task["task_id"]],
            "trace": [[k, repr(p) if p else None]
                      for k, p in trace],
            "termination": info["termination"],
        }
        if flavour == "param":
            assert info["score_calls_internal"] \
                == rec["score_calls"], \
                "internal/recorder call counts diverge"
            rec["true_path_classification"] = \
                classify_true_path(round_log,
                                   rec["returned_sha256"],
                                   A_WIN[task["task_id"]])
            rec["round_log"] = round_log
        return rec

    out, timed_out = drv._run_with_wall(attempt, WALL)
    if timed_out:
        return {"task_id": task["task_id"], "solved": False,
                "timeout": True}
    out["timeout"] = False
    return out


# --- the logging-invariance gate ---------------------------
ARMS = {"A": (), "B": tuple(keys)}


def run_gate():
    ckpt = STATE / "gate.json"
    if ckpt.exists():
        prior = json.loads(ckpt.read_text())
        print(f"[stage3] gate: checkpoint "
              f"verdict={prior['verdict']}", flush=True)
        return prior
    comparisons = []
    gate_ok = True
    for task_id in TASKS:
        task = control[task_id]
        for arm, arm_keys in ARMS.items():
            modes = {
                "stock": run_solve(task, arm_keys,
                                   flavour="stock", cap=CAP),
                "param_nolog": run_solve(
                    task, arm_keys, flavour="param", cap=CAP,
                    with_log=False),
                "param_log": run_solve(
                    task, arm_keys, flavour="param", cap=CAP,
                    with_log=True),
            }
            fields = ("returned_sha256", "solved",
                      "score_calls", "trace")
            same = all(
                len({json.dumps(modes[m][f], sort_keys=True)
                     for m in modes}) == 1 for f in fields)
            anchor = {"A": A_WIN[task_id],
                      "B": B_FAIL_RETURNED[task_id]}[arm]
            anchor_ok = modes["param_log"]["returned_sha256"] \
                == anchor
            ok = same and anchor_ok
            gate_ok = gate_ok and ok
            comparisons.append({
                "task_id": task_id, "arm": arm,
                "modes_identical": same,
                "stage0_anchor_ok": anchor_ok,
                "pass": ok,
                "returned_sha256":
                    modes["param_log"]["returned_sha256"],
                "solved": modes["param_log"]["solved"],
                "score_calls": modes["param_log"]["score_calls"],
            })
            print(f"[stage3] gate {task_id} arm {arm}: "
                  f"identical={same} anchor={anchor_ok}",
                  flush=True)
    out = {"gate": "logging-invariance (PR #173 §7.2)",
           "verdict": "PASS" if gate_ok else "FAIL",
           "comparisons": comparisons}
    ckpt.write_text(json.dumps(out, indent=1))
    return out


# --- intervention cells ------------------------------------
CELLS = {
    "control": {"rounds": STOCK_ROUNDS,
                "frontier_width": STOCK_FRONTIER},
    "rounds_only": {"rounds": 12,
                    "frontier_width": STOCK_FRONTIER},
    "frontier_only": {"rounds": STOCK_ROUNDS,
                      "frontier_width": 8},
}


def run_cell(name, cfg):
    ckpt = STATE / f"cell_{name}.json"
    if ckpt.exists():
        print(f"[stage3] cell {name}: checkpoint, skip",
              flush=True)
        return json.loads(ckpt.read_text())
    t0 = time.time()
    recs = {}
    for task_id in TASKS:
        rec = run_solve(control[task_id], keys, flavour="param",
                        cap=None, with_log=True, **cfg)
        # keep the evidence compact: per-round true-path
        # entries + round counters, not full frontier hashes
        rec["round_log"] = [
            {k: e[k] for k in ("round",
                               "n_candidates_generated",
                               "n_scored", "cap_break",
                               "best_score_after",
                               "frontier_size",
                               "frontier_cutoff_score",
                               "true_path") if k in e}
            for e in rec.get("round_log", [])]
        recs[task_id] = rec
    out = {"cell": name, "config": cfg, "cap": None,
           "wall_seconds": round(time.time() - t0, 1),
           "records": recs}
    ckpt.write_text(json.dumps(out, indent=1))
    print(f"[stage3] cell {name}: " + "; ".join(
        f"{t} solved={r['solved']} calls={r.get('score_calls')} "
        f"tp={r.get('true_path_classification')}"
        for t, r in recs.items()), flush=True)
    return out


def main():
    gate = run_gate()
    if gate["verdict"] != "PASS":
        record = {"experiment": "ctrlreg-stage3-intervention"
                                "-prep (PR #173 §7/§8)",
                  "scope": "DEVELOPMENT witnesses only — "
                           "no official Stage 3 run",
                  "gate": gate,
                  "verdict": "GATE_FAIL — diagnosis stops "
                             "(§7.2); no cell was run or read"}
        EVIDENCE.write_text(json.dumps(record, indent=1))
        print("[stage3] GATE FAIL — STOP", flush=True)
        sys.exit(2)
    cells = {name: run_cell(name, cfg)
             for name, cfg in CELLS.items()}
    # §8(d): the uncapped control cell must still reproduce
    # the failure before any comparison may be read.
    control_valid = all(
        not cells["control"]["records"][t]["solved"]
        for t in TASKS)
    summary = {}
    for t in TASKS:
        summary[t] = {
            "control_solved":
                cells["control"]["records"][t]["solved"],
            "rounds_only_solved":
                cells["rounds_only"]["records"][t]["solved"],
            "frontier_only_solved":
                cells["frontier_only"]["records"][t]["solved"],
            "rounds_only_recovers":
                cells["rounds_only"]["records"][t]["solved"]
                and not cells["control"]["records"][t]
                ["solved"],
            "frontier_only_recovers":
                cells["frontier_only"]["records"][t]["solved"]
                and not cells["control"]["records"][t]
                ["solved"],
        }
    record = {
        "experiment": "ctrlreg-stage3-intervention-prep "
                      "(PR #173 §7/§8)",
        "scope": "DEVELOPMENT witnesses only (band 20261501 "
                 "catalog_control-020/-021, arm B frozen "
                 "catalog incl. causal 'nc' key) — NOT an "
                 "official Stage 3 run; the fresh-band run "
                 "awaits the Stage 3 preregistration's "
                 "internal ratification",
        "catalog_digest": digest,
        "nc_key": repr(NC_KEY),
        "recovery_criterion": "solved = returned code passes "
                              "ALL holdout cases (PR #173 "
                              "§8(c)); hash equality with arm "
                              "A's solution is NOT the "
                              "criterion",
        "gate": gate,
        "cells": {n: {"config": c["config"], "cap": None,
                      "wall_seconds": c["wall_seconds"],
                      "records": c["records"]}
                  for n, c in cells.items()},
        "comparison_valid_per_section8d": control_valid,
        "summary": summary,
        "verdict": ("COMPARISON_VALID" if control_valid else
                    "CONTROL_DID_NOT_REPRODUCE — comparisons "
                    "must not be read (§8(d))"),
    }
    EVIDENCE.write_text(json.dumps(record, indent=1))
    print(f"[stage3] DONE — verdict={record['verdict']}",
          flush=True)


if __name__ == "__main__":
    main()
