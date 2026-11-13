# Validator Pra-Audit — Stage-3 Readiness (2026-11-13, worker pos validasi & pra-audit)

Extension design: `PREAUDIT_VALIDATOR_S3_EXTENSION_DESIGN.md`. Built and
tested offline against development evidence only (PR #184 harness outputs,
dev witnesses catalog_control-020/-021 on band 20261501). Sealed Stage-3
bands 20261601–03 and Ian's unpublished package were not touched.

## New checks (C4, active only when the manifest declares `stage3_check`)

Task maps (per-task solved/timeout per arm per band):
- solved ∧ timeout in one record → TIDAK SESUAI / TASK_STATE_CONTRADICTION
- duplicate task_id → TIDAK SESUAI / DUPLICATE_RECORD
- non-boolean/missing solved/timeout → UNKNOWN / INPUT_MALFORMED
- declared counts_ref: map aggregate [solved, total] must equal the
  referenced pair → COUNT_MISMATCH

Frontier provenance logs (per round):
- round sequence exactly 1..N → ROUND_SEQUENCE_BROKEN
- n_scored ≤ n_candidates_generated → COUNT_MISMATCH
- frontier member list vs frontier_size → COUNT_MISMATCH
- member without identity → UNKNOWN / PROVENANCE_MISSING
- parent never appearing in an earlier round of the complete log →
  TIDAK SESUAI / PROVENANCE_BROKEN
- true_path internal consistency (in_frontier ⇒ generated; scored ⇒
  generated; rank non-null iff scored) → FIELD_MISMATCH

Registry v2 adds those five codes; the registry version is a spec-digest
configuration component, so Stage-3-era verdicts are digest-distinguishable
from v2-era verdicts. Manifests without `stage3_check` produce exactly the
v2 three-check report (structural compatibility, regression-tested).

## Ladder results

- Stage-3 suite: 12/12 PASS — fixtures built from the verbatim PR #184
  cell_control records; oracle agreement on task-map aggregation and the
  round-series rule; 8 seeded defects each caught by its owning code;
  C4 false positives 0/2 valid variants; activation rule proven (no
  stage3_check → no C4, exit codes unchanged).
- Holdout S3, authored after freeze commit `053cd2d` (validator SHA-256
  `c784b9ca…`): 3/3 PASS on first run — new shapes: band/arm fields with
  counts_ref into a v3-style band record, `id`-keyed frontier members,
  positive-form true_path, timed-out tasks in the aggregate.
- Regression: all v1+v2 suites and both earlier holdouts pass (one oracle
  constant followed the new spec: registry version 2 + stage3_check in the
  ruleset closure — a spec change, applied to the oracle, not the verdicts).
- Full sweep: **318 tests OK (17 skipped)** = 303 + 12 + 3.

## Dev pilot on the real PR #184 outputs

Manifest over the three real cell files (control / frontier_only /
rounds_only), task maps for all three + frontier logs for both control
witnesses: **C4 SESUAI (5/5 items)**, C1 SESUAI; C2/C3 UNKNOWN (the dev
cells declare no count assertions or verdict pair — honest, expected).
Spec digest `5b0ea067692683b2…`. Files: `evidence/preaudit_pilot_s3/`.

## Readiness for Ian's Stage-3 package

Ready to run the moment the package is published: write its manifest
(C1 over all artifacts; C2 assertions for its counts; C3 against its
preregistration), declare `stage3_check` against its per-task maps and
frontier logs, run, and report the four checks under one spec digest.
Named limit, stated before the fact: the unpublished package's exact file
layout is unknown from this pos. If its shapes differ from the declared
forms, C4 fails toward UNKNOWN — never toward a false verdict — and only
the manifest declaration needs adjusting; the checks are shape-tested
against the only Stage-3-shaped evidence in existence today, the PR #184
dev harness.
