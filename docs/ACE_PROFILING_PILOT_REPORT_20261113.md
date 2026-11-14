# ACE Profiling Pilot — Report (2026-11-13)

**Status: PILOT, development band only. These numbers ESTIMATE variance
and RANK phases. They are not scientific evidence, not a gate result,
and must not be cited as a speedup or a bottleneck proof.** The full
analysis JSON is `docs/ACE_PROFILING_PILOT_ANALYSIS_20261113.json`.

Instrument: `code/ace_operational/profiling_observer.py` (schema
`ace-profiling/1.0`), tests in
`code/ace_operational/test_profiling_observer.py`. Base:
`origin/main` @ `08bd836`. No existing file is modified by this PR:
the observer wraps `pilot_abc` entry points from outside and can be
switched off entirely; sealed instruments and the official run driver
are untouched.

## Design in one paragraph

Manifest once per run (digests of build/solver/catalog/config, schema
version, clock domain per source, job process model, timeout policy,
instrumentation flag + sampling, buffer limit, rotation/retention);
lifecycle per job/attempt; phase spans with `parent_id`, wall
inclusive/self (self = inclusive − union of child intervals; CPU
user/system as separate non-overlapping rusage components); per-job
summary with queue wait explicitly **N/A** (no coordinator exists;
building a lease coordinator is not a prerequisite), logical score
calls, cache hit/miss **N/A** (no active cache — a shadow
potential-duplicate counter is reported under its own name), sampled
peak RSS with stated scope, process I/O bytes with stated scope, and
`solved` / `termination_reason` / `infra_status` as three separate
fields. Output is an append-only sidecar (JSONL segments + manifest)
kept separate from the scientific records. Collection is fail-open
for the work and fail-closed for the claim: completeness requires
reconciliation (footer present, contiguous seq, summarised jobs ==
registered jobs, paired spans, `dropped_events` accounted) — a zero
drop counter alone is not completeness.

## Pilot workload

Development band, arm-A fixed config, `solve_with_config` +
full verify per job. 72 tasks (families pricing + shipping, levels
1–3, seeds 1–12, generation failures excluded by the universe
builder), 4 blocks per task in ABBA order (off, on, on, off),
budget 200, 288 job records total, 144 instrumented jobs, 2,050
logical score calls (mean 14.2 per job). Run id
`profiling-pilot-a53e7ecc`; build digest `4dfe1768…`, config digest
`984f06b8…`, catalog digest `ef776cf9…`. Sidecar (1 segment,
1,057,064 bytes, sha256
`5ebad54eb7dadcdaa6b517afe3c2e2dfcc3a993387fff63666fdffb441e20e24`)
is held in the lane's handover store
(`~/workspace/ace-omega/handover/profiling_pilot_20261113/`), not in
git; reproducing it is one command (below).

**Workload character (limitation):** all 144 instrumented jobs ended
`shown_perfect` / solved — this universe is saturated for arm A, so
the ranking describes an easy-workload regime. A budget-exhausting
workload may shift share toward enumeration and shown execution;
that is a question for a follow-up pilot, not something this one
settles.

## Completeness and observer integrity

- Sidecar verdict: **complete** — 1,585 events, `dropped_events = 0`,
  footer present, seq contiguous, 144/144 registered jobs summarised.
- Scientific-field equality, instrumented vs off, per task
  (`code`, `shown_score`, `evals`, `solved`): **0 mismatches** in 72
  tasks. Equivalence of `ProfilingBudget` scores against the plain
  `Budget` (including broken code) is also pinned by unit tests.

## Variance estimate

Instrumented job wall: mean 11.43 ms, sd 19.40 ms (CV ≈ 1.70) —
heavy-tailed. Heaviest single job: `task_97e65db72a0b00e7`
(shipping L1 seed 2), 85.1 ms = **5.2% of the whole critical path**,
18 score calls. It is retained as data, not discarded as an outlier;
the top of the distribution is where this solver's time actually
goes. Uninstrumented job wall: mean 5.1 ms, sd 11.4 ms.

## Phase ranking (attributed, disjoint partition)

Shares of instrumented job wall; 95% CIs from a cluster bootstrap
(2,000 resamples, cluster = task, each cluster carrying all its
seeds/blocks). `enumeration` inclusive total was 0.325 s (19.7%);
its children are split out below, so it is not double-counted in
this partition. `verify_full` (runner-side, not a solver phase) took
0.9% and unattributed time (collector emits + glue) 7.0%.

| # | phase | share | 95% CI |
|---|-------|-------|--------|
| 1 | parse | 38.8% | 24.7–53.3 |
| 2 | compile | 30.0% | 16.0–43.7 |
| 3 | transform_serialize | 18.9% | 9.9–29.6 |
| 4 | dedup_frontier (derived residual) | 1.8% | 1.3–2.6 |
| 5 | exec_shown (self) | 1.4% | 1.1–1.9 |
| 6 | checkpoint_io | 1.1% | 0.8–1.4 |
| 7 | queue_startup | 0.23% | 0.13–0.41 |
| 8 | aggregation | 0.01% | 0.008–0.013 |

Blocks (the decisions should use blocks, not the parse/compile
split, whose CIs overlap): **parse+compile = 68.8% [55.5–79.5]**;
**parse+compile+transform_serialize = 87.6% [79.9–92.3]**. Source
text processing is the critical path; actually *running* the shown
cases (`exec_shown` self) is 1.4%.

**Parse caveat, stated plainly:** the `parse` row is the observer's
dedicated `ast.parse` pass — work the baseline does *inside*
`compile()`. It therefore measures the size of the parse component,
not extra baseline time, and the `compile` row already contains
its own internal parse. The baseline-true statement is the block
statement above, plus: compile alone is 0.493 s against a total
uninstrumented wall of 0.740 s for the same jobs.

Structural counts behind the ranking: 336 enumeration rounds;
1,344 transform calls (4 operator groups × 336 rounds — **the same
source is re-parsed by every group in every round**); 2,050 score
calls, of which 1,816 reached compile (234 failed parsing and
short-circuited to −1, exactly as the baseline behaves).

## Instrumentation overhead (measured, never subtracted)

Paired per task (median of blocks): **+1.50 ms per job**, median
on/off ratio **1.65×**; totals ratio 2.23× (1.646 s vs 0.740 s).
The overhead is dominated by the dedicated parse pass and per-call
rusage reads. No constant overhead was subtracted from any timing
in this report. For any repeat of this instrument, the parse pass
should be sampled rather than per-call — recorded here as a known
instrument flaw, with its size measured rather than hidden.

## First optimisation candidate

**Parse-once / compile-once in the candidate path** (search-set
preserving): within one solve round, parse the current source once
and let the four operator groups consume the shared tree; in the
scoring path, reuse the compiled code object for an identical
source string instead of recompiling per call. Parse and compile
are pure functions of the exact source, and the candidate set,
order, and scores are unchanged — this is an attribution-preserving
refactor, not an approximate one.

Explicitly **not** the candidate: a score/compile *cache* as the
main lever. The shadow counter shows duplicate score calls are
only 102 / 2,050 (**5.0%**; 1,948 distinct keys) — a cache caps out
near that share. The cost is per-distinct-candidate parse/compile,
repeated across groups and rounds; that repetition is what the
candidate removes.

Promotion gates for the candidate (unchanged from the profiling
blueprint): (1) equivalence replay — scientific fields identical
per task at the same timeout policy on a named workload; (2) a
separate speedup confirmation on a fresh workload that played no
part in choosing the candidate, with a three-state verdict
(confirmed / regression / inconclusive) against a delta fixed at
preregistration. No speedup figure is promised here.

Thresholds still TBD by the owner/maintainer before any expansion
of this instrument: acceptable overhead ceiling, completeness
threshold, sidecar disk quota — rotation (16 MiB segments, sha256
index) and the retention policy are already stated in the manifest.

## Reproduce

```bash
cd code
python3 -m unittest ace_operational.test_profiling_observer
python3 -m ace_operational.profiling_observer pilot --out <dir>
python3 -m ace_operational.profiling_observer analyze --out <dir>
```
