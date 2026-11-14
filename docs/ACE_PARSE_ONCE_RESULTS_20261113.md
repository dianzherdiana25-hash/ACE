# Parse-once / Compile-once — Equivalence + Speedup Confirmation (2026-11-13)

**Candidate:** the first optimisation selected by the profiling
pilot (PR #178, stacked base for this PR). **Class:**
search-set-preserving — candidate set, enumeration order, scores
and solve outputs are unchanged; only redundant re-parsing and
re-compilation of identical source text are removed.

## What changed (all in `pilot_abc.py`)

1. **Parse-once per round.** `variants_by_group` parses the current
   source once and shares the (read-only) tree with all four
   operator groups. Previously `_boundary`, `_basis` and
   `_multiplier` each re-parsed the same source on every round
   (the pilot counted 1,344 transform calls against 336 enumeration
   rounds). Group functions still parse for themselves when called
   without a tree — that unshared path is the frozen baseline
   reference used by the bench and the tests.
2. **Compile-once per distinct source.** `_budget_for` now returns
   `CachingBudget`, a `Budget` subclass that memoises the compiled
   code object per distinct source string and re-executes it in a
   fresh namespace on every call, exactly as `Budget.score` does.
   This is not a score cache: every call genuinely re-executes;
   only the redundant `compile()` of an identical source is skipped.
   Scores, `used` accounting and −1-on-any-exception are unchanged.

`profiling_observer.instrumented_solver` was updated to pass the
optional tree through its group wrappers (one line); nothing else
in PR #178 changes.

## Gate 1 — equivalence (must pass before any timing claim)

- Unit/differential tests (`test_parse_once.py`, 6 tests): shared-tree
  variants == unshared variants (set and order) over the corpus;
  group functions proven not to mutate the shared tree;
  `CachingBudget` scores == plain `Budget` scores including broken
  code, with exactly one code object per distinct compilable source;
  candidate solve == reference solve on 100+ tasks across levels
  1–4 (full result dicts: code, shown score, credits, evals);
  `evaluate_config` totals match the reference; the profiling
  observer still wraps the candidate correctly.
- Bench output equivalence: every bench run compares the full
  output tuple per task across 10 solves (5 per mode). **Zero
  mismatches** in both runs below (72/72 tasks each).
- Equivalence replay on the pilot workload (seeds 1–12, the
  workload that selected the candidate): median ratio 0.8117 —
  reported for completeness; per the confirmation discipline this
  workload's timing is *not* the verdict.

## Gate 2 — speedup confirmation (fresh workload)

Bench: `code/ace_operational/parse_once_bench.py`. Workload:
pricing + shipping, levels 1–3, **seeds 501–512** (disjoint from
the pilot's 1–12), 72 tasks, budget 200. Method: warm-up solve per
mode; 5 timed solves per mode per task with alternating start
order; per-mode medians (jobs are milliseconds on a shared VM —
the first bench version with medians of 2 produced stall-poisoned
ratios and was replaced before any verdict was taken from it);
task-cluster bootstrap (2,000 resamples) over per-task ratios.
Preregistered delta: 0.05 — CONFIRMED requires the whole 95% CI
below 0.95; REGRESSION requires it entirely above 1.0.

| measure | value |
|---|---|
| tasks | 72 |
| output mismatches | 0 |
| median per-task ratio (cand/base) | **0.8116** |
| 95% CI | **[0.8035, 0.8215]** |
| summed per-task medians | 0.107 s → 0.086 s |
| tasks slower under candidate | 1 / 72 (ratio 1.18, ~ms-scale task) |
| **verdict** | **CONFIRMED** (≈18.8% median improvement, above the 5% delta) |

Full per-task data: `docs/ACE_PARSE_ONCE_CONFIRMATION_20261113.json`.

## Honest bounds

- The measured regime is the same saturated dev-band workload
  family as the pilot (levels 1–3, arm-A config). The ratio is a
  property of this workload and this host, not a universal solver
  constant; a budget-exhausting workload should be benched before
  extrapolating.
- Compile-once's share of the win is bounded by the duplicate rate
  the pilot measured (5.0% of score calls) plus the initial
  re-score of the incumbent each round; parse-once in
  `variants_by_group` is the larger component. The bench measures
  the package, not the split.
- Rollback is trivial: `_budget_for` returning the plain `Budget`
  and group functions being called without a tree restores the
  baseline behaviour exactly (that path is retained and tested).

## Reproduce

```bash
cd code
python3 -m unittest ace_operational.test_parse_once
python3 -m ace_operational.parse_once_bench            # fresh seeds 501-512
python3 -m ace_operational.parse_once_bench --seeds 1-12  # replay workload
```
