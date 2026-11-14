# Profiling Pilot 2 — Post-Parse-Once Profile (2026-11-13)

**Status: PILOT, development band only. Estimates and ranking, not
evidence.** Same instrument (`ace-profiling/1.0`), same protocol as
pilot 1 (PR #178): 72 tasks (pricing + shipping, levels 1–3, seeds
1–12), ABBA paired blocks (off, on, on, off), budget 200, 144
instrumented jobs. The code under measurement now includes
parse-once / compile-once (PR #180, stacked base of this PR).
Analysis: `docs/ACE_PROFILING_POST_PARSE_ONCE_ANALYSIS_20261113.json`.
Sidecar: 1 segment, 1,056,751 bytes, sha256
`2c70d87e4895cf5609c43df39beebdbd4825908ed201fbc48ffed7f76083120d`,
held in the lane handover store
(`~/workspace/ace-omega/handover/profiling_pilot_post_parse_once_20261113/`),
run id in the analysis JSON.

**Instrument fidelity change (disclosed):** the harness now mirrors
the shipped budget path — off mode uses `pilot_abc._budget_for`
(the `CachingBudget`), and the instrumented twin
`ProfilingBudget` gained a `cache_compiles=True` option that
memoises `compile()` exactly as the product does (default off =
PR #178 behaviour; score equivalence is test-pinned). Without this,
the instrument would have re-introduced per-call compiles that the
product no longer performs.

**Workload fingerprint is identical to pilot 1** — 2,050 score
calls, 1,948 distinct sources, 102 shadow duplicates (5.0%), 336
enumeration rounds, 1,344 transform calls, 1,816 compile-reached
calls (234 parse failures) — so the two pilots differ only in
timing, never in what the solver did. Sidecar complete (1,585
events, dropped 0, reconciled); scientific fields on/off identical
for 72/72 tasks; all jobs solved (saturated workload, same caveat
as pilot 1).

## Ranking, side by side

Absolute attributed seconds are the robust comparison (the totals
differ); shares are of each pilot's own instrumented wall.

| phase | pilot 1 (s) | pilot 1 share | pilot 2 (s) | pilot 2 share [95% CI] | Δ abs |
|---|---|---|---|---|---|
| parse (observer pass — see caveat) | 0.639 | 38.8% | 0.448 | 46.9% [28.7–62.3] | −30% |
| compile | 0.493 | 30.0% | 0.151 | 15.8% [9.5–26.4] | **−69%** |
| transform_serialize | 0.311 | 18.9% | 0.173 | 18.0% [7.1–33.6] | −44% |
| dedup_frontier (derived) | 0.030 | 1.8% | 0.040 | 4.2% [3.1–5.9] | +34% |
| exec_shown (self) | 0.023 | 1.4% | 0.020 | 2.1% [1.6–2.9] | −13% |
| checkpoint_io | 0.018 | 1.1% | 0.012 | 1.3% [1.0–1.7] | −32% |
| queue_startup | 0.004 | 0.23% | 0.002 | 0.25% [0.19–0.36] | −35% |
| aggregation | 0.0002 | 0.01% | 0.0002 | 0.02% [0.01–0.02] | ~0 |
| **instrumented wall total** | **1.646** | | **0.957** | | **−42%** |
| uninstrumented wall total | 0.740 | | 0.510 | | −31% |
| enumeration (inclusive memo) | 0.325 | | 0.199 | | −39% |
| unattributed | 0.115 | 7.0% | 0.097 | 10.1% | −16% |

Job wall: mean 11.43 ms → 6.64 ms, sd 19.40 → 13.05 ms. Heaviest
job is now `task_41fbc88d52f8df8e` (shipping L1 seed 10), 68.3 ms =
7.1% of the critical path (pilot 1's heaviest was 5.2%) — the tail
concentrates as the body shrinks; retained as data, as before.

**Parse caveat, sharper this time:** the `parse` row is the
observer's own dedicated `ast.parse` pass — in the shipped code
that work lives inside `compile()`, and with compile-once the
product performs it once per *distinct* source. The parse row is
therefore now mostly a measurement of the instrument, not of the
product, and it must not be read as the product's top cost. The
product-true reading is: **transform_serialize (0.173 s) is now
the largest product phase**, ahead of compile (0.151 s, the
distinct-source floor).

## Instrumentation overhead on the new code (as-is)

Median paired difference **+1.12 ms per job**, median on/off ratio
**1.63×** (pilot 1: +1.50 ms, 1.65×). Totals ratio 1.88×
(0.957 s vs 0.510 s). Still dominated by the dedicated parse pass
and per-call rusage reads; still never subtracted from any timing.
The v2-instrument prescription from pilot 1 stands (sample the
parse pass instead of running it per call).

## Next candidate (chosen by the numbers above)

**Per-round generation context for candidate generation** —
the transform_serialize phase. Per round, the group functions
currently recompute the same invariants: `_spec_numbers(spec)`
(a regex pass + int conversions) is run independently by three
groups, and three groups each walk the whole shared tree looking
for their own node kinds, on top of `_boundary`'s repeated
whole-string scans per Compare node. The candidate: compute the
spec numbers once per `variants_by_group` call and do one shared
walk that collects the node subsets each group needs, passed to
the groups as a context object — the same pattern as the shared
tree (groups keep a no-context fallback path, which stays the
equivalence reference). Class: search-set-preserving
(raw-set/order); the candidate set, order and scores are unchanged
by construction.

Why not the alternatives, in numbers:

- **Compile (0.151 s):** already at its floor — one compile per
  distinct source; the duplicate share that caching could still
  harvest is 5.0% of calls and is already harvested.
- **Dedup/frontier (0.040 s):** share doubled, but the absolute
  time is small and the row is a derived residual that absorbs
  fixed loop/bookkeeping costs as other phases shrink. Watch item
  for pilot 3, not a candidate.
- **Exec_shown (0.020 s), checkpoint_io, queue_startup,
  aggregation:** negligible or dev-runner artefacts, not solver
  costs.

**Promotion gates for this candidate (same two steps, fixed now,
before any build):** (1) equivalence replay — differential tests
against the no-context path plus per-task output equivalence on
the pilot workload at the same budget/timeout policy; (2) speedup
confirmation on a fresh workload (seeds 901–912 suggested —
disjoint from 1–12 and from 501–512), preregistered **delta =
0.05**, three-state verdict (CONFIRMED when the bootstrap 95% CI
of the median per-task ratio lies entirely below 0.95; REGRESSION
when entirely above 1.0; INCONCLUSIVE otherwise). No speedup
figure is promised here; the addressable ceiling is
transform_serialize's 0.173 s of instrumented wall.

## Reproduce

```bash
cd code
python3 -m unittest ace_operational.test_profiling_observer
python3 -m ace_operational.profiling_observer pilot --out <dir>
python3 -m ace_operational.profiling_observer analyze --out <dir>
```
