# ACE Ω Checkpoint — Addendum 52 (A/B/C v3 build step 1 shipped; G3 application run starts)

Date: 2026-11-13. Two gates cleared in one movement.

## A/B/C v3, build step 1 — PR #151

`solve_task(task, adapter, extra_keys=(), extra_chains=(),
*, max_score_calls=None)` is lifted to module level in
`operator_discovery.py` on branch
`research/ace-omega-abc-v3-solver-20261113` (commit
c5e62a8, stacked on the B-3 branch; remote tree carries
the full lineage files per the F-1 lesson). The greedy
loop is verbatim; `run_discovery` delegates to it;
`max_score_calls` caps scoring evaluations — the shared
budget the three v3 arms run under.

Gates: `test_operator_discovery` passes UNCHANGED
(9 tests); the **v4-replication gate** against the
lifted solver reproduces `operator_discovery_v4.json`
**EXACTLY** on every count and every admitted key set
(1,376.6 s; `evidence/v3_solver_replication_run.json`;
the first launch of this gate died in a runtime
restart with no output and was re-run clean); lineage
sweep **265 OK** (262 + 3 budget tests). Build order
continues: grid universe census per stratum →
calibration → preregistration (DI composite) → run.

The frozen G3 application artifact is untouched by
this step: the application executes from the B-3
branch tip, which contains no lift.

## G3 application run — starting

Protocol `5f907362…b8bb6d` (Addendum 50). The runner
executes the locked text in five phases as separate
processes from a dedicated worktree at 83041dc: sets
(fresh grid universe seed 20261113; pricing band
50000–59999 with band-level program exclusion —
stronger than the locked digest-level fence, ratified
by the hub; constructed stratum seeds 60000–60099) →
per-family discovery → sham/constructed/control arms
→ finalize (composite → kernel record + audit →
dossier → instrument). The dossier then enters the
two-checker verification queue; **G3 remains
NOT_ASSESSED until it is scored there.**
