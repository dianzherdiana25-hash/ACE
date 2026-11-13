# Regression anchor — design + first self-test

Status: harness BUILT (`~/workspace/ace-omega/regression_anchor.py`,
harness-side like the other run drivers); identical-catalog
self-test PASSED 2026-11-13 (evidence below); the
empty-catalog self-test is QUEUED behind the A/B/C v3 gate
run (running it concurrently would contend for the CPU the
gate run's 60 s/task wall guards depend on). The build
subagent was interrupted by the 2026-11-13 12:49 WIB VM
replacement after writing the harness and the first
self-test evidence; this doc was completed by Ian from
the artifacts on disk.

## What it guarantees

Whenever an operator catalog changes, the anchor answers
one question with evidence: **what did the change lose?**
It solves a FIXED battery of evaluation tasks twice —
once restricted to the baseline catalog, once to the
candidate catalog — and reports per-class solved counts,
the regression list (classes where candidate < baseline),
improvements, and a verdict (REGRESSION_FOUND /
NO_REGRESSION) as a sealed-shape evidence artifact
(`ace.regression_anchor.v1`).

## Battery

Constructed by the v4 protocol's split, verbatim (the
same construction the replication guards use): pool =
first 3 singles per class, pair pool = first 6 mixed,
battery drawn from the evaluation remainder. Sizes:
`full` = all 29 evaluation tasks; `smoke` = round-robin
across class buckets capped by `--battery-size`. The
battery is identified by `battery_id` = sha256 of its
task-id list, so two anchor runs are comparable only
when their battery ids match.

## Catalogs

A catalog spec resolves to (admitted keys, chains) with
a content digest; the v4 catalog (from
`operator_discovery_v4.json`: 6 operators, 2 chains,
digest 388a464f…) is the standing baseline. Solving uses
the core `solve_task` restricted to the catalog's keys —
the same restriction the G4 WITH arm used.

## First self-test (identical catalogs)

Baseline v4 vs candidate v4, smoke battery 16 tasks
(battery_id ea56bd62…): **16/16 solved on both sides,
per-class identical, regressions [], verdict
NO_REGRESSION.** Evidence:
`evidence/regression_anchor_selftest-identical.json`.

## Outstanding

- Empty-catalog self-test (candidate = no operators):
  expected regressions exactly on the classes the v4
  catalog covers on this battery. Queued behind the v3
  gate run; its evidence file will be
  `evidence/regression_anchor_selftest-empty.json`.
- Trigger rule (standing): any future catalog change
  runs the anchor before the new catalog is used in a
  measurement; a REGRESSION_FOUND verdict blocks the
  change until it is explained in an addendum.

Brain of origin: Muse (build subagent + Ian).
