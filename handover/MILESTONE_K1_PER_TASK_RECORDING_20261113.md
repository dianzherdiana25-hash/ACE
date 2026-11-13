# FIRST-USEFULNESS MILESTONE #1 — PER-TASK CONTROL RECORDING (2026-11-13)

Status: BUILT + VERIFIED (see evidence). Adopted by
hub act (2026-11-13 ~21:56 WIB) from the coordination
harvest #2 candidate, with Ian's desk assessment.
This is ACE's first named usefulness milestone: a
small, real engineering job with a checked result.

## The gap (named, and lived)

The A/B/C v3 run state recorded aggregate arm
outcomes (counts and flips) but NOT which control
tasks each arm solved. When the control regression
surfaced, recovering just the two failing task ids
(catalog_control-020/-021) required the full Stage 0
identification replay of the control-regression line
(PR #174) — a whole experiment stage spent
reconstructing information the original run had in
its hands and threw away. The standing rule since
the v3 seal ("future runs must record per-task
control results") existed as a sentence; this
milestone makes it code.

## The change

`abc_v3_run.run_band` (the v3 run driver) now records,
for every arm, a per-task map for BOTH the evaluation
and control splits — `{task_id: {solved, timeout}}` —
(a) in the arm checkpoint file (new `per_task` key)
and (b) in the returned band record (new top-level
`per_task` key). The change is strictly ADDITIVE:
every pre-existing key, count, and semantic is
untouched; checkpoints written before the milestone
load unchanged and yield an empty map for their arm
(their per-task truth is unrecoverable — which is
the point of the milestone). The pattern is the
standing rule for every future run driver, not only
this one: per-task results are recorded BY DEFAULT.

## Verification (evidence/per_task_recording_verification.json)

Band 20261501 in a scratch state dir with arm C's
checkpoint withheld, so the patched driver recomputed
exactly one arm against known truth (Stage 0,
PR #174): the new control map carries 34 entries,
32 solved, and the failures are EXACTLY
catalog_control-020 and catalog_control-021; the
aggregate control_counts are unchanged ([32, 34]);
the evaluation map is complete; the rewritten
checkpoint carries the per_task key; legacy arms
resume to empty maps without error. All checks pass.

## What it pays into

- Control-regression line: witness identification
  becomes a file read, never a replay stage.
- The distractor-inoculation battery (PR #175):
  witnesses are per-task data by definition.
- Stage 3 design: per-task traces are its raw
  material (and its logging-invariance gate now has
  something concrete to be invariant ABOUT).

— Ian, 2026-11-13.
