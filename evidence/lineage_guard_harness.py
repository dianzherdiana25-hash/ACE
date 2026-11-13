"""ACE Omega — lineage-guard run harness (PR #188, Part B.1).

Built ONLY on activation (hub internal-ratification act,
2026-11-14; trigger: Stage 3 official verdict PR #192
confirming P1+P2+P3). Implements the wiring plan of
docs/research/ACE_LINEAGE_GUARD_PREREG_FULL_DRAFT_20261113.md
Part B exactly:

  - solve_task_param: PR #184's parameterised solver,
    copied line-faithfully (the reference; PR #184 gate
    PASS is its equivalence proof against the stock v3
    solver).
  - solve_task_guarded: the same copy plus EXACTLY the
    three insertions of B.2 — (1) the first-generation-wins
    lineage label map, (2) the guard hook (one reserved
    BASE slot), (3) the lineage-anchor recorder
    (schema ace.lineage_anchor.v1, A.4.1).
  - The run protocol of A.6 with its mechanical stops:
    L4 logging-invariance gate and L1/L2 reproduction on
    the development witnesses (steps 2-3, here), the
    step-4 battery gate delegated to
    evidence/lineage_guard_gate.py, confirmation-band
    cells (steps 5-6), the A.7 mechanical worksheet
    (step 7) and the top record (step 8). The band run
    refuses to start without an activation record
    supplying the five act fields of section 8 of the
    preregistration; nothing here touches a confirmation
    band on its own.

Custody pattern is PR #184's: the v3 solver base and the
frozen admitted catalogs live outside this repo
(ACE_OMEGA_BASE, default /home/hatch/workspace/ace-omega:
wt-abcv3/code, abc_v3_run.py, abc-v3-run-state/). Module
import is side-effect free (no universe is built at
import) so evidence/test_lineage_guard_harness.py can
exercise the solver synthetically with no band access.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / "lineage_guard_state"
TOP_RECORD = HERE / "lineage_guard_run.json"
ANCHOR_SCHEMA = "ace.lineage_anchor.v1"

SEED = 20261501
TASKS = ("catalog_control-020", "catalog_control-021")
NC_KEY = ("name_swap", (5, 2, 3, 0, 1, 4), "nc")
EXPECTED_DIGEST = \
    "a67685635cffb2c20a1c48bedd797b34ab71e93d7325eaae734231036418ee68"
A_WIN = {t: "6504b23bd0f407d222f3453430cb5edd92f87fc65dc5a0b07e19080068098322"
         for t in TASKS}
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

# --- solver base (loaded lazily; tests stub these) --------
apply_operator = None
apply_chain = None
solve_task_stock = None
_orig_safe_score = None
_od = None


def _base_dir() -> Path:
    if "--base" in sys.argv:
        return Path(sys.argv[sys.argv.index("--base") + 1])
    return Path(os.environ.get(
        "ACE_OMEGA_BASE", "/home/hatch/workspace/ace-omega"))


def _ensure_base():
    """Load the frozen v3 solver base (operator_discovery)
    and install the observation-only score recorder, PR #184
    pattern. Idempotent; a no-op once the globals are set
    (unit tests set them to synthetic stubs instead)."""
    global apply_operator, apply_chain, solve_task_stock
    global _orig_safe_score, _od
    if apply_operator is not None and _orig_safe_score \
            is not None:
        return
    base = _base_dir()
    for p in (str(base / "wt-abcv3/code"), str(base)):
        if p not in sys.path:
            sys.path.insert(0, p)
    import ace_operational.operator_discovery as od
    _od = od
    apply_operator = od.apply_operator
    apply_chain = od.apply_chain
    solve_task_stock = od.solve_task
    _orig_safe_score = od._safe_score
    od._safe_score = _recording_safe_score


# --- score recorder (observation only, PR #184) -----------
_rec = {"active": False, "hashes": []}


def _recording_safe_score(budget, code, seconds=0.5):
    if _rec["active"]:
        _rec["hashes"].append(
            hashlib.sha256(code.encode("utf-8")).hexdigest())
    return _orig_safe_score(budget, code, seconds)


def _sha(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


# --- reference solver: PR #184's solve_task_param, copied
# --- line-faithfully, with its _round_entry and
# --- classify_true_path (PR #184 gate PASS is the
# --- equivalence proof against the stock v3 solver) ------
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
                true_path_sha))
        frontier = new_frontier
        if not frontier:
            termination = "frontier_empty"
            break
    return best_code, {"termination": termination,
                       "score_calls_internal": calls}


def _round_entry(rnd, candidates, scored, frontier, best_code,
                 best_score, cap_break, true_path_sha):
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



# --- guarded solver: solve_task_param plus EXACTLY the ---
# --- three insertions of Part B.2 -------------------------
def solve_task_guarded(task, adapter, extra_keys=(),
                       extra_chains=(), *,
                       max_score_calls=None,
                       rounds=STOCK_ROUNDS,
                       frontier_width=STOCK_FRONTIER,
                       trace=None, round_log=None,
                       true_path_sha=None, guard=False):
    """Line-faithful copy of solve_task_param above, plus
    the three B.2 insertions (marked INSERTION 1/2/3).
    With guard=False the guard hook is a no-op and the
    function is behaviour-identical to solve_task_param —
    the L4 gate in run_dev_gates is the proof. The anchor
    recorder (insertion 3) is observation-only, exactly as
    PR #184's recorder: entries are appended after each
    round's selection and never feed back into the search.
    info additionally carries lineage_labels
    ({sha256: label}) for the anchor joins (L1/L3)."""
    provenance: dict[str, tuple] = {}
    # INSERTION 1 (label map), seeded once start exists —
    # see below; extended_variants closes over label_of.
    label_of: dict[str, str] = {}

    def extended_variants(code):
        # INSERTION 1: the parent label is label_of[code];
        # baseline-step children inherit it, key/chain-step
        # children are ENRICHED; a text is labelled only if
        # not already labelled (first-generation-wins), at
        # generation time, whether or not it survives the
        # seen dedup into the candidate list. Generation
        # order is the stock order: baseline variants, then
        # keys, then chains.
        parent_label = label_of[code]
        variants = adapter.baseline_variants(code)
        for text in variants:
            if text not in label_of:
                label_of[text] = parent_label
        if trace is not None:
            for text in variants:
                provenance.setdefault(text, ("baseline", None))
        for key in extra_keys:
            text = apply_operator(code, key)
            if text is not None:
                if text not in label_of:
                    label_of[text] = "ENRICHED"
                if text not in variants:
                    variants.append(text)
                    if trace is not None:
                        provenance.setdefault(text, ("key", key))
        for chain in extra_chains:
            text = apply_chain(code, chain)
            if text is not None:
                if text not in label_of:
                    label_of[text] = "ENRICHED"
                if text not in variants:
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
    label_of[start] = "BASE"  # INSERTION 1: seed.
    best_code, best_score = start, score(start)
    frontier, seen = [start], {start}
    termination = "rounds_exhausted"
    for rnd in range(1, rounds + 1):
        if best_score >= len(task["shown_cases"]):
            termination = "shown_perfect_exit"
            break
        frontier_in = list(frontier)  # INSERTION 3 input.
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
        # INSERTION 2 (guard hook): after the stock frontier
        # list is built and before it is assigned — if the
        # frontier holds no BASE member and at least one
        # BASE candidate was scored this round, the last
        # (lowest-ranked) member is replaced by the
        # highest-ranked BASE scored candidate of the round
        # (first BASE entry in the ranked scored order).
        guard_event = None
        if guard:
            guard_event = {"triggered": False,
                           "occupant": None, "displaced": None}
            if new_frontier and all(
                    label_of[c] != "BASE" for c in new_frontier):
                base_scored = [c for s, c in scored
                               if label_of[c] == "BASE"]
                if base_scored:
                    occupant = base_scored[0]
                    displaced = new_frontier[-1]
                    new_frontier = new_frontier[:-1] + [occupant]
                    guard_event = {
                        "triggered": True,
                        "occupant": _sha(occupant),
                        "displaced": _sha(displaced)}
        if round_log is not None:
            round_log.append(_round_entry_guarded(
                rnd, candidates, scored, new_frontier,
                best_code, best_score, cap_break,
                true_path_sha, frontier_in, label_of,
                guard_event))
        frontier = new_frontier
        if not frontier:
            termination = "frontier_empty"
            break
    return best_code, {"termination": termination,
                       "score_calls_internal": calls,
                       "lineage_labels": {
                           _sha(t): lab
                           for t, lab in label_of.items()}}


def _round_entry_guarded(rnd, candidates, scored, frontier,
                         best_code, best_score, cap_break,
                         true_path_sha, frontier_in, label_of,
                         guard_event):
    """PR #184's _round_entry fields (frontier = the
    post-guard frontier_out) plus INSERTION 3, the lineage
    anchor fields of A.4.1: frontier_in / frontier_out as
    (sha256, label) lists, the round's best scored BASE
    candidate (sha256, score, rank) or None, the guard
    event or None, and the lineage_alive_in bit (L2)."""
    entry = _round_entry(rnd, candidates, scored, frontier,
                         best_code, best_score, cap_break,
                         true_path_sha)
    entry["frontier_in"] = [[_sha(c), label_of[c]]
                            for c in frontier_in]
    entry["frontier_out"] = [[_sha(c), label_of[c]]
                             for c in frontier]
    base_best = None
    for i, (s, c) in enumerate(scored):
        if label_of[c] == "BASE":
            base_best = [_sha(c), s, i + 1]
            break
    entry["scored_base_best"] = base_best
    entry["guard_event"] = guard_event
    entry["lineage_alive_in"] = any(
        label_of[c] == "BASE" for c in frontier_in)
    return entry


def check_l5(round_log):
    """L5 actuation check (A.4.1), mechanical: wherever the
    guard triggered, the reserved slot's occupant IS the
    round's highest-ranked BASE scored candidate, sits in
    frontier_out labelled BASE, and the displaced member
    is gone from frontier_out. One violation voids the
    run. Returns the list of violations (empty = L5 held
    on every recorded round)."""
    violations = []
    for e in round_log:
        ev = e.get("guard_event")
        if not ev or not ev.get("triggered"):
            continue
        best = e.get("scored_base_best")
        if best is None:
            violations.append({
                "round": e["round"],
                "violation": "triggered_without_base_scored"})
            continue
        if ev["occupant"] != best[0]:
            violations.append({
                "round": e["round"],
                "violation": "occupant_not_argmax_base",
                "occupant": ev["occupant"],
                "expected": best[0]})
        if [ev["occupant"], "BASE"] not in e["frontier_out"]:
            violations.append({
                "round": e["round"],
                "violation": "occupant_not_in_frontier_out"})
        if any(sha == ev["displaced"]
               for sha, _lab in e["frontier_out"]):
            violations.append({
                "round": e["round"],
                "violation": "displaced_still_in_frontier_out"})
    return violations


# --- contexts: custody reconstruction (PR #184 pattern) ---
def _load_ctx(seed, discovery_path, expect_digest=None):
    _ensure_base()
    base = _base_dir()
    import abc_v3_run as drv
    from ace_operational.grid_adapter import GRID_ADAPTER
    from ace_operational.grid_generalization import \
        build_universe
    universe = build_universe(seed=seed)
    split = drv.split_universe(universe["tasks"])
    control = {t["task_id"]: t for t in split["control"]}
    discovery = json.loads(
        Path(discovery_path).read_text())
    keys, chains = drv._extract_admitted(discovery)
    digest = drv.catalog_digest(keys, chains)
    if expect_digest is not None:
        assert digest == expect_digest, \
            f"catalog digest {digest}"
    return {"base": base, "drv": drv, "adapter": GRID_ADAPTER,
            "build_universe": build_universe,
            "control": control, "keys": list(keys),
            "chains": list(chains), "digest": digest,
            "cap": drv.CAP, "wall": drv.WALL_PER_TASK,
            "seed": seed}


def load_dev_context():
    """The development-witness context (band 20261501):
    frozen catalog, digest asserted against the Stage 0/1
    frozen value before anything runs (PR #184 custody)."""
    base = _base_dir()
    ctx = _load_ctx(
        SEED, base / "abc-v3-run-state" /
        f"discovery_{SEED}.json",
        expect_digest=EXPECTED_DIGEST)
    assert NC_KEY in ctx["keys"], "causal 'nc' key missing"
    assert all(t in ctx["control"] for t in TASKS)
    return ctx


def load_band_context(seed, discovery_path):
    """A confirmation band's context (A.5): universe and
    split by the v3 census code path; catalog admitted
    from the band's own discovery; digest recorded, not
    asserted (it is fixed by step 5 before any solve)."""
    return _load_ctx(seed, discovery_path)


# --- one instrumented solve, any flavour ------------------
def run_solve(ctx, task, keys, *, flavour, cap, chains=(),
              guard=False, true_path_sha=None):
    """flavour: 'stock' (wt-abcv3 solve_task), 'param'
    (solve_task_param) or 'guarded' (solve_task_guarded;
    guard flag selects the arm). Solved per §8(c): the
    returned code passes ALL holdout cases. Guarded
    records carry the anchor round log and the mechanical
    L5 check result."""
    drv = ctx["drv"]
    adapter = ctx["adapter"]
    trace: list = []
    round_log: list = []

    def attempt():
        _rec["hashes"] = []
        _rec["active"] = True
        try:
            if flavour == "stock":
                code = solve_task_stock(
                    task, adapter, tuple(keys), tuple(chains),
                    max_score_calls=cap, trace=trace)
                info = {"termination": None,
                        "score_calls_internal": None}
            elif flavour == "param":
                code, info = solve_task_param(
                    task, adapter, tuple(keys), tuple(chains),
                    max_score_calls=cap, trace=trace,
                    round_log=round_log,
                    true_path_sha=true_path_sha)
            elif flavour == "guarded":
                code, info = solve_task_guarded(
                    task, adapter, tuple(keys), tuple(chains),
                    max_score_calls=cap, trace=trace,
                    round_log=round_log,
                    true_path_sha=true_path_sha, guard=guard)
            else:
                raise ValueError(f"flavour {flavour!r}")
        finally:
            _rec["active"] = False
        budget = adapter.make_budget(task)
        shown = _orig_safe_score(budget, code)
        cases = [tuple(c) for c in task["holdout_cases"]]
        npass = adapter.passes(code, cases,
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
            "trace": [[k, repr(p) if p else None]
                      for k, p in trace],
            "termination": info["termination"],
        }
        if flavour in ("param", "guarded"):
            assert info["score_calls_internal"] \
                == rec["score_calls"], \
                "internal/recorder call counts diverge"
            if true_path_sha is not None:
                rec["true_path_classification"] = \
                    classify_true_path(
                        round_log, rec["returned_sha256"],
                        true_path_sha)
            rec["round_log"] = round_log
        if flavour == "guarded":
            rec["l5_violations"] = check_l5(round_log)
        return rec

    out, timed_out = drv._run_with_wall(attempt, ctx["wall"])
    if timed_out:
        return {"task_id": task["task_id"], "solved": False,
                "timeout": True}
    out["timeout"] = False
    return out


# --- steps 2-3: L4 gate + L1/L2 reproduction --------------
def run_dev_gates(ctx, state_dir=STATE):
    """A.6 steps 2-3 on the development witnesses.
    L4: guard-OFF instrumented (anchor attached) == param
    == stock, per witness x {arm A, arm B}, capped, plus
    the Stage 0 recorded hashes. L1/L2: from the same
    guard-OFF arm-B anchor records — BASE membership zero
    from round 2, death round == 2, both tasks; L3 joins
    the true-path classification to the death round.
    Writes gate.json and anchor_dev.json; returns both."""
    state_dir.mkdir(parents=True, exist_ok=True)
    gate_ckpt = state_dir / "gate.json"
    if gate_ckpt.exists():
        prior = json.loads(gate_ckpt.read_text())
        print(f"[lg] L4 gate: checkpoint "
              f"verdict={prior['verdict']}", flush=True)
        return prior, json.loads(
            (state_dir / "anchor_dev.json").read_text())
    comparisons = []
    gate_ok = True
    arm_b_logs = {}
    for task_id in TASKS:
        task = ctx["control"][task_id]
        for arm, arm_keys in (("A", ()), ("B", tuple(ctx["keys"]))):
            modes = {
                "stock": run_solve(
                    ctx, task, arm_keys, flavour="stock",
                    cap=ctx["cap"], true_path_sha=A_WIN[task_id]),
                "param": run_solve(
                    ctx, task, arm_keys, flavour="param",
                    cap=ctx["cap"], true_path_sha=A_WIN[task_id]),
                "guarded_off": run_solve(
                    ctx, task, arm_keys, flavour="guarded",
                    cap=ctx["cap"], guard=False,
                    true_path_sha=A_WIN[task_id]),
            }
            fields = ("returned_sha256", "solved",
                      "score_calls", "trace")
            same = all(
                len({json.dumps(modes[m][f], sort_keys=True)
                     for m in modes}) == 1 for f in fields)
            anchor = {"A": A_WIN[task_id],
                      "B": B_FAIL_RETURNED[task_id]}[arm]
            anchor_ok = modes["guarded_off"]["returned_sha256"] \
                == anchor
            ok = same and anchor_ok
            gate_ok = gate_ok and ok
            if arm == "B":
                arm_b_logs[task_id] = modes["guarded_off"]
            comparisons.append({
                "task_id": task_id, "arm": arm,
                "modes_identical": same,
                "stage0_anchor_ok": anchor_ok, "pass": ok,
                "returned_sha256":
                    modes["guarded_off"]["returned_sha256"],
                "solved": modes["guarded_off"]["solved"],
                "score_calls":
                    modes["guarded_off"]["score_calls"]})
            print(f"[lg] L4 {task_id} arm {arm}: "
                  f"identical={same} anchor={anchor_ok}",
                  flush=True)
    gate = {"gate": "L4 logging-invariance, lineage anchor "
                    "attached (PR #188 A.4.1)",
            "scope": "DEVELOPMENT witnesses (band 20261501)",
            "verdict": "PASS" if gate_ok else "FAIL",
            "comparisons": comparisons}
    gate_ckpt.write_text(json.dumps(gate, indent=1))

    anchor_tasks = {}
    l1l2_ok = True
    for task_id in TASKS:
        rec = arm_b_logs[task_id]
        rounds = []
        death_round = None
        for e in rec["round_log"]:
            base_in = sum(1 for _s, lab in e["frontier_in"]
                          if lab == "BASE")
            base_out = sum(1 for _s, lab in e["frontier_out"]
                           if lab == "BASE")
            if base_in == 0 and death_round is None:
                death_round = e["round"]
            rounds.append({
                "round": e["round"],
                "frontier_in_base": base_in,
                "frontier_out_base": base_out,
                "lineage_alive_in": e["lineage_alive_in"]})
        zero_from_2 = all(r["frontier_in_base"] == 0
                          for r in rounds if r["round"] >= 2)
        ok = death_round == 2 and zero_from_2
        l1l2_ok = l1l2_ok and ok
        anchor_tasks[task_id] = {
            "rounds": rounds, "death_round": death_round,
            "base_membership_zero_from_round_2": zero_from_2,
            "l1_l2_reproduced": ok,
            "l3_true_path": {
                "classification":
                    rec.get("true_path_classification"),
                "death_round": death_round}}
    anchor = {"schema": ANCHOR_SCHEMA,
              "scope": "DEVELOPMENT witnesses under stock "
                       "(guard OFF, anchor attached), arm B",
              "verdict": "PASS" if l1l2_ok else "FAIL",
              "rule": "BASE membership zero from round 2 "
                      "and death round == 2, both tasks",
              "tasks": anchor_tasks}
    (state_dir / "anchor_dev.json").write_text(
        json.dumps(anchor, indent=1))
    print(f"[lg] L1/L2 verdict={anchor['verdict']}",
          flush=True)
    return gate, anchor


# --- steps 5-6: confirmation-band cells -------------------
def _registry_records(registry_path):
    import ast
    data = json.loads(Path(registry_path).read_text())
    return [{"id": rec["id"],
             "key": ast.literal_eval(rec["key"])}
            for rec in data["distractors"]]


def run_band_cells(ctx, records, state_dir=STATE):
    """A.6 step 6, fixed order per band: stock-clean,
    guarded-clean, then per distractor stock-infected,
    guarded-infected. Both arms run through the guarded
    solver (stock = guard OFF, anchor attached — L4 is
    the identity proof) so every cell record carries its
    anchor records (B.5). Checkpoint per cell; a loss
    resumes from checkpoints, never restarts a cell."""
    state_dir.mkdir(parents=True, exist_ok=True)
    seed = ctx["seed"]
    base_keys = list(ctx["keys"])
    conditions = [("clean", base_keys)]
    for rec in records:
        infected = base_keys + [rec["key"]] \
            if rec["key"] not in base_keys else list(base_keys)
        conditions.append((f"infected_{rec['id']}", infected))
    cells = {}
    clean_returned = {}
    # fixed order: stock-clean, guarded-clean, then per
    # distractor stock-infected, guarded-infected
    order = [("stock", "clean"), ("guarded", "clean")]
    for rec in records:
        order.append(("stock", f"infected_{rec['id']}"))
        order.append(("guarded", f"infected_{rec['id']}"))
    cond_keys = dict(conditions)
    for arm, cond in order:
        ckpt = state_dir / f"cell_{seed}_{arm}_{cond}.json"
        if ckpt.exists():
            print(f"[lg] cell {seed} {arm} {cond}: "
                  f"checkpoint, skip", flush=True)
            cells[(arm, cond)] = json.loads(ckpt.read_text())
            continue
        t0 = time.time()
        recs = {}
        for task_id, task in sorted(ctx["control"].items()):
            tp = clean_returned.get(task_id) \
                if cond != "clean" else None
            rec = run_solve(ctx, task, cond_keys[cond],
                            flavour="guarded", cap=None,
                            chains=tuple(ctx["chains"]),
                            guard=(arm == "guarded"),
                            true_path_sha=tp)
            recs[task_id] = rec
            if arm == "stock" and cond == "clean" \
                    and rec["solved"]:
                clean_returned[task_id] = \
                    rec["returned_sha256"]
        out = {"band": seed, "arm": arm, "condition": cond,
               "wall_seconds": round(time.time() - t0, 1),
               "records": recs}
        ckpt.write_text(json.dumps(out, indent=1))
        cells[(arm, cond)] = out
        print(f"[lg] cell {seed} {arm} {cond}: "
              f"{sum(1 for r in recs.values() if r['solved'])}"
              f"/{len(recs)} wall={out['wall_seconds']}s",
              flush=True)
    return cells


# --- step 7: the mechanical worksheet (A.7) ---------------
def death_round_of(round_log):
    for e in round_log:
        if not any(lab == "BASE"
                   for _s, lab in e["frontier_in"]):
            return e["round"]
    return None


def worksheet(bands_cells, records):
    """bands_cells: {seed: {(arm, condition): cell}}.
    Returns the A.7 worksheet: W / R / H sets (band,
    task, distractor carried), the median cost ratio over
    R, per-arm death-round distributions over infected
    cells, and the verdict string (gate/VOID outcomes are
    the caller's, applied before this worksheet)."""
    W, R, H = [], [], []
    ratios = []
    deaths = {"stock": [], "guarded": []}
    l5 = []
    for seed, cells in bands_cells.items():
        stock_clean = cells[("stock", "clean")]["records"]
        guarded_clean = cells[("guarded", "clean")]["records"]
        for task_id, rec in stock_clean.items():
            if rec["solved"] and \
                    not guarded_clean[task_id]["solved"]:
                H.append({"band": seed, "task": task_id})
        for rec in records:
            cond = f"infected_{rec['id']}"
            s_inf = cells[("stock", cond)]["records"]
            g_inf = cells[("guarded", cond)]["records"]
            for task_id, srec in s_inf.items():
                deaths["stock"].append(
                    death_round_of(srec.get("round_log", [])))
                deaths["guarded"].append(death_round_of(
                    g_inf[task_id].get("round_log", [])))
                l5.extend(g_inf[task_id].get(
                    "l5_violations", []))
                if stock_clean[task_id]["solved"] \
                        and not srec["solved"]:
                    w = {"band": seed, "task": task_id,
                         "distractor": rec["id"]}
                    W.append(w)
                    if g_inf[task_id]["solved"]:
                        R.append(w)
                        ratios.append(
                            g_inf[task_id]["score_calls"] /
                            srec["score_calls"])
    ratios_sorted = sorted(ratios)
    median = None
    if ratios_sorted:
        n = len(ratios_sorted)
        median = ratios_sorted[n // 2] if n % 2 else (
            ratios_sorted[n // 2 - 1] +
            ratios_sorted[n // 2]) / 2
    if l5:
        verdict = "VOID"
    elif not W:
        verdict = "NOT_REPRODUCED"
    elif H:
        verdict = "GUARD_HARMFUL" if R else "GUARD_REFUTED"
    elif len(R) == len(W):
        verdict = "GUARD_ADOPTED" if median is not None \
            and median <= 3 else "RECOVERY_AT_COST"
    elif R:
        verdict = "GUARD_PARTIAL"
    else:
        verdict = "GUARD_REFUTED"
    return {"W": W, "R": R, "H": H,
            "cost_ratios": ratios_sorted,
            "median_cost_ratio": median,
            "death_rounds": deaths,
            "l5_violations": l5, "verdict": verdict}


# --- main: gate mode (steps 2-3) and the act-gated run ----
def _fail(msg):
    print(f"[lg] STOP — {msg}", flush=True)
    sys.exit(2)


def main():
    args = sys.argv[1:]
    mode = args[0] if args else "gate"
    if mode == "gate":
        ctx = load_dev_context()
        gate, anchor = run_dev_gates(ctx)
        ok = gate["verdict"] == "PASS" \
            and anchor["verdict"] == "PASS"
        print(f"[lg] DEV GATES — L4={gate['verdict']} "
              f"L1/L2={anchor['verdict']}", flush=True)
        sys.exit(0 if ok else 2)
    if mode != "run":
        _fail(f"unknown mode {mode!r} (gate | run)")
    # A.6 step 0: no act record, no run.
    if "--act" not in args:
        _fail("run requires --act <activation record json> "
              "(A.6 step 0)")
    act = json.loads(Path(
        args[args.index("--act") + 1]).read_text())
    for field in ("verdict_ref", "seeds",
                  "registry_snapshot", "operator", "window"):
        if field not in act:
            _fail(f"act missing field {field!r} (section 8)")
    seeds = act["seeds"]
    used = {20261501, 20261502, 20261503,
            20261601, 20261602, 20261603}
    if len(seeds) != 3 or seeds != sorted(seeds) or \
            seeds[1] != seeds[0] + 1 or \
            seeds[2] != seeds[1] + 1 or \
            any(s in used for s in seeds):
        _fail(f"act seeds {seeds} violate A.5 (three "
              f"consecutive, disjoint from used blocks)")
    snap = act["registry_snapshot"]
    reg_path = Path(snap["path"])
    if not reg_path.exists():
        _fail(f"registry snapshot not found: {reg_path}")
    actual_sha = hashlib.sha256(
        reg_path.read_bytes()).hexdigest()
    if actual_sha != snap["sha256"]:
        _fail("registry snapshot sha256 mismatch "
              f"({actual_sha} != {snap['sha256']})")
    records = _registry_records(reg_path)
    if [r["id"] for r in records] != snap["ids"]:
        _fail("registry snapshot ids mismatch")
    base = _base_dir()
    # Steps 2-3, fresh in this session.
    ctx_dev = load_dev_context()
    gate_path = STATE / "gate.json"
    if gate_path.exists():
        gate_path.unlink()
    anchor_path = STATE / "anchor_dev.json"
    if anchor_path.exists():
        anchor_path.unlink()
    gate, anchor = run_dev_gates(ctx_dev)
    if gate["verdict"] != "PASS":
        _fail("L4 gate FAIL — instrument void (A.6 step 2)")
    if anchor["verdict"] != "PASS":
        _fail("L1/L2 reproduction FAIL — instrument void "
              "(A.6 step 3)")
    # Step 4: the battery gate, as its own adapter (B.3).
    gate_cmd = [sys.executable,
                str(HERE / "lineage_guard_gate.py"),
                "--registry", str(reg_path),
                "--state-dir", str(STATE),
                "--base", str(base)]
    if "--battery-dir" in args:
        gate_cmd += ["--battery-dir",
                     args[args.index("--battery-dir") + 1]]
    rc = subprocess.run(gate_cmd).returncode
    if rc != 0:
        guarded_rep = STATE / "battery_guarded.json"
        overall = None
        if guarded_rep.exists():
            overall = json.loads(
                guarded_rep.read_text())["overall"]
        verdict = "GUARD_REFUTED" \
            if overall == "SUSCEPTIBLE" else "VOID"
        TOP_RECORD.write_text(json.dumps({
            "experiment": "lineage-guard confirmation run "
                          "(PR #188)",
            "act": act, "verdict": verdict,
            "stopped_at": "A.6 step 4 (inoculation gate)",
            "guarded_battery_overall": overall}, indent=1))
        _fail(f"step 4 gate stop — verdict {verdict}")
    # Steps 5-6: bands and cells.
    bands_cells = {}
    band_digests = {}
    for seed in seeds:
        disc = base / "abc-v3-run-state" / \
            f"discovery_{seed}.json"
        if not disc.exists():
            _fail(f"band {seed} discovery missing: {disc} "
                  f"(A.6 step 5 — the v3 discovery path "
                  f"must produce it before the run)")
        ctx = load_band_context(seed, disc)
        band_digests[seed] = ctx["digest"]
        bands_cells[seed] = run_band_cells(ctx, records)
    # Step 7: worksheet. Step 8: the top record.
    ws = worksheet(bands_cells, records)
    TOP_RECORD.write_text(json.dumps({
        "experiment": "lineage-guard confirmation run "
                      "(PR #188)",
        "act": act,
        "gates": {"L4": gate["verdict"],
                  "L1_L2": anchor["verdict"],
                  "step4_battery": "PASS"},
        "band_digests": band_digests,
        "worksheet": ws, "verdict": ws["verdict"]},
        indent=1))
    print(f"[lg] RUN DONE — verdict={ws['verdict']}",
          flush=True)


if __name__ == "__main__":
    main()
