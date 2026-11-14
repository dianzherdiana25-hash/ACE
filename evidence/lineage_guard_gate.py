"""ACE Omega — lineage-guard step-4 gate adapter
(PR #188 Part B.3).

Binds the PR #175 distractor-inoculation battery to the
two solver arms of evidence/lineage_guard_harness.py:

  stock   = solve_task_param at the stock defaults,
            guard OFF (via the harness's run_solve);
  guarded = solve_task_guarded, guard ON.

Both bindings run under the PR #175 witness protocol:
cap 4000 score calls, 60 s wall per solve, witness
universe reconstructed by the v3 split at seed 20261501,
catalog under test = the band's admitted keys with every
registered distractor key removed (the battery injects
each distractor at the end, one at a time — the PR #175
injection form). The registry is loaded through PR
#175's fail-closed loader; the battery module itself is
consumed as-is and never modified (located via
--battery-dir, else $ACE_BATTERY_DIR, else the repo
tree's code/ace_operational/).

Outputs (into --state-dir, default the harness's
lineage_guard_state/): battery_stock.json and
battery_guarded.json (schema ace.distractor_inoculation
.v1, unmodified) plus anchor_battery.json — the anchor
comparison in PR #167's verdict form over the two
bindings' per-witness outcomes (guarded must not lose
any witness either stock binding solved, in either
condition). Exit code is 0 only when guarded ==
NOT_SUSCEPTIBLE and stock == SUSCEPTIBLE (the positive
control) and the anchor verdict is NO_REGRESSION and
the L5 actuation check held on every guarded solve —
the A.6 step-4 stop rule is therefore mechanical.
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lineage_guard_harness as lg

BATTERY_CAP = 4000  # PR #175 witness protocol


def _load_battery(battery_dir):
    candidates = []
    if battery_dir:
        candidates.append(Path(battery_dir))
    import os
    if os.environ.get("ACE_BATTERY_DIR"):
        candidates.append(Path(os.environ["ACE_BATTERY_DIR"]))
    candidates.append(HERE.parent / "code" / "ace_operational")
    for cand in candidates:
        mod_path = cand / "distractor_inoculation.py"
        if mod_path.exists():
            spec = importlib.util.spec_from_file_location(
                "distractor_inoculation", mod_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod, cand
    raise SystemExit(
        "distractor_inoculation.py (PR #175) not found in "
        f"any of: {[str(c) for c in candidates]} — pass "
        "--battery-dir <dir containing it>")


def main():
    args = sys.argv[1:]

    def opt(name, default=None):
        return args[args.index(name) + 1] \
            if name in args else default

    registry_path = opt("--registry")
    if not registry_path:
        raise SystemExit("--registry <path> is required "
                         "(the activation record supplies it)")
    state_dir = Path(opt("--state-dir", str(lg.STATE)))
    state_dir.mkdir(parents=True, exist_ok=True)
    battery, battery_dir = _load_battery(opt("--battery-dir"))
    registry = battery.load_registry(registry_path)
    ctx = lg.load_dev_context()

    distractor_keys = {rec["_key_tuple"] for rec in registry}
    catalog_keys = [k for k in ctx["keys"]
                    if k not in distractor_keys]
    print(f"[lg-gate] registry: "
          f"{[r['id'] for r in registry]}; catalog under "
          f"test: {len(catalog_keys)} keys (admitted "
          f"{len(ctx['keys'])} minus registered)",
          flush=True)

    caches = {"stock": {}, "guarded": {}}
    l5_all = []

    def make_solve(binding):
        def solve(task_id, keys):
            cache_key = (task_id, tuple(keys))
            if cache_key in caches[binding]:
                return caches[binding][cache_key]
            task = ctx["control"][task_id]
            if binding == "stock":
                rec = lg.run_solve(
                    ctx, task, keys, flavour="param",
                    cap=BATTERY_CAP,
                    true_path_sha=lg.A_WIN.get(task_id))
            else:
                rec = lg.run_solve(
                    ctx, task, keys, flavour="guarded",
                    cap=BATTERY_CAP, guard=True,
                    true_path_sha=lg.A_WIN.get(task_id))
                l5_all.extend(rec.get("l5_violations", []))
            caches[binding][cache_key] = rec["solved"]
            return rec["solved"]
        return solve

    reports = {}
    for binding in ("stock", "guarded"):
        reports[binding] = battery.run_battery(
            catalog_keys=catalog_keys,
            solve=make_solve(binding), registry=registry)
        out = state_dir / f"battery_{binding}.json"
        out.write_text(json.dumps(reports[binding], indent=1))
        print(f"[lg-gate] {binding}: overall="
              f"{reports[binding]['overall']}", flush=True)

    # The anchor comparison (PR #167 verdict form) over
    # the two bindings' per-witness outcomes.
    regressions = []
    totals = {"stock": [0, 0], "guarded": [0, 0]}
    for e_stock, e_guarded in zip(
            reports["stock"]["distractors"],
            reports["guarded"]["distractors"]):
        assert e_stock["distractor_id"] == \
            e_guarded["distractor_id"]
        for w_stock, w_guarded in zip(
                e_stock["witnesses"], e_guarded["witnesses"]):
            assert w_stock["task_id"] == w_guarded["task_id"]
            for cond in ("clean", "injected"):
                s = w_stock[f"solved_{cond}"]
                g = w_guarded[f"solved_{cond}"]
                totals["stock"][0] += bool(s)
                totals["guarded"][0] += bool(g)
                totals["stock"][1] += 1
                totals["guarded"][1] += 1
                if s and not g:
                    regressions.append({
                        "distractor": e_stock["distractor_id"],
                        "task": w_stock["task_id"],
                        "condition": cond})
    anchor = {
        "artifact": "lineage-guard step-4 anchor comparison "
                    "(PR #167 anchor verdict form, computed "
                    "over the PR #175 battery bindings)",
        "baseline": {"binding": "stock (solve_task_param "
                                "defaults, guard OFF)",
                     "solved": totals["stock"][0],
                     "outcomes": totals["stock"][1]},
        "candidate": {"binding": "guarded "
                                 "(solve_task_guarded, "
                                 "guard ON)",
                      "solved": totals["guarded"][0],
                      "outcomes": totals["guarded"][1]},
        "regressions": regressions,
        "l5_violations": l5_all,
        "verdict": "NO_REGRESSION" if not regressions
                   else "REGRESSION_FOUND",
    }
    (state_dir / "anchor_battery.json").write_text(
        json.dumps(anchor, indent=1))

    ok = reports["guarded"]["overall"] == "NOT_SUSCEPTIBLE" \
        and reports["stock"]["overall"] == "SUSCEPTIBLE" \
        and anchor["verdict"] == "NO_REGRESSION" \
        and not l5_all
    print(f"[lg-gate] anchor={anchor['verdict']} "
          f"l5_violations={len(l5_all)} — "
          f"{'GATE PASS' if ok else 'GATE STOP'}",
          flush=True)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
