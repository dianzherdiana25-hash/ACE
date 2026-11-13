# Validator Pra-Audit — Stage-3 Extension Design (2026-11-13, worker pos validasi & pra-audit)

Extends v2 (PR #185) with checks over the new-shaped Stage-3 artifacts, so the
validator is ready before Ian's Stage-3 package (bands 20261601–03, sealed —
NOT touched by this work) is published. Development evidence only: the
PR #184 intervention harness outputs (dev witnesses catalog_control-020/-021,
band 20261501) and synthetic fixtures in those shapes.

## Activation rule (compatibility)

The new check **C4 activates only when the manifest declares a
`stage3_check` block**. Manifests without it produce exactly the v2 report
(three checks, same states, same exit codes) — the v1/v2 regression lock is
therefore structural, not just tested. When `stage3_check` is present, it is
part of the ruleset closed by `validation_spec_digest`.

## C4 — Stage-3 artifact consistency

Manifest block:
```
"stage3_check": {
  "task_maps":    [ {"artifact": ..., "pointer": ..., "arm": "B",
                     "counts_ref": {"artifact": ..., "pointer": ...}} ],
  "frontier_logs":[ {"artifact": ..., "pointer": ...} ]
}
```
Pointers follow the v1 pointer language. All C4 inputs must pass C1 first
(same dependency rule as C2/C3: failed integrity → UNKNOWN/DEPENDENCY_UNRESOLVED).

### Task maps (per-task solved/timeout, per arm per band)
The pointer resolves to either a dict task_id → record or a list of records
(each record carrying `task_id`). Per record, `solved` and `timeout` must be
booleans:
- both true in one record → TIDAK SESUAI / `TASK_STATE_CONTRADICTION`
  (a task cannot be both solved and timed out in the same record);
- a task_id appearing twice → TIDAK SESUAI / `DUPLICATE_RECORD`;
- missing/non-boolean fields → UNKNOWN / `INPUT_MALFORMED` (record shape
  not decidable, checker stops);
- when `counts_ref` is declared, the pair [solved_count, record_count]
  aggregated from the map must equal the referenced pair →
  TIDAK SESUAI / `COUNT_MISMATCH` on inequality.

### Frontier provenance logs (per round)
The pointer resolves to one series: a list of round entries (e.g. a record's
`round_log` in a PR #184 cell file). Per series:
- `round` values are exactly 1..N in order → else TIDAK SESUAI /
  `ROUND_SEQUENCE_BROKEN`;
- `n_scored <= n_candidates_generated` when both present → else
  TIDAK SESUAI / `COUNT_MISMATCH`;
- `frontier_size`, when present, is a non-negative integer → else
  UNKNOWN / `INPUT_MALFORMED`;
- if a `frontier` member list is present: its length must equal
  `frontier_size` (COUNT_MISMATCH); every member must carry an identity
  (`candidate`/`id`/`hash`) — missing identity → UNKNOWN /
  `PROVENANCE_MISSING`; every member's `parents` must resolve to identities
  seen in earlier rounds of the same series (round-1 members must have no
  parents or be declared seeds) — an unresolvable parent in a complete log
  → TIDAK SESUAI / `PROVENANCE_BROKEN`;
- a `true_path` block, when present, must be internally consistent:
  `in_frontier ⇒ generated`, `scored ⇒ generated`, `rank` non-null iff
  `scored` → else TIDAK SESUAI / `FIELD_MISMATCH`.

`stage3_check` present but with neither list, or entries malformed →
UNKNOWN (`NOT_DECLARED` / `INPUT_MALFORMED`). C4's false-positive class:
shape rigidity of the new artifact forms — it fails toward UNKNOWN, and the
FP probes below measure it on the real dev-harness shapes.

## Reason-code registry v2

`REASON_CODE_REGISTRY_VERSION` becomes "2", adding:
`TASK_STATE_CONTRADICTION`, `DUPLICATE_RECORD`, `ROUND_SEQUENCE_BROKEN`,
`PROVENANCE_BROKEN` (all TIDAK SESUAI) and `PROVENANCE_MISSING` (UNKNOWN).
The registry version is a configuration component of the spec digest, so
v2-era and Stage-3-era verdicts are distinguishable by digest even on the
same package. All v1/v2 codes unchanged.

## Self-test ladder (v1 discipline, this extension)

- Independent oracle extension for the C4 aggregations and sequence rule.
- Fixtures built from the real PR #184 dev outputs (cell_control records for
  020/021, values embedded with provenance noted) — a fully SESUAI C4 run.
- Seeded defects per new rule; FP probes (valid variants: member-list absent
  vs present, dict vs list task maps, extra fields, round entries with
  additional telemetry keys).
- Regression: all v1+v2 suites and both holdouts pass; a v2 pilot manifest
  (no stage3_check) still yields the identical three-check report shape.
- New holdout authored after this extension freezes.

## Readiness statement (what "ready" means here)

When Ian's Stage-3 package is published, readiness = a manifest can be
written against its artifacts (C1), its counts cross-checked (C2), its
verdict read against its preregistration (C3), and — with `stage3_check`
declared against its per-task maps and frontier logs — C4. What is NOT
claimed: the exact file layout of Ian's unpublished package is unknown from
this pos; if its shapes differ from the declared forms, C4 fails toward
UNKNOWN (never a false verdict) and the manifest/declaration is adjusted —
the checks themselves are shape-tested against the only Stage-3-shaped
evidence that exists today, the PR #184 dev harness outputs.
